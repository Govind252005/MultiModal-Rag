"""
Advanced ranking metrics for retrieval evaluation.
"""

from __future__ import annotations

import math
from typing import Dict, List, Sequence, Set


def reciprocal_rank(retrieved_ids: Sequence[str], relevant_ids: Set[str]) -> float:
    for rank, item_id in enumerate(retrieved_ids, start=1):
        if item_id in relevant_ids:
            return 1.0 / rank
    return 0.0


def r_precision(retrieved_ids: Sequence[str], relevant_ids: Set[str]) -> float:
    """Precision at rank R, where R is the total number of relevant documents."""
    r = len(relevant_ids)
    if r == 0:
        return 1.0
    top_r = retrieved_ids[:r]
    hits = sum(1 for item in top_r if item in relevant_ids)
    return hits / r


def first_relevant_rank(retrieved_ids: Sequence[str], relevant_ids: Set[str]) -> int:
    """Returns the 1-based rank of the first relevant document, or -1 if none."""
    for rank, item_id in enumerate(retrieved_ids, start=1):
        if item_id in relevant_ids:
            return rank
    return -1


def rank_biased_precision(
    retrieved_ids: Sequence[str], relevant_ids: Set[str], p: float = 0.8
) -> float:
    """Rank-Biased Precision (RBP) modeling a user browsing down with persistence parameter p."""
    if not relevant_ids:
        return 1.0
    score = 0.0
    for rank, item_id in enumerate(retrieved_ids, start=1):
        if item_id in relevant_ids:
            score += (1.0 - p) * (p ** (rank - 1))
    return score
