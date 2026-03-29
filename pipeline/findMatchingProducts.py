from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1] / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.connectors.canadiantire_connector import CanadianTireConnector
from app.connectors.homedepot_connector import HomeDepotConnector
from app.connectors.kms_connector import KMSConnector
from app.connectors.scn_connector import SCNConnector
from app.connectors.whitecap_connector import WhiteCapConnector
from app.models.normalized_result import NormalizedResult
from app.services.search_service import SearchService


def _normalize(value: str | None) -> str:
    return " ".join((value or "").lower().split())


def _build_queries(scn_result: NormalizedResult) -> list[str]:
    """Search model first, then description, then manufacturer."""
    candidates = [
        (scn_result.sku or "").strip(),
        (scn_result.title or "").strip(),
        (scn_result.brand or "").strip(),
    ]
    queries: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = _normalize(candidate)
        if not normalized:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        queries.append(candidate)
    return queries


def _tokens(value: str | None) -> set[str]:
    return {token for token in _normalize(value).replace("/", " ").replace("-", " ").split() if token}


def _match_score(scn_result: NormalizedResult, connector_result: NormalizedResult) -> int:
    score = 0

    scn_sku = _normalize(scn_result.sku)
    target_sku = _normalize(connector_result.sku)
    target_title = _normalize(connector_result.title)

    if scn_sku:
        if target_sku and scn_sku == target_sku:
            score += 90
        elif scn_sku in target_title:
            score += 80

    scn_brand = _normalize(scn_result.brand)
    target_brand = _normalize(connector_result.brand)
    if scn_brand and target_brand and scn_brand == target_brand:
        score += 10

    scn_tokens = _tokens(scn_result.title)
    target_tokens = _tokens(connector_result.title)
    if scn_tokens and target_tokens:
        overlap = len(scn_tokens.intersection(target_tokens))
        score += min(20, overlap * 2)

    return score


async def find_first_match(min_score: int = 80, limit: int | None = None) -> int:
    scn_connector = SCNConnector()
    search_service = SearchService(
        connectors=[
            WhiteCapConnector(),
            KMSConnector(),
            CanadianTireConnector(),
            HomeDepotConnector(),
        ]
    )

    scn_results = await scn_connector.search("")
    if not scn_results:
        warning = getattr(scn_connector, "last_warning", None)
        print("No SCN products available to scan.")
        if warning:
            print(f"SCN warning: {warning}")
        return 1

    checked = 0
    for scn_result in scn_results:
        if limit is not None and checked >= limit:
            break

        queries = _build_queries(scn_result)
        if not queries:
            continue

        checked += 1
        print(f"[{checked}/{len(scn_results)}] Checking SCN product: {scn_result.sku or scn_result.title}")
        print(f"  Query order: {queries}")

        for query in queries:
            connector_results, errors, warnings = await search_service.collect_live_results(query)

            for source, error in errors.items():
                print(f"  - {source} error (query='{query}'): {error}")
            for source, warning in warnings.items():
                print(f"  - {source} warning (query='{query}'): {warning}")

            ranked_matches: list[tuple[int, NormalizedResult]] = []
            for connector_result in connector_results:
                score = _match_score(scn_result, connector_result)
                if score >= min_score:
                    ranked_matches.append((score, connector_result))

            if ranked_matches:
                ranked_matches.sort(key=lambda item: item[0], reverse=True)
                best_score, best_match = ranked_matches[0]
                print("\nMatch found. Stopping scan.")
                print(f"Matched using query: {query}")
                print(f"SCN title: {scn_result.title}")
                print(f"SCN sku/model: {scn_result.sku}")
                print(f"SCN brand: {scn_result.brand}")
                print(f"Matched source: {best_match.source}")
                print(f"Matched title: {best_match.title}")
                print(f"Matched sku: {best_match.sku}")
                print(f"Matched brand: {best_match.brand}")
                print(f"Matched URL: {best_match.product_url}")
                print(f"Match score: {best_score}")
                return 0

    print("No cross-connector product match found.")
    return 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Scan SCN catalog items and run all other connectors until the first product match is found."
        )
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=80,
        help="Minimum internal match score required to consider a result a match. Default: 80",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional cap on number of SCN products to scan.",
    )

    args = parser.parse_args()
    exit_code = asyncio.run(find_first_match(min_score=args.min_score, limit=args.limit))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
