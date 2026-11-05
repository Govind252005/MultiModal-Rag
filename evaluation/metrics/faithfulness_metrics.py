"""
Faithfulness metrics module.
Calculates semantic grounding and unfaithful hallucination rates.

CRITICAL (Requirement 10):
`faithfulness_warning_rate` is kept strictly as an internal diagnostic flag,
NOT as the primary research faithfulness metric.
"""

from __future__ import annotations

from typing import Dict, List, Sequence


def semantic_faithfulness_score(
    total_claims: int,
    supported_claims: int
) -> float:
    """
    Research-grade semantic faithfulness:
    Proportion of verifiable claims in generated response that are grounded
    in the retrieved evidence. Returns 1.0 if answer contains no empirical claims.
    """
    if total_claims == 0:
        return 1.0
    return supported_claims / total_claims


def hallucination_rate(
    total_claims: int,
    unsupported_claims: int
) -> float:
    """Proportion of claims that cannot be grounded in retrieved evidence."""
    if total_claims == 0:
        return 0.0
    return unsupported_claims / total_claims


def diagnostic_warning_rate(warning_flags: Sequence[bool]) -> float:
    """
    Internal diagnostic metric: proportion of backend responses flagged with
    faithfulness heuristic warnings.
    """
    if not warning_flags:
        return 0.0
    return sum(1 for w in warning_flags if w) / len(warning_flags)
