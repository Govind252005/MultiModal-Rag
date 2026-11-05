"""
Statistical evaluation utilities: bootstrap confidence intervals, variance, standard errors.
"""

from __future__ import annotations

import math
import random
import statistics
from typing import Dict, List, Optional, Sequence, Tuple


def mean_and_std(values: Sequence[float]) -> Dict[str, float]:
    if not values:
        return {"mean": 0.0, "std": 0.0, "n": 0}
    n = len(values)
    m = statistics.mean(values)
    s = statistics.stdev(values) if n > 1 else 0.0
    return {"mean": round(m, 4), "std": round(s, 4), "n": n}


def bootstrap_ci(
    values: Sequence[float],
    n_bootstraps: int = 1000,
    confidence_level: float = 0.95,
    seed: int = 42,
) -> Tuple[float, float]:
    """
    Computes non-parametric bootstrap confidence interval for the mean.
    Returns (lower_bound, upper_bound).
    """
    if not values:
        return 0.0, 0.0
    if len(values) == 1:
        return values[0], values[0]

    rng = random.Random(seed)
    n = len(values)
    boot_means = []

    for _ in range(n_bootstraps):
        sample = [rng.choice(values) for _ in range(n)]
        boot_means.append(sum(sample) / n)

    boot_means.sort()
    alpha = (1.0 - confidence_level) / 2.0
    low_idx = int(alpha * n_bootstraps)
    high_idx = int((1.0 - alpha) * n_bootstraps)
    low_idx = max(0, min(n_bootstraps - 1, low_idx))
    high_idx = max(0, min(n_bootstraps - 1, high_idx))

    return round(boot_means[low_idx], 4), round(boot_means[high_idx], 4)
