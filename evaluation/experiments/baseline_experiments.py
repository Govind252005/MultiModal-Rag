"""
Baseline Retrieval Experiments (B1 to B5).
Runs systematic retrieval pipeline configurations:
- B1: BM25 lexical only
- B2: Dense semantic only
- B3: Dense + BM25
- B4: Dense + BM25 + CLIP
- B4': Dense + BM25 + CLIP + RRF
- B5: Full hybrid pipeline with neural cross-encoder
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Sequence
from evaluation.evaluators.ablation_evaluator import AblationEvaluator
from evaluation.schemas.dataset_schema import QADatasetItem


def run_baseline_experiments(
    dataset: Sequence[QADatasetItem],
    backend_caller=None,
    top_k: int = 5,
) -> Dict[str, Any]:
    """Runs baseline retrieval experiments B1 through B5."""
    evaluator = AblationEvaluator()
    results = []

    # Map baseline configs
    configs = ["B1", "B2", "B3", "B4", "B4_prime", "B5"]

    for exp_id in configs:
        t0 = time.perf_counter()
        retrieved_items = []

        # If backend caller is provided, execute queries with specific ablation flags
        if backend_caller is not None:
            for item in dataset:
                ret = backend_caller(item.question, top_k=top_k, experiment_id=exp_id)
                retrieved_items.append({
                    "question_id": item.question_id,
                    "retrieved_ids": [h.get("id") for h in ret.get("retrieved", [])],
                    "relevant_ids": item.relevant_chunk_ids,
                })
        else:
            # When caller not available, recorded as pending live execution
            pass

        dur = time.perf_counter() - t0
        res = evaluator.evaluate_ablation_run(exp_id, retrieved_items, duration_seconds=dur)
        results.append(res.to_dict())

    return {
        "status": "COMPLETED" if any(r.get("status") == "COMPLETED" for r in results) else "NOT_RUN",
        "experiments": results,
    }
