"""
Ground-truth evaluation dataset — schema + loader (brief §64).

A dataset is a JSON file: a list of question objects. See
evaluation/datasets/example_dataset.json for the shape. This loader does
no network/model calls — it just validates structure so a malformed
dataset fails fast with a clear message instead of a confusing crash deep
inside the runner.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

REQUIRED_FIELDS = {"question_id", "question", "category"}
VALID_CATEGORIES = {
    "factual", "multi-hop", "comparison", "numerical", "table",
    "summarization", "image", "audio", "cross-modal", "unanswerable",
    "adversarial",
}


class DatasetError(ValueError):
    pass


def load_dataset(path: str | Path) -> List[Dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        raise DatasetError(f"Dataset file not found: {p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DatasetError(f"Dataset is not valid JSON: {exc}") from exc
    if not isinstance(data, list):
        raise DatasetError("Dataset must be a JSON array of question objects.")

    for i, item in enumerate(data):
        missing = REQUIRED_FIELDS - set(item.keys())
        if missing:
            raise DatasetError(f"Question #{i} is missing required fields: {missing}")
        if item["category"] not in VALID_CATEGORIES:
            raise DatasetError(
                f"Question #{i} ('{item['question_id']}') has an unknown category "
                f"'{item['category']}'. Valid categories: {sorted(VALID_CATEGORIES)}"
            )
        item.setdefault("relevant_chunk_ids", [])
        item.setdefault("relevant_document_ids", [])
        item.setdefault("required_citations", [])
        item.setdefault("expected_answer", None)
    return data
