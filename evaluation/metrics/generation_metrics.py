"""
Generation metrics for RAG answers.
Includes token overlap, exact match, ROUGE-L, length ratio, and abstention accuracy.
"""

from __future__ import annotations

import re
from typing import Dict, List, Sequence, Set


def normalize_answer(text: str) -> str:
    """Lowercases, strips punctuation and extra whitespace."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def exact_match(predicted: str, reference: str) -> float:
    return 1.0 if normalize_answer(predicted) == normalize_answer(reference) else 0.0


def token_overlap_f1(predicted: str, reference: str) -> Dict[str, float]:
    """Token-level precision, recall, and F1."""
    pred_tokens = normalize_answer(predicted).split()
    ref_tokens = normalize_answer(reference).split()

    if not pred_tokens and not ref_tokens:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    if not pred_tokens or not ref_tokens:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    ref_counts: Dict[str, int] = {}
    for t in ref_tokens:
        ref_counts[t] = ref_counts.get(t, 0) + 1

    overlap = 0
    rem = dict(ref_counts)
    for t in pred_tokens:
        if rem.get(t, 0) > 0:
            overlap += 1
            rem[t] -= 1

    precision = overlap / len(pred_tokens)
    recall = overlap / len(ref_tokens)
    f1 = (2.0 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    return {"precision": precision, "recall": recall, "f1": f1}


def longest_common_subsequence(seq1: Sequence[str], seq2: Sequence[str]) -> int:
    m, n = len(seq1), len(seq2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m):
        for j in range(n):
            if seq1[i] == seq2[j]:
                dp[i + 1][j + 1] = dp[i][j] + 1
            else:
                dp[i + 1][j + 1] = max(dp[i + 1][j], dp[i][j + 1])
    return dp[m][n]


def rouge_l_score(predicted: str, reference: str) -> Dict[str, float]:
    """ROUGE-L based on Longest Common Subsequence of word tokens."""
    pred_tokens = normalize_answer(predicted).split()
    ref_tokens = normalize_answer(reference).split()

    if not pred_tokens and not ref_tokens:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    if not pred_tokens or not ref_tokens:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    lcs = longest_common_subsequence(pred_tokens, ref_tokens)
    p = lcs / len(pred_tokens)
    r = lcs / len(ref_tokens)
    f1 = (2.0 * p * r / (p + r)) if (p + r) > 0 else 0.0
    return {"precision": p, "recall": r, "f1": f1}


ABSTENTION_PATTERNS = [
    "i could not find",
    "i couldn't find",
    "could not find",
    "couldn't find",
    "not found in the provided",
    "not present in the provided",
    "not available in the provided",
    "not mentioned in the provided",
    "not contained in the provided",
    "not enough information",
    "insufficient information",
    "cannot answer from the provided",
    "can't answer from the provided",
    "unable to answer from the provided",
    "provided documents do not mention",
    "no information provided",
    "does not mention",
]


def is_abstention(text: str) -> bool:
    """Checks whether the generated text indicates an explicit refusal/abstention."""
    lowered = text.lower()
    return any(p in lowered for p in ABSTENTION_PATTERNS)


def abstention_accuracy(unanswerable_total: int, correctly_abstained: int) -> float:
    if unanswerable_total == 0:
        return 1.0
    return correctly_abstained / unanswerable_total
