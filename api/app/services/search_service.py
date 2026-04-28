from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.config import settings
from app.connectors.amazonca_connector import AmazonCAConnector
from app.connectors.base import BaseConnector
from app.connectors.canadiantire_connector import CanadianTireConnector
from app.connectors.canadaweldingsupply_connector import CanadaWeldingSupplyConnector
from app.connectors.homedepot_connector import HomeDepotConnector
from app.connectors.kms_connector import KMSConnector
from app.connectors.scn_connector import SCNConnector
from app.models.normalized_result import NormalizedResult, SearchResponse
from app.services.analysis_service import AnalysisService
from app.services.scn_catalog_service import SCNCatalogService, SCNItem
from app.services.semantic_match_service import SemanticMatchService


class SearchService:
    def __init__(
        self,
        primary_connectors: list[BaseConnector] | None = None,
        secondary_connectors: list[BaseConnector] | None = None,
        connectors: list[BaseConnector] | None = None,
    ) -> None:
        self.primary_connectors = primary_connectors or connectors or [SCNConnector()]
        self.secondary_connectors = secondary_connectors or [
            KMSConnector(),
            CanadaWeldingSupplyConnector(),
            CanadianTireConnector(),
            AmazonCAConnector(),
            HomeDepotConnector(),
        ]
        # Backward compatibility for tests and handlers that still use .connectors.
        self.connectors = [*self.primary_connectors, *self.secondary_connectors]

        self.analysis_service = AnalysisService()
        self.scn_catalog_service = SCNCatalogService()
        self.logger = logging.getLogger(__name__)
        self._connector_lookup = self._build_connector_lookup(self.connectors)

    async def _run_connector_search(
        self,
        connector: BaseConnector,
        query: str,
        semaphore: asyncio.Semaphore,
        failure_log_message: str,
    ) -> dict[str, Any]:
        async with semaphore:
            try:
                results = await connector.search(query)
                return {
                    "connector": connector,
                    "results": results,
                    "warning": getattr(connector, "last_warning", None),
                    "error": None,
                }
            except Exception as exc:  # noqa: BLE001
                self.logger.error(
                    failure_log_message,
                    extra={"source": connector.source, "query": query},
                    exc_info=True,
                )
                return {
                    "connector": connector,
                    "results": [],
                    "warning": None,
                    "error": str(exc),
                }

    @staticmethod
    def _build_connector_lookup(connectors: list[BaseConnector]) -> dict[str, BaseConnector]:
        lookup: dict[str, BaseConnector] = {}
        for connector in connectors:
            aliases = {
                connector.source,
                connector.source.replace("_", ""),
                connector.source_label.lower(),
                connector.source_label.lower().replace(" ", ""),
                connector.source_label.lower().replace(" ", "_"),
            }
            for alias in aliases:
                lookup[alias] = connector
        return lookup

    def resolve_connector(self, connector_name: str) -> BaseConnector | None:
        normalized = connector_name.strip().lower()
        if not normalized:
            return None
        return self._connector_lookup.get(normalized) or self._connector_lookup.get(normalized.replace("-", "_"))

    async def search(self, query: str, page: int = 1, page_size: int = 25) -> SearchResponse:
        per_source_errors: dict[str, str] = {}
        per_source_warnings: dict[str, str] = {}
        aggregated_results: list[NormalizedResult] = []
        semaphore = asyncio.Semaphore(settings.connector_max_concurrency)

        connector_outcomes = await asyncio.gather(
            *(
                self._run_connector_search(
                    connector=connector,
                    query=query,
                    semaphore=semaphore,
                    failure_log_message="Primary connector search failed",
                )
                for connector in self.primary_connectors
            )
        )
        for outcome in connector_outcomes:
            connector = outcome["connector"]
            aggregated_results.extend(outcome["results"])
            if outcome["warning"]:
                per_source_warnings[connector.source_label] = outcome["warning"]
            if outcome["error"]:
                per_source_errors[connector.source_label] = outcome["error"]

        ranked_results = self._rank_results(
            query=query,
            results=aggregated_results,
            per_source_warnings=per_source_warnings,
        )
        analysis = self.analysis_service.build(
            ranked_results,
            per_source_errors=per_source_errors,
            per_source_warnings=per_source_warnings,
        )

        total_results = len(ranked_results)
        total_pages = (total_results + page_size - 1) // page_size if total_results else 0
        start = max(page - 1, 0) * page_size
        end = start + page_size

        return SearchResponse(
            query=query,
            results=ranked_results[start:end],
            analysis=analysis,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            total_results=total_results,
            per_source_errors=per_source_errors,
            per_source_warnings=per_source_warnings,
        )

    async def search_step1(
        self,
        query: str,
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[SearchResponse, list[SCNItem]]:
        response = await self.search(query=query, page=page, page_size=page_size)
        return response, self.scn_catalog_service.search(query)

    async def search_step2(self, query: str, scn_items: list[SCNItem] | None = None) -> SearchResponse:
        per_source_errors: dict[str, str] = {}
        per_source_warnings: dict[str, str] = {}
        all_results: list[NormalizedResult] = []
        semaphore = asyncio.Semaphore(settings.connector_max_concurrency)

        connector_outcomes = await asyncio.gather(
            *(
                self._run_connector_search(
                    connector=connector,
                    query=query,
                    semaphore=semaphore,
                    failure_log_message="Secondary connector search failed",
                )
                for connector in self.secondary_connectors
            )
        )
        for outcome in connector_outcomes:
            connector = outcome["connector"]
            all_results.extend(outcome["results"])
            if outcome["warning"]:
                per_source_warnings[connector.source_label] = outcome["warning"]
            if outcome["error"]:
                per_source_errors[connector.source_label] = outcome["error"]

        ranked_results = self._rank_results(
            query=query,
            results=all_results,
            per_source_warnings=per_source_warnings,
        )

        return SearchResponse(
            query=query,
            results=ranked_results,
            analysis=self.analysis_service.build(
                ranked_results,
                per_source_errors=per_source_errors,
                per_source_warnings=per_source_warnings,
            ),
            page=1,
            page_size=len(ranked_results),
            total_pages=1 if ranked_results else 0,
            total_results=len(ranked_results),
            per_source_errors=per_source_errors,
            per_source_warnings=per_source_warnings,
        )

    async def search_connector_with_scn_variants(
        self,
        connector: BaseConnector,
        query: str,
        scn_items: list[SCNItem] | None = None,
    ) -> list[NormalizedResult]:
        return await connector.search(query)

    def _rank_results(
        self,
        query: str,
        results: list[NormalizedResult],
        per_source_warnings: dict[str, str],
    ) -> list[NormalizedResult]:
        # Pass 1: connector output already includes parser-level normalization and lexical filtering.
        pass1_ranked = sorted(results, key=lambda item: (item.score, item.price_value is not None), reverse=True)

        if not settings.semantic_second_pass_enabled:
            return pass1_ranked
        if len(per_source_warnings) >= settings.semantic_warning_skip_threshold:
            return pass1_ranked

        return self._apply_semantic_second_pass(query=query, results=pass1_ranked)

    def _apply_semantic_second_pass(self, query: str, results: list[NormalizedResult]) -> list[NormalizedResult]:
        evaluated = 0
        threshold = SemanticMatchService.threshold()
        reranked: list[NormalizedResult] = []

        for result in results:
            if not self._requires_semantic_review(query=query, result=result):
                reranked.append(result)
                continue
            if evaluated >= settings.semantic_max_evaluations_per_request:
                reranked.append(result)
                continue

            try:
                comparison_text = SemanticMatchService.build_comparison_text(result)
                similarity = SemanticMatchService.compute_semantic_similarity(query, comparison_text)
                evaluated += 1
                semantic_score = int(round(similarity * 100))
                updated_score = max(result.score, semantic_score) if similarity >= threshold else max(0, result.score - 10)
                reranked.append(
                    result.model_copy(
                        update={
                            "score": updated_score,
                            "why": (
                                f"{result.why} Semantic pass-2 reviewed ambiguous match "
                                f"({semantic_score}% vs threshold {int(round(threshold * 100))}%)."
                            ).strip(),
                        }
                    )
                )
            except Exception:
                # Semantic service failures should never fail request ranking.
                reranked.append(result)

        return sorted(reranked, key=lambda item: (item.score, item.price_value is not None), reverse=True)

    @staticmethod
    def _requires_semantic_review(query: str, result: NormalizedResult) -> bool:
        min_score = settings.semantic_ambiguous_min_score
        max_score = settings.semantic_ambiguous_max_score
        in_score_band = min_score <= result.score <= max_score
        return in_score_band or not SearchService._has_exact_part_match(query, result)

    @staticmethod
    def _has_exact_part_match(query: str, result: NormalizedResult) -> bool:
        query_tokens = SearchService._normalize_model_tokens(query)
        if not query_tokens:
            return False
        for candidate in [result.sku, result.model, result.manufacturer_model]:
            normalized = SearchService._normalize_model_token(candidate)
            if normalized and normalized in query_tokens:
                return True
        return False

    @staticmethod
    def _normalize_model_tokens(value: str) -> set[str]:
        return {
            SearchService._normalize_model_token(token)
            for token in value.split()
            if SearchService._normalize_model_token(token)
        }

    @staticmethod
    def _normalize_model_token(value: str | None) -> str:
        if not value:
            return ""
        return "".join(char for char in value.lower() if char.isalnum())
