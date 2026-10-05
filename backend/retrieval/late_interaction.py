"""
Phase 3B — Optional ColBERT / late-interaction reranker.

This is applied AFTER the existing retrieval pipeline (dense + BM25 + CLIP +
RRF + cross-encoder) as an extra, opt-in reranking stage. It is:

  * config-gated (config.COLBERT_ENABLED, default OFF), and
  * fully graceful: if the optional `ragatouille` dependency or the ColBERT
    model is unavailable, it logs once and returns the hits UNCHANGED.

It never imports or modifies retrieval/search.py, so the core pipeline stays
byte-for-byte identical when this feature is off (the default).

Install (optional, on the machine that will use it):
    pip install ragatouille
The model (config.COLBERT_MODEL) downloads once, then runs offline.
"""

from __future__ import annotations

from typing import Any, Dict, List

from backend import config

_model = None
_load_failed = False


def _get_model():
    """Lazily load a ColBERT reranker. Returns None if unavailable."""
    global _model, _load_failed
    if _model is not None or _load_failed:
        return _model
    try:
        # pyrefly: ignore [missing-import]
        from ragatouille import RAGPretrainedModel
        _model = RAGPretrainedModel.from_pretrained(config.COLBERT_MODEL)
    except Exception as exc:  # missing dep, no model, offline first run, etc.
        print(f"[colbert] unavailable, skipping rerank: {exc}")
        _load_failed = True
        _model = None
    return _model


def rerank(
    query: str,
    hits: List[Dict[str, Any]],
    top_n: int | None = None,
) -> List[Dict[str, Any]]:
    """Late-interaction rerank of *hits* for *query*.

    Returns hits reordered (and truncated to top_n) on success, or the
    original hits unchanged on any failure / when disabled.
    """
    if not config.COLBERT_ENABLED or not hits:
        return hits

    top_n = top_n or config.COLBERT_TOP_N

    model = _get_model()
    if model is None:
        return hits

    try:
        documents = [
            h.get("text") or h.get("snippet") or ""
            for h in hits
        ]

        results = model.rerank(
            query=query,
            documents=documents,
            k=min(top_n, len(documents)),
        )

        reranked: List[Dict[str, Any]] = []

        for r in results:
            idx = r.get("result_index")

            if idx is None or idx >= len(hits):
                continue

            h = dict(hits[idx])
            h["colbert_score"] = float(r.get("score", 0.0))
            reranked.append(h)

        return reranked or hits

    except Exception as exc:
        print(
            f"[colbert] rerank failed, returning original order: {exc}"
        )
        return hits
