"""
Ablation Evaluator module (Requirement 14).
Runs systematic baseline ablations (B1 to B5) and component ablations:
- B1 = BM25 only
- B2 = Dense only
- B3 = Dense + BM25
- B4 = Dense + BM25 + CLIP
- B4' = Dense + BM25 + CLIP + RRF
- B5 = Dense + BM25 + CLIP + RRF + Cross Encoder
- Component ablations: B5 - Dense, B5 - BM25, B5 - CLIP, B5 - RRF, B5 - Cross Encoder
"""

from __future__ import annotations

import statistics
import time
from typing import Any, Dict, List, Optional, Sequence, Set
from evaluation.metrics.retrieval_metrics import calculate_retrieval_suite, mean_average_precision, mrr
from evaluation.schemas.experiment_schema import AblationConfig, ExperimentResult


class AblationEvaluator:
    """Manages baseline and component ablation experiments."""

    def __init__(self):
        self.ablation_definitions: List[AblationConfig] = [
            AblationConfig("B1", "BM25 only", "Lexical keyword search only", use_dense=False, use_bm25=True, use_clip=False, use_rrf=False, use_cross_encoder=False),
            AblationConfig("B2", "Dense only", "Dense semantic vector search only", use_dense=True, use_bm25=False, use_clip=False, use_rrf=False, use_cross_encoder=False),
            AblationConfig("B3", "Dense + BM25", "Hybrid dense and lexical without CLIP or reranking", use_dense=True, use_bm25=True, use_clip=False, use_rrf=False, use_cross_encoder=False),
            AblationConfig("B4", "Dense + BM25 + CLIP", "Multi-channel retrieval without RRF", use_dense=True, use_bm25=True, use_clip=True, use_rrf=False, use_cross_encoder=False),
            AblationConfig("B4_prime", "Dense + BM25 + CLIP + RRF", "Multi-channel retrieval with Reciprocal Rank Fusion", use_dense=True, use_bm25=True, use_clip=True, use_rrf=True, use_cross_encoder=False),
            AblationConfig("B5", "Dense + BM25 + CLIP + RRF + Cross Encoder", "Full hybrid pipeline with neural cross-encoder reranking", use_dense=True, use_bm25=True, use_clip=True, use_rrf=True, use_cross_encoder=True),
            # Component ablations
            AblationConfig("B5_minus_dense", "B5 - Dense", "Full pipeline without dense text retrieval", use_dense=False, use_bm25=True, use_clip=True, use_rrf=True, use_cross_encoder=True),
            AblationConfig("B5_minus_bm25", "B5 - BM25", "Full pipeline without BM25 lexical retrieval", use_dense=True, use_bm25=False, use_clip=True, use_rrf=True, use_cross_encoder=True),
            AblationConfig("B5_minus_clip", "B5 - CLIP", "Full pipeline without CLIP visual retrieval", use_dense=True, use_bm25=True, use_clip=False, use_rrf=True, use_cross_encoder=True),
            AblationConfig("B5_minus_cross_encoder", "B5 - Cross Encoder", "Full pipeline without neural reranking", use_dense=True, use_bm25=True, use_clip=True, use_rrf=True, use_cross_encoder=False),
        ]

    def evaluate_ablation_run(
        self,
        experiment_id: str,
        retrieved_items: Sequence[Dict[str, Any]],
        duration_seconds: float = 0.0,
    ) -> ExperimentResult:
        """Computes metrics for a completed ablation variant."""
        config_obj = next((c for c in self.ablation_definitions if c.experiment_id == experiment_id), None)
        if not config_obj:
            config_obj = AblationConfig(experiment_id, experiment_id, "Custom ablation")

        if not retrieved_items:
            return ExperimentResult(
                experiment_id=experiment_id,
                name=config_obj.name,
                status="NOT_RUN",
                reason="No retrieval data collected for this ablation variant",
                config=config_obj.to_dict(),
            )

        all_retrieved = []
        all_relevant = []
        metric_values: Dict[str, List[float]] = {}

        for item in retrieved_items:
            r = item.get("retrieved_ids") or []
            s = set(item.get("relevant_ids") or [])
            if s:
                all_retrieved.append(r)
                all_relevant.append(s)
                suite = calculate_retrieval_suite(r, s, ks=(1, 3, 5, 10))
                for metric_name, value in suite.items():
                    metric_values.setdefault(metric_name, []).append(float(value))

        if not all_relevant:
            return ExperimentResult(
                experiment_id=experiment_id,
                name=config_obj.name,
                status="NOT_RUN",
                reason="No ground truth relevant chunks found in items",
                config=config_obj.to_dict(),
            )

        ret_metrics = {
            metric_name: round(statistics.mean(values), 4)
            for metric_name, values in metric_values.items()
        }
        ret_metrics["mrr"] = round(mrr(all_retrieved, all_relevant), 4)
        ret_metrics["map"] = round(mean_average_precision(all_retrieved, all_relevant), 4)
        ret_metrics["evaluated_queries"] = len(all_relevant)

        return ExperimentResult(
            experiment_id=experiment_id,
            name=config_obj.name,
            status="COMPLETED",
            config=config_obj.to_dict(),
            retrieval_metrics=ret_metrics,
            num_samples=len(all_relevant),
            duration_seconds=round(duration_seconds, 2),
        )
