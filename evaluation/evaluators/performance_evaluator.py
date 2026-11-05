"""
Performance Evaluator module.
Aggregates stage-wise latencies and percentiles without estimating or fabricating.
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence
from evaluation.metrics.performance_metrics import (
    aggregate_stage_latencies,
    calculate_percentiles,
)


class PerformanceEvaluator:
    """Evaluates latency percentiles across query stages."""

    def evaluate_performance(
        self,
        total_latencies: Sequence[float],
        stage_samples: Sequence[Dict[str, float]],
    ) -> Dict[str, Any]:
        if not total_latencies:
            return {
                "query_latency_p50_ms": None,
                "query_latency_p95_ms": None,
                "stages": {},
            }

        overall_pct = calculate_percentiles(total_latencies)
        stages_pct = aggregate_stage_latencies(stage_samples)

        return {
            "query_latency_min_ms": overall_pct.get("min"),
            "query_latency_mean_ms": overall_pct.get("mean"),
            "query_latency_p50_ms": overall_pct.get("P50"),
            "query_latency_p75_ms": overall_pct.get("P75"),
            "query_latency_p90_ms": overall_pct.get("P90"),
            "query_latency_p95_ms": overall_pct.get("P95"),
            "query_latency_p99_ms": overall_pct.get("P99"),
            "query_latency_max_ms": overall_pct.get("max"),
            "stages": stages_pct,
        }
