from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RankingMetrics:
    precision_at_k: float
    false_positive_rate: float
    exact_part_number_hit_rate: float


class RankingEvaluationService:
    @staticmethod
    def should_rollout_hybrid(
        baseline: RankingMetrics,
        hybrid: RankingMetrics,
        min_precision_improvement: float,
    ) -> bool:
        precision_gain = hybrid.precision_at_k - baseline.precision_at_k
        has_precision_gain = precision_gain >= min_precision_improvement
        has_fpr_improvement = hybrid.false_positive_rate <= baseline.false_positive_rate
        has_exact_part_hit_improvement = (
            hybrid.exact_part_number_hit_rate >= baseline.exact_part_number_hit_rate
        )
        return has_precision_gain and has_fpr_improvement and has_exact_part_hit_improvement
