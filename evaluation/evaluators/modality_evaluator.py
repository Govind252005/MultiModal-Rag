"""
Modality and Cross-Modal Evaluator module (Requirements 8 & 9).
Evaluates retrieval across modality categories:
- document text
- image
- scanned / OCR
- audio
- cross-modal
"""

from __future__ import annotations

import statistics
from typing import Any, Dict, List, Sequence, Set
from evaluation.metrics.retrieval_metrics import calculate_retrieval_suite, mrr


class ModalityEvaluator:
    """Evaluates retrieval quality segmented by modality and cross-modal queries."""

    def evaluate_modalities(
        self,
        question_results: Sequence[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        question_results: List of dicts with:
          - modality: str
          - retrieved_ids: List[str]
          - relevant_ids: Set[str]
        """
        by_modality: Dict[str, List[Dict[str, Any]]] = {}

        for item in question_results:
            mod = item.get("modality", "text").lower()
            by_modality.setdefault(mod, []).append(item)

        modality_metrics: Dict[str, Any] = {}

        for mod, items in by_modality.items():
            all_retrieved = []
            all_relevant = []
            p5_vals = []
            r5_vals = []
            f1_vals = []
            ndcg5_vals = []
            hit5_vals = []

            for q in items:
                ret_ids = q.get("retrieved_ids") or []
                rel_ids = set(q.get("relevant_ids") or [])
                if rel_ids:
                    all_retrieved.append(ret_ids)
                    all_relevant.append(rel_ids)
                    suite = calculate_retrieval_suite(ret_ids, rel_ids, ks=(1, 3, 5, 10))
                    p5_vals.append(suite.get("precision@5", 0.0))
                    r5_vals.append(suite.get("recall@5", 0.0))
                    f1_vals.append(suite.get("f1@5", 0.0))
                    ndcg5_vals.append(suite.get("ndcg@5", 0.0))
                    hit5_vals.append(suite.get("hit@5", 0.0))

            if all_relevant:
                mrr_score = mrr(all_retrieved, all_relevant)
                modality_metrics[mod] = {
                    "count": len(items),
                    "evaluated_queries": len(all_relevant),
                    "precision@5": round(statistics.mean(p5_vals), 4) if p5_vals else 0.0,
                    "recall@5": round(statistics.mean(r5_vals), 4) if r5_vals else 0.0,
                    "f1@5": round(statistics.mean(f1_vals), 4) if f1_vals else 0.0,
                    "ndcg@5": round(statistics.mean(ndcg5_vals), 4) if ndcg5_vals else 0.0,
                    "hit@5": round(statistics.mean(hit5_vals), 4) if hit5_vals else 0.0,
                    "mrr": round(mrr_score, 4),
                }

        # Check balance note
        dataset_modalities = list(by_modality.keys())
        is_balanced = len(dataset_modalities) >= 4

        return {
            "status": "COMPLETED" if modality_metrics else "NOT_RUN",
            "modalities": modality_metrics,
            "represented_modalities": dataset_modalities,
            "is_balanced": is_balanced,
            "balance_note": (
                "Dataset contains balanced multi-modal representation."
                if is_balanced
                else f"Dataset currently covers {dataset_modalities}; audio/OCR benchmark expansion pending."
            ),
        }
