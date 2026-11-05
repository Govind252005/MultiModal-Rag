"""
Vector store — a thin wrapper around ChromaDB (embedded, no server).

Two collections in ONE persistent Chroma DB:
  * TEXT_COLLECTION  (384-dim) : document chunks, image OCR, image captions,
                                 audio transcripts.
  * IMAGE_COLLECTION (512-dim) : raw CLIP image vectors (visual / text->image).

Every item carries rich metadata (session_id, file, modality, page, timecode,
source_type). The `session_id` field is what isolates each chat's library:
queries and listings always filter by it.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.config import Settings

from backend import config
from backend.retrieval import lexical_index
# ------------------------------------------------------------------
# Client + collections (created once, reused)
# ------------------------------------------------------------------
_client = chromadb.PersistentClient(
    path=str(config.CHROMA_DIR),
    settings=Settings(anonymized_telemetry=False, allow_reset=True),
)

_text_col = _client.get_or_create_collection(
    name=config.TEXT_COLLECTION, metadata={"hnsw:space": "cosine"})
_image_col = _client.get_or_create_collection(
    name=config.IMAGE_COLLECTION, metadata={"hnsw:space": "cosine"})


def _clean_meta(meta: Dict[str, Any]) -> Dict[str, Any]:
    """Chroma only accepts str/int/float/bool metadata (no None/nested)."""
    out: Dict[str, Any] = {}
    for k, v in meta.items():
        if v is None:
            continue
        out[k] = v if isinstance(v, (str, int, float, bool)) else str(v)
    return out


def _now() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


# ------------------------------------------------------------------
# where-filter builder (session + modality + specific files)
# ------------------------------------------------------------------
def build_where(
    session_id: Optional[str] = None,
    modality: Optional[str] = None,
    files: Optional[List[str]] = None,
    user_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Compose a Chroma `where` filter. Chroma needs $and for >1 condition."""
    clauses: List[Dict[str, Any]] = []
    if user_id:
        clauses.append({"user_id": user_id})
    if session_id:
        clauses.append({"session_id": session_id})
    if modality and modality != "all":
        clauses.append({"modality": modality})
    if files:
        clauses.append({"file": {"$in": list(files)}})
    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


# ------------------------------------------------------------------
# Writing
# ------------------------------------------------------------------
def add_text_chunks(ids, embeddings, documents, metadatas) -> None:
    if not ids:
        return
    metas = [_clean_meta({**m, "ingested_at": m.get("ingested_at", _now())}) for m in metadatas]
    _text_col.add(ids=ids, embeddings=embeddings, documents=documents, metadatas=metas)
    # Keep the persistent lexical (BM25/FTS5) index in lockstep with the
    # dense index instead of rebuilding it from the corpus at query time
    # (AUDIT_REPORT.md P1-1). Use the *cleaned* metadata so both indexes
    # agree on what was actually stored.
    try:
        lexical_index.add_chunks(ids=ids, documents=documents, metadatas=metas)
    except Exception as exc:  # never fail ingestion because of the lexical index
        print(f"[vector_store] lexical index update failed: {exc}")


def add_images(ids, embeddings, documents, metadatas) -> None:
    if not ids:
        return
    metas = [_clean_meta({**m, "ingested_at": m.get("ingested_at", _now())}) for m in metadatas]
    _image_col.add(ids=ids, embeddings=embeddings, documents=documents, metadatas=metas)


# ------------------------------------------------------------------
# Querying
# ------------------------------------------------------------------
def _format_results(res: Dict[str, Any]) -> List[Dict[str, Any]]:
    hits: List[Dict[str, Any]] = []
    if not res or not res.get("ids") or not res["ids"][0]:
        return hits
    ids = res["ids"][0]
    docs = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    dists = res.get("distances", [[]])[0]
    for i, _id in enumerate(ids):
        dist = dists[i] if i < len(dists) else 1.0
        hits.append({
            "id": _id,
            "document": docs[i] if i < len(docs) else "",
            "metadata": metas[i] if i < len(metas) else {},
            "score": round(1.0 - float(dist), 4),
        })
    return hits

