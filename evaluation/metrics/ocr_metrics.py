"""
OCR quality metrics: Character Error Rate (CER) and Word Error Rate (WER).
Uses exact Levenshtein distance on characters and tokenized words.
"""

from __future__ import annotations

from typing import Dict, List, Sequence


def levenshtein_distance(seq1: Sequence[any], seq2: Sequence[any]) -> int:
    """Computes exact edit distance between two sequences (chars or words)."""
    m, n = len(seq1), len(seq2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if seq1[i - 1] == seq2[j - 1]:
                cost = 0
            else:
                cost = 1
            dp[i][j] = min(
                dp[i - 1][j] + 1,       # deletion
                dp[i][j - 1] + 1,       # insertion
                dp[i - 1][j - 1] + cost # substitution
            )
    return dp[m][n]


def character_error_rate(reference: str, hypothesis: str) -> float:
    """
    CER = Levenshtein_distance(reference_chars, hypothesis_chars) / len(reference_chars).
    Returns 0.0 if reference is empty and hypothesis is empty.
    """
    ref_chars = list(reference)
    hyp_chars = list(hypothesis)
    if not ref_chars:
        return 0.0 if not hyp_chars else 1.0
    dist = levenshtein_distance(ref_chars, hyp_chars)
    return dist / len(ref_chars)


def word_error_rate(reference: str, hypothesis: str) -> float:
    """
    WER = Levenshtein_distance(reference_words, hypothesis_words) / len(reference_words).
    Returns 0.0 if reference is empty and hypothesis is empty.
    """
    ref_words = reference.split()
    hyp_words = hypothesis.split()
    if not ref_words:
        return 0.0 if not hyp_words else 1.0
    dist = levenshtein_distance(ref_words, hyp_words)
    return dist / len(ref_words)


def calculate_ocr_metrics_suite(
    pairs: Sequence[tuple[str, str]]
) -> Dict[str, float]:
    """
    Takes a sequence of (ground_truth, hypothesis) pairs and calculates
    mean CER and mean WER.
    """
    if not pairs:
        return {"mean_cer": 0.0, "mean_wer": 0.0, "samples": 0}
    total_cer = sum(character_error_rate(ref, hyp) for ref, hyp in pairs)
    total_wer = sum(word_error_rate(ref, hyp) for ref, hyp in pairs)
    n = len(pairs)
    return {
        "mean_cer": round(total_cer / n, 4),
        "mean_wer": round(total_wer / n, 4),
        "samples": n,
    }
