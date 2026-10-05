"""
Retrieval Evaluator module.
Computes P@K, R@K, F1@K, Hit@K, MRR, MAP, nDCG@K, and ROC/PR-AUC.
"""

from __future__ import annotations

import statistics
from typing import Any, Dict, List, Optional, Sequence, Set
from evaluation.metrics.retrieval_metrics import (
    calculate_retrieval_suite,
    compute_roc_pr_auc,
    mean_average_precision,
    mrr,
)


class RetrievalEvaluator:
    """Evaluates retrieval quality over evaluated questions."""

    def __init__(self, ks: Sequence[int] = (1, 3, 5, 10)):
        self.ks = tuple(ks)

    def evaluate_retrieval(
        self,
        retrieved_results: Sequence[Dict[str, Any]],
        candidate_scores: Optional[Sequence[float]] = None,
        candidate_labels: Optional[Sequence[int]] = None,
    ) -> Dict[str, Any]:
        """
        retrieved_results: List of dicts with:
          - 'question_id'
          - 'retrieved_ids': List[str]
          - 'relevant_ids': Set[str]
        """
        if not retrieved_results:
            return {"status": "NOT_RUN", "reason": "No retrieval results to score"}

        all_retrieved: List[List[str]] = []
        all_relevant: List[Set[str]] = []
        per_query_metrics: List[Dict[str, Any]] = []

        by_metric: Dict[str, List[float]] = {}

        for item in retrieved_results:
            ret_ids = item.get("retrieved_ids") or []
            rel_ids = set(item.get("relevant_ids") or [])

            if rel_ids:
                all_retrieved.append(ret_ids)
                all_relevant.append(rel_ids)

                q_suite = calculate_retrieval_suite(ret_ids, rel_ids, self.ks)
                per_query_metrics.append({"question_id": item.get("question_id"), **q_suite})

                for m_name, val in q_suite.items():
                    by_metric.setdefault(m_name, []).append(val)

        if not all_relevant:
            return {"status": "NOT_RUN", "reason": "No ground truth relevant chunks found in evaluated items"}

        aggregates: Dict[str, Any] = {}
        for m_name, vals in by_metric.items():
            aggregates[m_name] = round(statistics.mean(vals), 4)

        aggregates["mrr"] = round(mrr(all_retrieved, all_relevant), 4)
        aggregates["map"] = round(mean_average_precision(all_retrieved, all_relevant), 4)
        aggregates["evaluated_queries"] = len(all_relevant)

        # ROC / PR AUC if candidate scores are present
        if candidate_scores and candidate_labels and len(candidate_scores) == len(candidate_labels):
            auc_res = compute_roc_pr_auc(candidate_scores, candidate_labels)
            aggregates["roc_auc"] = auc_res.get("roc_auc")
            aggregates["pr_auc"] = auc_res.get("pr_auc")
            aggregates["roc_pr_details"] = auc_res

        return aggregates
