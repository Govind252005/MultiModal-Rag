"""
Retrieval quality metrics.
All functions take plain Python collections — no backend dependencies —
so they can be unit-tested in isolation and reused across all evaluators.

Covers:
- Precision@K (K=1, 3, 5, 10)
- Recall@K (K=1, 3, 5, 10)
- Retrieval F1@K (K=1, 3, 5, 10)
- Hit@K (K=5, 10)
- Mean Reciprocal Rank (MRR)
- Mean Average Precision (MAP)
- Normalized Discounted Cumulative Gain (nDCG@K)
- ROC-AUC and PR-AUC with explicit binary classification task definitions.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple


def _unique_ranked_ids(retrieved_ids: Sequence[str]) -> List[str]:
    """Deduplicate ranked IDs while preserving first-occurrence order."""
    seen: Set[str] = set()
    unique: List[str] = []
    for item_id in retrieved_ids:
        if item_id not in seen:
            seen.add(item_id)
            unique.append(item_id)
    return unique


def precision_recall_f1(
    true_positive: int, false_positive: int, false_negative: int
) -> Dict[str, float]:
    """Return binary-classification precision, recall, and F1.

    Kept here for compatibility with the original evaluation metric API.
    Retrieval ranking metrics below remain separate from answer-quality
    metrics, but existing callers can continue importing this helper.
    """
    precision_denominator = true_positive + false_positive
    recall_denominator = true_positive + false_negative
    precision = true_positive / precision_denominator if precision_denominator else 0.0
    recall = true_positive / recall_denominator if recall_denominator else 0.0
    f1 = (2.0 * precision * recall / (precision + recall)) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def token_f1(predicted: str, reference: str) -> Dict[str, float]:
    """Compatibility wrapper for the canonical answer token-overlap metric."""
    from evaluation.metrics.generation_metrics import token_overlap_f1

    return token_overlap_f1(predicted, reference)


def exact_match(predicted: str, reference: str) -> float:
    """Compatibility wrapper for normalized answer exact match."""
    from evaluation.metrics.generation_metrics import exact_match as _exact_match

    return _exact_match(predicted, reference)


def roc_curve(scores: Sequence[float], labels: Sequence[int]) -> Dict[str, Any]:
    """Compatibility wrapper exposing the historical ``auc`` field."""
    result = compute_roc_pr_auc(scores, labels)
    return {
        "applicable": result["applicable"],
        "auc": result.get("roc_auc"),
        "fpr": result.get("fpr"),
        "tpr": result.get("tpr"),
        "reason": result.get("reason"),
    }


def recall_at_k(retrieved_ids: Sequence[str], relevant_ids: Set[str], k: int) -> float:
    """Relevant items retrieved in top K / total relevant.
    Returns 1.0 if there are no relevant items (nothing to miss)."""
    if not relevant_ids:
        return 1.0
    top_k = set(_unique_ranked_ids(retrieved_ids)[:k])
    return len(top_k & relevant_ids) / len(relevant_ids)


def precision_at_k(retrieved_ids: Sequence[str], relevant_ids: Set[str], k: int) -> float:
    """Relevant items retrieved in top K / K.
    Returns 0.0 if fewer than K items were returned or top_k is empty."""
    top_k = _unique_ranked_ids(retrieved_ids)[:k]
    if not top_k:
        return 0.0
    hits = sum(1 for i in top_k if i in relevant_ids)
    return hits / len(top_k)


def hit_rate_at_k(retrieved_ids: Sequence[str], relevant_ids: Set[str], k: int) -> float:
    """1.0 if at least one relevant item appears in top K, else 0.0."""
    if not relevant_ids:
        return 1.0
    return 1.0 if set(_unique_ranked_ids(retrieved_ids)[:k]) & relevant_ids else 0.0


def f1_at_k(precision: float, recall: float) -> float:
    """Harmonic mean of precision@k and recall@k."""
    if precision + recall == 0.0:
        return 0.0
    return 2.0 * (precision * recall) / (precision + recall)


def reciprocal_rank(retrieved_ids: Sequence[str], relevant_ids: Set[str]) -> float:
    """1 / rank of the first relevant result (1-indexed); 0.0 if none found."""
    for rank, item_id in enumerate(_unique_ranked_ids(retrieved_ids), start=1):
        if item_id in relevant_ids:
            return 1.0 / rank
    return 0.0


def mrr(all_retrieved: Sequence[Sequence[str]], all_relevant: Sequence[Set[str]]) -> float:
    """Mean Reciprocal Rank across a sequence of queries."""
    if len(all_retrieved) != len(all_relevant):
        raise ValueError("retrieved and relevant query collections must have equal length")
    if not all_retrieved:
        return 0.0
    scores = [reciprocal_rank(r, rel) for r, rel in zip(all_retrieved, all_relevant)]
    return sum(scores) / len(scores)


def average_precision(retrieved_ids: Sequence[str], relevant_ids: Set[str]) -> float:
    """Average Precision for a single query."""
    if not relevant_ids:
        return 1.0
    hits = 0
    precisions = []
    for rank, item_id in enumerate(_unique_ranked_ids(retrieved_ids), start=1):
        if item_id in relevant_ids:
            hits += 1
            precisions.append(hits / rank)
    if not precisions:
        return 0.0
    return sum(precisions) / len(relevant_ids)


def mean_average_precision(
    all_retrieved: Sequence[Sequence[str]], all_relevant: Sequence[Set[str]]
) -> float:
    """Mean Average Precision across multiple queries."""
    if len(all_retrieved) != len(all_relevant):
        raise ValueError("retrieved and relevant query collections must have equal length")
    if not all_retrieved:
        return 0.0
    scores = [average_precision(r, rel) for r, rel in zip(all_retrieved, all_relevant)]
    return sum(scores) / len(scores)


def dcg_at_k(relevances: Sequence[float], k: int) -> float:
    """Discounted Cumulative Gain at rank K."""
    total = 0.0
    for i, rel in enumerate(relevances[:k], start=1):
        total += rel / math.log2(i + 1)
    return total


def ndcg_at_k(
    retrieved_ids: Sequence[str],
    relevance_by_id: Dict[str, float],
    k: int,
) -> float:
    """Normalized DCG@K.
    `relevance_by_id` maps item id -> graded relevance (1.0 for binary relevance).
    Returns 1.0 when there are no relevant items in ground truth."""
    graded = [relevance_by_id.get(i, 0.0) for i in _unique_ranked_ids(retrieved_ids)[:k]]
    actual = dcg_at_k(graded, k)
    ideal_order = sorted(relevance_by_id.values(), reverse=True)
    ideal = dcg_at_k(ideal_order, k)
    if ideal == 0.0:
        return 1.0
    return actual / ideal


def calculate_retrieval_suite(
    retrieved_ids: Sequence[str],
    relevant_ids: Set[str],
    ks: Sequence[int] = (1, 3, 5, 10),
) -> Dict[str, float]:
    """Calculates full per-query retrieval metrics for given cutoffs K."""
    res: Dict[str, float] = {}
    rel_map = {rid: 1.0 for rid in relevant_ids}

    for k in ks:
        p = precision_at_k(retrieved_ids, relevant_ids, k)
        r = recall_at_k(retrieved_ids, relevant_ids, k)
        res[f"precision@{k}"] = p
        res[f"recall@{k}"] = r
        res[f"f1@{k}"] = f1_at_k(p, r)
        res[f"hit@{k}"] = hit_rate_at_k(retrieved_ids, relevant_ids, k)
        res[f"ndcg@{k}"] = ndcg_at_k(retrieved_ids, rel_map, k)

    res["reciprocal_rank"] = reciprocal_rank(retrieved_ids, relevant_ids)
    res["average_precision"] = average_precision(retrieved_ids, relevant_ids)
    return res


# ------------------------------------------------------------------
# Strictly defined ROC-AUC & PR-AUC classification task
# ------------------------------------------------------------------

def compute_roc_pr_auc(
    scores: Sequence[float],
    labels: Sequence[int],
    task_description: str = (
        "Binary classification task: Given candidate chunks with continuous relevance scores "
        "(e.g., cross-encoder or fusion score), predict binary relevance ground truth (1=relevant, 0=non-relevant)."
    )
) -> Dict[str, Any]:
    """
    Computes ROC-AUC and PR-AUC for candidate retrieval scoring.
    
    POSITIVE CLASS: 1 (chunk is relevant according to ground truth)
    NEGATIVE CLASS: 0 (chunk is not in ground truth relevant set)
    SCORE: continuous relevance score where higher indicates predicted relevance.
    """
    if len(scores) != len(labels):
        raise ValueError(f"Length mismatch: {len(scores)} scores vs {len(labels)} labels")
    if any(label not in (0, 1) for label in labels):
        raise ValueError("labels must contain only binary values 0 and 1")

    # Group equal scores before adding curve points so tied candidates do not
    # produce an order-dependent ROC/PR result.
    pairs = sorted(zip(scores, labels), key=lambda x: x[0], reverse=True)
    n_pos = sum(labels)
    n_neg = len(labels) - n_pos

    if n_pos == 0 or n_neg == 0:
        return {
            "applicable": False,
            "reason": f"Only one class present in evaluated candidate set (pos={n_pos}, neg={n_neg}). "
                      f"ROC-AUC / PR-AUC mathematically undefined without both classes.",
            "task_definition": task_description,
            "roc_auc": None,
            "pr_auc": None,
        }

    # ROC curve points
    fpr_points = [0.0]
    tpr_points = [0.0]
    tp = fp = 0
    i = 0
    while i < len(pairs):
        score = pairs[i][0]
        while i < len(pairs) and pairs[i][0] == score:
            if pairs[i][1] == 1:
                tp += 1
            else:
                fp += 1
            i += 1
        fpr_points.append(fp / n_neg)
        tpr_points.append(tp / n_pos)

    # Trapezoidal ROC AUC
    roc_auc = 0.0
    for i in range(1, len(fpr_points)):
        w = fpr_points[i] - fpr_points[i - 1]
        h = (tpr_points[i] + tpr_points[i - 1]) / 2.0
        roc_auc += w * h

    # PR curve points
    recall_points = [0.0]
    precision_points = [1.0]
    tp = fp = 0
    i = 0
    while i < len(pairs):
        score = pairs[i][0]
        while i < len(pairs) and pairs[i][0] == score:
            if pairs[i][1] == 1:
                tp += 1
            else:
                fp += 1
            i += 1
        r = tp / n_pos
        p = tp / (tp + fp) if (tp + fp) > 0 else 1.0
        recall_points.append(r)
        precision_points.append(p)

    # Trapezoidal PR AUC
    pr_auc = 0.0
    for i in range(1, len(recall_points)):
        w = recall_points[i] - recall_points[i - 1]
        h = (precision_points[i] + precision_points[i - 1]) / 2.0
        pr_auc += w * h

    return {
        "applicable": True,
        "task_definition": task_description,
        "roc_auc": round(roc_auc, 4),
        "pr_auc": round(pr_auc, 4),
        "fpr": fpr_points,
        "tpr": tpr_points,
        "precision_curve": precision_points,
        "recall_curve": recall_points,
        "num_positive": n_pos,
        "num_negative": n_neg,
    }
