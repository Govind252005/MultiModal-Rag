"""
Ingestion orchestrator (session-aware).

Given a file it picks the right parser, embeds the records into the correct
vector space, and stores them in Chroma tagged with a `session_id` so each
chat has its OWN isolated library. Re-ingesting a file first removes its old
chunks (upsert) so you never get duplicates.

CLI (test without the API / frontend):
    python -m ingestion.ingest  path\\to\\file.pdf  [session_id]
    python -m ingestion.ingest  path\\to\\a_folder  [session_id]
"""

from __future__ import annotations

import hashlib
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend import config
from backend.observability import metrics as obs_metrics
from backend.retrieval import embeddings, vector_store
DOC_EXT = {".pdf", ".docx", ".doc"}
IMG_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp", ".gif"}
AUD_EXT = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac"}

# brief §44: configurable ingestion depth. Default is MAX_QUALITY —
# i.e. exactly the behavior this app already had before this option
# existed, so no existing caller regresses by not passing `mode`.
#   FAST     — text extraction + embedding only (no OCR fallback, no
#              table extraction, no embedded-image extraction/captions)
#   BALANCED — + selective OCR (only when extracted text is sparse) +
#              CLIP for standalone images; no BLIP captions, no embedded
#              images pulled out of documents
#   MAX_QUALITY — everything: OCR, tables, embedded images, BLIP
#              captions, CLIP — this app's original, only behavior
VALID_MODES = ("fast", "balanced", "max_quality")


def _mode_flags(mode: str) -> Dict[str, bool]:
    mode = (mode or "max_quality").lower()
    if mode not in VALID_MODES:
        raise ValueError(f"Unknown ingestion mode '{mode}'. Valid: {VALID_MODES}")
    return {
        "ocr_fallback": mode in ("balanced", "max_quality"),
        "extract_tables": mode == "max_quality",
        "extract_embedded_images": mode == "max_quality",
        "caption_images": mode == "max_quality",
    }


