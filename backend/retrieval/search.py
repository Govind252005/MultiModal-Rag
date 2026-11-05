"""
Multimodal search / fusion with per-USER + per-SESSION + per-FILE scoping and
citation de-duplication.

Channels merged:
  Text channel : text query vector -> TEXT collection (chunks/OCR/captions/transcripts)
  CLIP channel : CLIP text vector  -> IMAGE collection (text -> image match)

De-duplication keeps ONE citation per distinct piece of source:
  * document -> per (file, page)
  * audio    -> per (file, timecode)
  * image    -> the visual+caption collapse to one, but each OCR *chunk* of a
                text-heavy image stays its own citation (so big images surface
                all their extracted text, each independently clickable).
"""



from __future__ import annotations

import re
import threading
import numpy as np
from sentence_transformers import CrossEncoder

from typing import Any, Dict, List, Optional

from PIL import Image
import logging
logger = logging.getLogger(__name__)

from backend import config
from backend.retrieval import embeddings, lexical_index, vector_store

_SECTION_NAMES = (
    "abstract", "introduction", "background", "related work", "methods",
    "methodology", "results", "discussion", "conclusion", "references",
    "acknowledgments", "appendix",
)
_VISUAL_TERMS = re.compile(
    r"\b(image|photo|photograph|figure|chart|diagram|graph|visual|look at|see)\b",
    re.IGNORECASE,
)


def _requested_section(query: str) -> Optional[str]:
    value = (query or "").lower()
    for section in _SECTION_NAMES:
        if re.search(rf"\b{re.escape(section)}\b", value):
            return section
    return None


def _visual_query(query: str) -> bool:
    return bool(_VISUAL_TERMS.search(query or ""))

def _normalize(hit: Dict[str, Any], channel: str) -> Dict[str, Any]:
    m = hit.get("metadata", {}) or {}
    text = hit.get("document", "") or ""
    snippet = text.strip().replace("\n", " ")
    if len(snippet) > 300:
        snippet = snippet[:300].rstrip() + "…"
    file = m.get("file", "unknown")
    sid = m.get("session_id")
    # Use media_file (saved extracted image) when available, else the source file.
    serve_name = m.get("media_file") or file
    media_url = f"/api/media/{sid}/{serve_name}" if sid else f"/api/media/{serve_name}"
    return {
        "id": hit["id"],
        "modality": m.get("modality", "document"),
        "source_type": m.get("source_type", "text"),
        "file": file,
        "session_id": sid,
        "snippet": snippet,
        "text": text,
        "page": m.get("page"),
        "chunk": m.get("chunk"),
        "section": m.get("section"),
        "start": m.get("start"),
        "end": m.get("end"),
        "timestamp": m.get("timestamp"),
        "media_url": media_url,
        "media_file": m.get("media_file"),
        "score": hit.get("score", 0.0),
        "channel": channel,
    }


def _citation_key(h: Dict[str, Any]) -> str:
    if h["modality"] == "audio":
        return f"{h['file']}|{h.get('timestamp') or h.get('start')}"
    if h["modality"] == "document":
        return f"{h['file']}|p{h.get('page')}"
    # image: OCR chunks stay separate; caption + visual collapse to one per image.
    if h.get("source_type") == "ocr":
        return f"{h['file']}|ocr|{h.get('chunk')}"
    # Use media_file to distinguish embedded images from the same document.
    discriminator = h.get("media_file") or "standalone"
    return f"{h['file']}|img|{discriminator}"


def _merge_and_rank(text_hits, clip_hits, top_k) -> List[Dict[str, Any]]:
    normalized = [_normalize(h, "text") for h in text_hits]
    normalized += [_normalize(h, "clip") for h in clip_hits]

    groups: Dict[str, Dict[str, Any]] = {}
    for n in normalized:
        key = _citation_key(n)
        cur = groups.get(key)
        if cur is None:
            groups[key] = n
            continue
        best = max(cur["score"], n["score"])
        if n["source_type"] == "image" and cur["source_type"] != "image":
            rep = n
        elif cur["source_type"] == "image" and n["source_type"] != "image":
            rep = cur
        else:
            rep = n if len(n["text"]) > len(cur["text"]) else cur
        groups[key] = {**rep, "score": best}

    ranked = sorted(groups.values(), key=lambda x: x["score"], reverse=True)
    return ranked[:top_k]

#--Reranker--
_reranker = None
_reranker_lock = threading.Lock()

def _get_reranker():
    global _reranker
    if _reranker is None:
        with _reranker_lock:  # brief §100 — same double-checked-locking fix as embeddings.py
            if _reranker is None:
                _reranker = CrossEncoder(config.RERANK_MODEL, device=config.DEVICE)
    return _reranker

