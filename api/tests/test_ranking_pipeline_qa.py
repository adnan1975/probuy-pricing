from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.models.normalized_result import NormalizedResult
from app.services.matching_service import MatchingService
from app.services.ranking_evaluation_service import RankingEvaluationService, RankingMetrics


@dataclass
class QueryMetrics:
    precision_at_k: float
    false_positive_rate: float
    exact_part_number_hit: float


def _normalize_token(value: str | None) -> str:
    if not value:
        return ""
    return "".join(char for char in value.lower() if char.isalnum())


def _is_relevant(result: NormalizedResult, relevant_tokens: set[str]) -> bool:
    fields = [result.title, result.sku, result.model, result.manufacturer_model]
    normalized = " ".join(_normalize_token(field) for field in fields if field).strip()
    return any(token in normalized for token in relevant_tokens)


def _is_non_relevant(result: NormalizedResult, non_relevant_tokens: set[str]) -> bool:
    fields = [result.title, result.sku, result.model, result.manufacturer_model]
    normalized = " ".join(_normalize_token(field) for field in fields if field).strip()
    return any(token in normalized for token in non_relevant_tokens)


def _exact_part_hit(query: str, result: NormalizedResult) -> bool:
    query_normalized = {_normalize_token(token) for token in query.split() if _normalize_token(token)}
    for candidate in [result.sku, result.model, result.manufacturer_model]:
        token = _normalize_token(candidate)
        if token and token in query_normalized:
            return True
    return False


def _make_result(candidate: dict[str, str], idx: int) -> NormalizedResult:
    return NormalizedResult(
        source="QA",
        source_type="retail",
        title=candidate["title"],
        sku=candidate.get("sku"),
        model=candidate.get("sku"),
        manufacturer_model=candidate.get("sku"),
        price_text=None,
        price_value=None,
        currency="CAD",
        brand=None,
        availability="In Stock",
        product_url=f"https://example.com/{idx}",
        image_url=None,
        confidence="Medium",
        score=0,
        why="QA candidate",
    )


def _score_baseline(query: str, candidates: list[NormalizedResult]) -> list[NormalizedResult]:
    matcher = MatchingService()
    query_tokens = matcher._tokenize(query)
    query_model_tokens = matcher._extract_model_like_tokens(query)

    scored: list[NormalizedResult] = []
    for candidate in candidates:
        title_tokens = matcher._tokenize(candidate.title)
        lexical_score, _ = matcher._compute_lexical_score(
            query_tokens=query_tokens,
            title_tokens=title_tokens,
            query_model_tokens=query_model_tokens,
            result=candidate,
        )
        scored.append(candidate.model_copy(update={"score": lexical_score, "why": "baseline lexical"}))

    return sorted(scored, key=lambda item: item.score, reverse=True)


def _score_hybrid(query: str, candidates: list[NormalizedResult]) -> list[NormalizedResult]:
    return MatchingService().apply(query, candidates)


def _evaluate_query(
    query: str,
    ranked_results: list[NormalizedResult],
    relevant_tokens: set[str],
    non_relevant_tokens: set[str],
    k: int,
) -> QueryMetrics:
    top_k = ranked_results[:k]
    relevant_hits = sum(1 for result in top_k if _is_relevant(result, relevant_tokens))
    non_relevant_hits = sum(1 for result in top_k if _is_non_relevant(result, non_relevant_tokens))
    precision_at_k = relevant_hits / max(1, len(top_k))
    false_positive_rate = non_relevant_hits / max(1, len(top_k))
    exact_part_number_hit = 1.0 if top_k and _exact_part_hit(query, top_k[0]) else 0.0
    return QueryMetrics(precision_at_k, false_positive_rate, exact_part_number_hit)


def _aggregate(metrics: list[QueryMetrics]) -> RankingMetrics:
    n = max(1, len(metrics))
    return RankingMetrics(
        precision_at_k=sum(m.precision_at_k for m in metrics) / n,
        false_positive_rate=sum(m.false_positive_rate for m in metrics) / n,
        exact_part_number_hit_rate=sum(m.exact_part_number_hit for m in metrics) / n,
    )


def test_hybrid_pipeline_beats_baseline_on_qa_fixture():
    fixture_path = Path(__file__).parent / "fixtures" / "ranking_qa_dataset.json"
    cases = json.loads(fixture_path.read_text())
    k = 2

    baseline_query_metrics: list[QueryMetrics] = []
    hybrid_query_metrics: list[QueryMetrics] = []

    for case in cases:
        candidates = [_make_result(candidate, idx) for idx, candidate in enumerate(case["candidates"])]
        relevant = {_normalize_token(token) for token in case["relevant"]}
        non_relevant = {_normalize_token(token) for token in case["non_relevant"]}

        baseline_ranked = _score_baseline(case["query"], candidates)
        hybrid_ranked = _score_hybrid(case["query"], candidates)

        baseline_query_metrics.append(_evaluate_query(case["query"], baseline_ranked, relevant, non_relevant, k))
        hybrid_query_metrics.append(_evaluate_query(case["query"], hybrid_ranked, relevant, non_relevant, k))

    baseline = _aggregate(baseline_query_metrics)
    hybrid = _aggregate(hybrid_query_metrics)

    assert hybrid.precision_at_k >= baseline.precision_at_k
    assert hybrid.false_positive_rate <= baseline.false_positive_rate
    assert hybrid.exact_part_number_hit_rate >= baseline.exact_part_number_hit_rate


def test_rollout_gate_requires_minimum_precision_improvement_and_baseline_fallback():
    baseline = RankingMetrics(precision_at_k=0.55, false_positive_rate=0.30, exact_part_number_hit_rate=0.66)
    underperforming_hybrid = RankingMetrics(precision_at_k=0.57, false_positive_rate=0.28, exact_part_number_hit_rate=0.66)
    strong_hybrid = RankingMetrics(precision_at_k=0.66, false_positive_rate=0.20, exact_part_number_hit_rate=1.0)

    assert not RankingEvaluationService.should_rollout_hybrid(
        baseline=baseline,
        hybrid=underperforming_hybrid,
        min_precision_improvement=0.03,
    )
    assert RankingEvaluationService.should_rollout_hybrid(
        baseline=baseline,
        hybrid=strong_hybrid,
        min_precision_improvement=0.03,
    )
