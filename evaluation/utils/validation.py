"""
Dataset and configuration validation utilities.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple
from evaluation.schemas.dataset_schema import QADatasetItem, load_qa_dataset


def validate_qa_dataset(dataset_path: str | Path) -> Tuple[bool, List[str], Dict[str, Any]]:
    """
    Validates the 190-question evaluation dataset.
    Returns (is_valid, error_list, stats_dict).
    """
    errors: List[str] = []
    stats: Dict[str, Any] = {
        "total_questions": 0,
        "answerable_count": 0,
        "unanswerable_count": 0,
        "with_ground_truth": 0,
        "with_source_file": 0,
        "with_required_citations": 0,
        "with_relevant_chunks": 0,
        "categories": {},
        "modalities": {},
    }

    try:
        items = load_qa_dataset(dataset_path)
    except Exception as e:
        return False, [f"Failed to load dataset: {e}"], stats

    stats["total_questions"] = len(items)

    for idx, item in enumerate(items):
        qid = item.question_id or item.id or f"index_{idx}"
        if not item.question.strip():
            errors.append(f"[{qid}] Missing question text.")

        if item.answerable:
            stats["answerable_count"] += 1
            if not item.answer.strip():
                errors.append(f"[{qid}] Answerable question missing ground-truth answer.")
            else:
                stats["with_ground_truth"] += 1

            if item.source_file:
                stats["with_source_file"] += 1

            if item.required_citations:
                stats["with_required_citations"] += 1

            if item.relevant_chunk_ids:
                stats["with_relevant_chunks"] += 1
        else:
            stats["unanswerable_count"] += 1

        cat = item.category or "unknown"
        stats["categories"][cat] = stats["categories"].get(cat, 0) + 1

        mod = item.modality or "text"
        stats["modalities"][mod] = stats["modalities"].get(mod, 0) + 1

    is_valid = len(errors) == 0
    return is_valid, errors, stats
