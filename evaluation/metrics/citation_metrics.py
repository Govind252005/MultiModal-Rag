"""
Citation metrics module.
Strictly separates citation evaluation into four independent dimensions (Requirement 11):
1. Citation presence: Did the generated answer contain citations?
2. Source-level citation precision: Did cited source files match expected source files?
3. Claim-level citation accuracy: Does each citation actually support the specific claim attached to it?
4. Citation completeness / claim coverage: Are claims that require evidence actually supported?

CRITICAL: Source-level citation precision is NOT called "citation accuracy".
"""

from __future__ import annotations

from typing import Dict, List, Sequence, Set


def citation_presence(cited_sources: Sequence[str]) -> bool:
    """Dimension 1: Boolean indicating whether any citation is present."""
    return bool(cited_sources)


def source_level_precision(cited_sources: Sequence[str], expected_sources: Set[str]) -> float:
    """
    Dimension 2: Source-level citation precision.
    Fraction of cited source files that appear in the expected/required source files.
    Returns 1.0 if no citations were used (nothing invalid to penalize).
    """
    if not cited_sources:
        return 1.0
    if not expected_sources:
        return 1.0
    valid_count = sum(1 for s in cited_sources if s in expected_sources)
    return valid_count / len(cited_sources)


def claim_level_accuracy(claims_checked: int, claims_supported_by_citation: int) -> float:
    """
    Dimension 3: Claim-level citation accuracy.
    Of the claims that carry citations, how many are factually supported by their cited source.
    Returns 1.0 if no cited claims were checked.
    """
    if claims_checked == 0:
        return 1.0
    return claims_supported_by_citation / claims_checked


def citation_completeness(claims_requiring_citation: int, claims_with_citation: int) -> float:
    """
    Dimension 4: Citation completeness / claim coverage.
    Fraction of factual claims that required evidence and received a citation.
    Returns 1.0 if no claims required citations.
    """
    if claims_requiring_citation == 0:
        return 1.0
    return claims_with_citation / claims_requiring_citation


def citation_recall(claims_requiring_citation: int, claims_with_valid_citation: int) -> float:
    """Valid-cited claims / claims that needed citation."""
    if claims_requiring_citation == 0:
        return 1.0
    return claims_with_valid_citation / claims_requiring_citation


def citation_f1(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return 2.0 * precision * recall / (precision + recall)


# Backward-compatible alias for existing callers
def citation_precision(citations_used: Sequence[any], citations_valid: Sequence[bool]) -> float:
    if not citations_used:
        return 1.0
    return sum(1 for v in citations_valid if v) / len(citations_used)


def citation_accuracy(citations_checked: int, citations_supporting_claim: int) -> float:
    return claim_level_accuracy(citations_checked, citations_supporting_claim)
