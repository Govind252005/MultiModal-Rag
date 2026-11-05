"""
Performance metrics calculation: percentiles, latency aggregations, and stage-wise breakdowns.
"""

from __future__ import annotations

import statistics
from typing import Dict, List, Optional, Sequence


def calculate_percentiles(values: Sequence[float]) -> Dict[str, float]:
    """Calculates min, mean, median, P50, P75, P90, P95, P99, max from raw timings."""
    if not values:
        return {}
    s = sorted(values)
    n = len(s)

    def pct(p: float) -> float:
        idx = min(n - 1, max(0, int(round(p / 100.0 * (n - 1)))))
        return round(s[idx], 2)

    return {
        "min": round(s[0], 2),
        "mean": round(statistics.mean(s), 2),
        "median": round(statistics.median(s), 2),
        "P50": pct(50),
        "P75": pct(75),
        "P90": pct(90),
        "P95": pct(95),
        "P99": pct(99),
        "max": round(s[-1], 2),
        "count": n,
    }


def aggregate_stage_latencies(
    stage_samples: Sequence[Dict[str, float]]
) -> Dict[str, Dict[str, float]]:
    """
    Given a list of dicts {stage_name: latency_ms}, computes percentiles for each stage.
    """
    by_stage: Dict[str, List[float]] = {}
    for sample in stage_samples:
        for stage, lat in sample.items():
            if lat is not None:
                by_stage.setdefault(stage, []).append(lat)

    aggregated: Dict[str, Dict[str, float]] = {}
    for stage, lats in by_stage.items():
        aggregated[stage] = calculate_percentiles(lats)

    return aggregated
