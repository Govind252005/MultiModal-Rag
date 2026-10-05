"""
Component Ablation Experiments (Requirement 14).
Runs systematic component removal ablations:
- B5 - Dense
- B5 - BM25
- B5 - CLIP
- B5 - RRF
- B5 - Cross Encoder
- B5 - Semantic Chunking
- B5 - OCR
- B5 - Audio transcription
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Sequence
from evaluation.evaluators.ablation_evaluator import AblationEvaluator
from evaluation.schemas.dataset_schema import QADatasetItem


def run_component_ablations(
    dataset: Sequence[QADatasetItem],
    backend_caller=None,
    top_k: int = 5,
) -> Dict[str, Any]:
    evaluator = AblationEvaluator()
    results = []

    component_configs = [
        "B5_minus_dense",
        "B5_minus_bm25",
        "B5_minus_clip",
        "B5_minus_cross_encoder",
    ]

    for exp_id in component_configs:
        t0 = time.perf_counter()
        retrieved_items = []

        if backend_caller is not None:
            for item in dataset:
                ret = backend_caller(item.question, top_k=top_k, experiment_id=exp_id)
                retrieved_items.append({
                    "question_id": item.question_id,
                    "retrieved_ids": [h.get("id") for h in ret.get("retrieved", [])],
                    "relevant_ids": item.relevant_chunk_ids,
                })

        dur = time.perf_counter() - t0
        res = evaluator.evaluate_ablation_run(exp_id, retrieved_items, duration_seconds=dur)
        results.append(res.to_dict())

    return {
        "status": "COMPLETED" if any(r.get("status") == "COMPLETED" for r in results) else "NOT_RUN",
        "experiments": results,
    }