def get_text_corpus(where=None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    got = _text_col.get(where=where or None, include=["documents", "metadatas"])
    ids = got.get("ids", []) or []
    docs = got.get("documents", []) or []
    metas = got.get("metadatas", []) or []

    out: List[Dict[str, Any]] = []
    n = len(ids) if limit is None else min(len(ids), limit)
    for i in range(n):
        out.append({
            "id": ids[i],
            "document": docs[i] if i < len(docs) else "",
            "metadata": metas[i] if i < len(metas) else {},
            "score": 0.0,
        })
    return out

def query_text(embedding, top_k=config.DEFAULT_TOP_K, where=None) -> List[Dict[str, Any]]:
    res = _text_col.query(
        query_embeddings=[embedding], n_results=top_k, where=where or None,
        include=["documents", "metadatas", "distances"])
    return _format_results(res)


def query_images(embedding, top_k=config.DEFAULT_TOP_K, where=None) -> List[Dict[str, Any]]:
    res = _image_col.query(
        query_embeddings=[embedding], n_results=top_k, where=where or None,
        include=["documents", "metadatas", "distances"])
    return _format_results(res)


# ------------------------------------------------------------------
# Housekeeping
# ------------------------------------------------------------------
def get_by_id(doc_id: str) -> Optional[Dict[str, Any]]:
    for col in (_text_col, _image_col):
        res = col.get(ids=[doc_id], include=["documents", "metadatas"])
        if res and res.get("ids"):
            return {
                "id": res["ids"][0],
                "document": res["documents"][0] if res["documents"] else "",
                "metadata": res["metadatas"][0] if res["metadatas"] else {},
            }
    return None


def list_files(session_id: Optional[str] = None,
               user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Per-file summary, scoped to a chat session and/or user."""
    where = build_where(session_id=session_id, user_id=user_id)
    summary: Dict[str, Dict[str, Any]] = {}
    for col in (_text_col, _image_col):
        got = col.get(where=where, include=["metadatas"])
        for meta in got.get("metadatas", []) or []:
            fname = meta.get("file", "unknown")
            entry = summary.setdefault(
                fname,
                {"file": fname, "modality": meta.get("modality", "unknown"),
                 "chunks": 0, "ingested_at": meta.get("ingested_at", "")})
            entry["chunks"] += 1
    return sorted(summary.values(), key=lambda x: x["file"])


def delete_file(filename: str, session_id: Optional[str] = None) -> int:
    """Remove a file's chunks. Scope to a session if given."""
    removed = 0
    where = build_where(session_id=session_id, files=[filename])
    for col in (_text_col, _image_col):
        got = col.get(where=where, include=[])
        ids = got.get("ids", [])
        if ids:
            col.delete(ids=ids)
            removed += len(ids)
    try:
        lexical_index.delete_by_file(filename, session_id=session_id)
    except Exception as exc:
        print(f"[vector_store] lexical index delete_by_file failed: {exc}")
    return removed


def delete_session(session_id: str) -> int:
    """Remove every chunk belonging to a chat session."""
    removed = 0
    where = {"session_id": session_id}
    for col in (_text_col, _image_col):
        got = col.get(where=where, include=[])
        ids = got.get("ids", [])
        if ids:
            col.delete(ids=ids)
            removed += len(ids)
    try:
        lexical_index.delete_by_session(session_id)
    except Exception as exc:
        print(f"[vector_store] lexical index delete_by_session failed: {exc}")
    return removed


def reset() -> None:
    global _text_col, _image_col
    _client.delete_collection(config.TEXT_COLLECTION)
    _client.delete_collection(config.IMAGE_COLLECTION)
    _text_col = _client.get_or_create_collection(
        name=config.TEXT_COLLECTION, metadata={"hnsw:space": "cosine"})
    _image_col = _client.get_or_create_collection(
        name=config.IMAGE_COLLECTION, metadata={"hnsw:space": "cosine"})
    try:
        lexical_index.reset()
    except Exception as exc:
        print(f"[vector_store] lexical index reset failed: {exc}")


def stats() -> Dict[str, int]:
    out = {"text_items": _text_col.count(), "image_items": _image_col.count()}
    try:
        out.update(lexical_index.stats())
    except Exception:
        pass
    return out


def get_file_fingerprint(file: str, session_id: Optional[str] = None,
                         user_id: Optional[str] = None) -> Optional[Dict[str, str]]:
    """brief §45: cheap existence+metadata check used to skip re-ingesting
    a file whose content/pipeline version/ingestion mode hasn't changed.
    Returns {"content_hash": ..., "pipeline_version": ..., "ingestion_mode": ...}
    from one existing chunk (every chunk of the same ingestion run
    carries the same values), or None if the file has no chunks yet."""
    where = build_where(session_id=session_id, user_id=user_id, files=[file])
    try:
        got = _text_col.get(where=where, limit=1, include=["metadatas"])
        metas = got.get("metadatas") or []
        if not metas:
            return None
        m = metas[0]
        return {
            "content_hash": m.get("content_hash", ""),
            "pipeline_version": m.get("pipeline_version", ""),
            "ingestion_mode": m.get("ingestion_mode", "max_quality"),
        }
    except Exception:
        return None


def has_images(session_id: Optional[str] = None,
               user_id: Optional[str] = None,
               files: Optional[List[str]] = None) -> bool:
    """Cheap existence check used to skip the CLIP retrieval branch entirely
    when the current scope has no images at all (AUDIT_REPORT.md P1-6: CLIP
    was always invoked for modality in {all, image}, even for text-only
    sessions). Fails open (returns True) if the check itself errors, so a
    version mismatch in the underlying client never silently disables image
    retrieval."""
    where = build_where(session_id=session_id, user_id=user_id, files=files)
    try:
        got = _image_col.get(where=where, limit=1, include=[])
        return bool(got.get("ids"))
    except Exception:
        return True