def _modality_for(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext in DOC_EXT:
        return "document"
    if ext in IMG_EXT:
        return "image"
    if ext in AUD_EXT:
        return "audio"
    raise ValueError(f"Unsupported file type: {ext}")


def _records_for(path: str, modality: str,
                 image_dir: Optional[Path] = None, mode: str = "max_quality") -> List[Dict[str, Any]]:
    flags = _mode_flags(mode)
    if modality == "document":
        from backend.ingestion.pdf_docx_parser import parse_document        
        return parse_document(path, image_dir=image_dir,
                              ocr_fallback=flags["ocr_fallback"],
                              extract_tables=flags["extract_tables"],
                              extract_embedded_images=flags["extract_embedded_images"])
    if modality == "image":
        from backend.ingestion.image_pipeline import parse_image        
        return parse_image(path, caption_images=flags["caption_images"])
    if modality == "audio":
        from backend.ingestion.audio_pipeline import parse_audio        
        return parse_audio(path)
    return []


def _content_hash(path: str) -> str:
    """SHA-256 of the file's bytes (brief §45)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ingest_file(path: str, session_id: Optional[str] = None,
                user_id: Optional[str] = None, mode: str = "max_quality") -> Dict[str, Any]:
    """Parse + embed + store one file into a user's session library.

    `mode` (brief §44): "fast" | "balanced" | "max_quality" — see the
    VALID_MODES comment above for exactly what each tier skips.

    Idempotent (brief §45): if this exact file (by content hash) was
    already ingested with the current pipeline version AND mode, this is
    a no-op that skips OCR/embedding/captioning entirely instead of
    redoing all of it just because the same bytes were uploaded again.
    Re-ingestion still happens — deliberately — when the content, the
    pipeline version, OR the mode has changed (a different mode
    genuinely produces different chunks, so it must invalidate the
    "already ingested" check same as a content change would).
    """
    file = Path(path).name
    modality = _modality_for(path)
    content_hash = _content_hash(path)
    mode = (mode or "max_quality").lower()
    _mode_flags(mode)  # raises ValueError early on an invalid mode name

    existing = vector_store.get_file_fingerprint(file, session_id=session_id, user_id=user_id)
    if (existing and existing.get("content_hash") == content_hash
            and existing.get("pipeline_version") == config.INGESTION_PIPELINE_VERSION
            and existing.get("ingestion_mode", "max_quality") == mode):
        print(f"[ingest] {file} unchanged (hash+pipeline version+mode match) — skipping re-ingestion")
        return {"file": file, "modality": modality, "chunks": 0, "skipped_duplicate": True}

    # Upsert within this session.
    vector_store.delete_file(file, session_id=session_id)

    # Embedded images are saved next to the source file — that is exactly the
    # directory /api/media/{session}/{name} serves from, so they render inline.
    image_dir = Path(path).parent
    # brief §70: per-stage ingestion timing. Pushed to the same Prometheus
    # registry the rest of the app uses (observability/metrics.py) so
    # ingestion latency shows up on the same dashboard as query latency,
    # rather than being a separate, uncorrelated measurement.
    parse_start = time.perf_counter()
    records = _records_for(path, modality, image_dir=image_dir, mode=mode)
    parse_ms = (time.perf_counter() - parse_start) * 1000
    obs_metrics.observe_histogram("ingestion_stage_duration_ms", parse_ms,
                                  {"stage": "parse", "modality": modality})

    for r in records:                       # tag every chunk with owner + session
        if session_id:
            r["metadata"]["session_id"] = session_id
        if user_id:
            r["metadata"]["user_id"] = user_id
        # brief §45/§46: every chunk records the content hash + pipeline
        # version + ingestion mode that produced it, so a future ingest
        # can tell whether this exact combination was already processed,
        # and so a version/mode change makes old chunks recognizably stale.
        r["metadata"]["content_hash"] = content_hash
        r["metadata"]["pipeline_version"] = config.INGESTION_PIPELINE_VERSION
        r["metadata"]["embedding_model"] = config.TEXT_EMBED_MODEL
        r["metadata"]["ingestion_mode"] = mode

    text_recs = [r for r in records if r["target"] == "text"]
    image_recs = [r for r in records if r["target"] == "image"]

    embed_start = time.perf_counter()
    if text_recs:
        vecs = embeddings.embed_text([r["text"] for r in text_recs])
        vector_store.add_text_chunks(
            ids=[uuid.uuid4().hex for _ in text_recs], embeddings=vecs.tolist(),
            documents=[r["text"] for r in text_recs],
            metadatas=[r["metadata"] for r in text_recs])

    if image_recs:
        vecs = embeddings.embed_clip_image([r["image"] for r in image_recs])
        vector_store.add_images(
            ids=[uuid.uuid4().hex for _ in image_recs], embeddings=vecs.tolist(),
            documents=[r["text"] for r in image_recs],
            metadatas=[r["metadata"] for r in image_recs])
    embed_ms = (time.perf_counter() - embed_start) * 1000
    obs_metrics.observe_histogram("ingestion_stage_duration_ms", embed_ms,
                                  {"stage": "embed_and_index", "modality": modality})

    total = len(text_recs) + len(image_recs)
    print(f"[ingest] {file} -> {total} chunks ({modality}) session={session_id} "
         f"(parse={parse_ms:.0f}ms, embed+index={embed_ms:.0f}ms)")
    return {
        "file": file, "modality": modality, "chunks": total, "skipped_duplicate": False,
        "parse_ms": round(parse_ms, 1), "embed_and_index_ms": round(embed_ms, 1),
    }


def ingest_path(path: str, session_id: Optional[str] = None,
                user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    p = Path(path)
    results = []

    if p.is_dir():
        for f in sorted(p.rglob("*")):
            if f.is_file():
                try:
                    results.append(ingest_file(str(f), session_id, user_id))
                except Exception as e:
                    print(f"[WARN] Failed to ingest {f}: {e}")
    else:
        results.append(ingest_file(str(p), session_id, user_id))

    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    sid = sys.argv[2] if len(sys.argv) > 2 else "cli-test"
    uid = sys.argv[3] if len(sys.argv) > 3 else None

    summary = ingest_path(sys.argv[1], sid, uid)

    print("\n=== Ingestion summary ===")
    for s in summary:
        print(f"  {s['file']:<40} {s['modality']:<10} {s['chunks']} chunks")

    print("Index stats:", vector_store.stats())