#--BM25 / lexical (persistent SQLite FTS5 index; see retrieval/lexical_index.py)--
def _bm25_search(
    query: str,
    top_n: int,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    modality: Optional[str] = None,
    files: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Reads the persistent lexical index built at ingest time — no corpus
    load or tokenizer pass here (AUDIT_REPORT.md P1-1)."""
    try:
        return lexical_index.search(
            query, top_n=top_n, user_id=user_id, session_id=session_id,
            modality=modality, files=files,
        )
    except Exception as exc:
        logger.exception("Lexical search failed: %s", exc)
        return []

#---RRF merge---
def _rrf_merge(rank_lists: List[List[Dict[str, Any]]], k: int) -> List[Dict[str, Any]]:
    pool: Dict[str, Dict[str, Any]] = {}
    rrf_scores: Dict[str, float] = {}

    for lst in rank_lists:
        for rank, hit in enumerate(lst, start=1):
            hid = hit["id"]
            if hid not in pool:
                pool[hid] = hit
            rrf_scores[hid] = rrf_scores.get(hid, 0.0) + (1.0 / (k + rank))

    merged = []
    for hid, h in pool.items():
        merged.append({**h, "score": rrf_scores[hid]})
    merged.sort(key=lambda x: x["score"], reverse=True)
    return merged

#--reranker helper--
def _rerank(query: str, hits: List[Dict[str, Any]], top_n: int) -> List[Dict[str, Any]]:
    if not hits:
        return []

    if not config.RERANK_ENABLED:
        return hits[:top_n]

    try:
        model = _get_reranker()

        pairs = [
            [query, h.get("document", "") or h.get("snippet", "")]
            for h in hits
        ]

        scores = model.predict(
            pairs,
            batch_size=config.RERANK_BATCH_SIZE
        )

        reranked = []

        for i, h in enumerate(hits):
            reranked.append({
                **h,
                "rerank_score": float(scores[i])
            })

        reranked.sort(
            key=lambda x: x["rerank_score"],
            reverse=True
        )

        return reranked[:top_n]

    except Exception as e:
        logger.exception("Reranker failed: %s", e)
        return hits[:top_n]
# ------------------------------------------------------------------ text query
def text_query(
    query: str,
    top_k: int = config.DEFAULT_TOP_K,
    modality: str = "all",
    session_id: Optional[str] = None,
    files: Optional[List[str]] = None,
    user_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    where = vector_store.build_where(
        session_id=session_id, modality=modality, files=files, user_id=user_id)
    requested_section = _requested_section(query)

    # 1) Dense text search
    text_vec = embeddings.embed_text([query])[0].tolist()
    dense_text_hits = vector_store.query_text(
        text_vec, top_k=max(top_k, config.DENSE_CANDIDATES), where=where
    )

    # 2) BM25 keyword search — reads the persistent lexical index (no
    # corpus load / re-tokenize per query; see AUDIT_REPORT.md P1-1).
    bm25_hits = _bm25_search(
        query, top_n=max(top_k, config.BM25_CANDIDATES),
        user_id=user_id, session_id=session_id, modality=modality, files=files,
    )

    # 3) Optional CLIP text-to-image dense branch — skipped entirely when
    # this scope has no images at all (AUDIT_REPORT.md P1-6), instead of
    # unconditionally embedding the query with CLIP and querying an empty
    # collection on every text-only session.
    clip_hits: List[Dict[str, Any]] = []

    if modality in ("all", "image") and (modality == "image" or _visual_query(query)) and vector_store.has_images(
        session_id=session_id, user_id=user_id, files=files
    ):
        img_where = vector_store.build_where(
            session_id=session_id,
            files=files,
            user_id=user_id,
        )

        clip_vec = embeddings.embed_clip_text([query])[0].tolist()

        clip_hits = vector_store.query_images(
            clip_vec,
            top_k=max(top_k, config.DENSE_CANDIDATES),
            where=img_where,
        )

    # 4) Merge using RRF
    merged = _rrf_merge([dense_text_hits, bm25_hits, clip_hits], k=config.FUSION_RRF_K)

    # 5) Normalize fields and dedupe by citation target
    normalized = [_normalize(h, "hybrid") for h in merged]
    deduped: Dict[str, Dict[str, Any]] = {}
    for n in normalized:
        key = _citation_key(n)
        cur = deduped.get(key)
        if cur is None or n["score"] > cur["score"]:
            deduped[key] = n
    candidates = sorted(deduped.values(), key=lambda x: x["score"], reverse=True)

    # Apply section scope after dense/BM25/CLIP fusion so unrelated channels
    # cannot reintroduce passages outside the requested document section.
    if requested_section:
        section_candidates = [h for h in candidates if h.get("section")]
        # Older ingested chunks may not have section metadata. Do not turn
        # valid retrieval into a false empty result in that case; use the
        # normal semantic/lexical ranking until those files are re-ingested.
        if section_candidates:
            candidates = [
                h for h in section_candidates
                if h.get("section") == requested_section
            ]

    # 6) Cross-encoder rerank and return top_k (default 5)
    reranked = _rerank(query, candidates, top_n=top_k)
    return reranked

# ------------------------------------------------------------------ image query
def image_query(
    image: Image.Image,
    top_k: int = config.DEFAULT_TOP_K,
    session_id: Optional[str] = None,
    files: Optional[List[str]] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    from backend.ingestion.image_pipeline import caption_image, ocr_image
    caption = caption_image(image)
    ocr_text = ocr_image(image)

    img_where = vector_store.build_where(session_id=session_id, files=files, user_id=user_id)
    clip_vec = embeddings.embed_clip_image([image])[0].tolist()
    clip_hits = vector_store.query_images(clip_vec, top_k=top_k, where=img_where)

    probe = (caption + ". " + ocr_text).strip()
    txt_where = vector_store.build_where(session_id=session_id, files=files, user_id=user_id)
    text_vec = embeddings.embed_text([probe])[0].tolist()
    text_hits = vector_store.query_text(text_vec, top_k=top_k, where=txt_where)

    hits = _merge_and_rank(text_hits, clip_hits, top_k)
    return {"query_caption": caption, "query_ocr": ocr_text, "hits": hits}
