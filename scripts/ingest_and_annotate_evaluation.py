"""Ingest the canonical evaluation corpus and attach current chunk IDs.

This uses the same ingestion orchestrator and Chroma/FTS5 stores as the API.
Chunk annotations are explicitly marked as candidate annotations: matching an
answer/source term to a chunk is useful for a reproducible pilot, but still
requires human review before publication-grade retrieval scores are claimed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


SUPPORTED = {".pdf", ".docx", ".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp", ".gif", ".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac"}


def _tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]{3,}", (value or "").lower()) if token not in {"what", "which", "when", "where", "how", "does", "was", "were", "the", "this", "that", "with", "from", "into", "and", "for"}}


def _candidate_chunks(question: Dict[str, Any], chunks: List[Dict[str, Any]]) -> List[str]:
    source = question.get("source_file")
    if not source or not question.get("answerable", True):
        return []
    target_tokens = _tokens(f"{question.get('question', '')} {question.get('answer', question.get('expected_answer', ''))}")
    scored = []
    for chunk in chunks:
        meta = chunk.get("metadata", {})
        if meta.get("file") != source:
            continue
        score = len(target_tokens & _tokens(chunk.get("document", "")))
        if score:
            scored.append((score, chunk["id"]))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [chunk_id for _, chunk_id in scored[:8]]


def run(corpus_dir: Path, dataset_path: Path, session_id: str, user_id: str, output_dir: Path, mode: str) -> Dict[str, Any]:
    from backend import sessions as session_store
    from backend.ingestion.ingest import ingest_file
    from backend.retrieval import vector_store

    session_store.ensure_exists(session_id, user_id)
    files = sorted(path for path in corpus_dir.rglob("*") if path.is_file() and path.suffix.lower() in SUPPORTED)
    results: List[Dict[str, Any]] = []
    started = time.perf_counter()
    for path in files:
        try:
            result = ingest_file(str(path), session_id=session_id, user_id=user_id, mode=mode)
            results.append({"path": str(path), **result})
        except Exception as exc:
            results.append({"path": str(path), "file": path.name, "status": "FAILED", "error": f"{type(exc).__name__}: {exc}"})

    where = vector_store.build_where(session_id=session_id, user_id=user_id)
    chunks = vector_store.get_text_corpus(where=where)
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    for item in dataset:
        candidate_ids = _candidate_chunks(item, chunks)
        item["relevant_chunk_ids"] = candidate_ids
        if item.get("answerable", True) and item.get("source_file"):
            item["ground_truth_status"] = "candidate_chunk_annotation_requires_human_review"
            item["notes"] = ((item.get("notes") or "").rstrip() + " Current chunk IDs were generated from the unified corpus; review before publication-grade scoring.").strip()
        elif not item.get("answerable", True):
            item["relevant_chunk_ids"] = []
    dataset_path.write_text(json.dumps(dataset, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    session_store.set_files(session_id, vector_store.list_files(session_id=session_id, user_id=user_id))
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "session_id": session_id,
        "user_id": user_id,
        "corpus_dir": str(corpus_dir),
        "dataset": str(dataset_path),
        "ingestion_mode": mode,
        "duration_seconds": round(time.perf_counter() - started, 2),
        "files": results,
        "successful_files": sum(1 for item in results if item.get("status") != "FAILED" and not item.get("error")),
        "failed_files": sum(1 for item in results if item.get("status") == "FAILED" or item.get("error")),
        "text_chunks": len(chunks),
        "candidate_annotated_questions": sum(1 for item in dataset if item.get("relevant_chunk_ids")),
        "human_review_required": True,
    }
    (output_dir / "ingestion_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (output_dir / "chunk_catalog.json").write_text(json.dumps(chunks, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest the unified evaluation corpus and update current chunk IDs.")
    parser.add_argument("--corpus", type=Path, default=Path("evaluation/corpus"))
    parser.add_argument("--dataset", type=Path, default=Path("evaluation/datasets/rag_test_dataset.json"))
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--output", type=Path, default=Path("reports/evaluation/unified_corpus"))
    parser.add_argument("--mode", choices=("fast", "balanced", "max_quality"), default="max_quality")
    args = parser.parse_args()
    manifest = run(args.corpus, args.dataset, args.session_id, args.user_id, args.output, args.mode)
    print(json.dumps({key: manifest[key] for key in ("session_id", "successful_files", "failed_files", "text_chunks", "candidate_annotated_questions", "human_review_required")}, indent=2))
    return 0 if manifest["failed_files"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())