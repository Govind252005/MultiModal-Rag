"""
Embedding models — the heart of "shared semantic space" retrieval.

  1. TEXT encoder  (multilingual MiniLM) -> 384-dim : text/OCR/captions/transcripts
  2. CLIP encoder  (ViT-B/32)            -> 512-dim : images AND text, one space

Loaded lazily and cached as singletons so we never reload heavy models per
request. Encoding is batched (config.EMBED_BATCH_SIZE) for GPU throughput.
"""

from __future__ import annotations

import threading
from typing import List

import numpy as np
from PIL import Image

from backend import config

_text_model = None
_clip_model = None
# brief §100: FastAPI's sync `def` route handlers run in a threadpool, so
# two concurrent first-requests could both see `_model is None` and both
# load a multi-hundred-MB model at once. Not a correctness bug in CPython
# (module-level assignment is atomic; the loser's model just gets
# garbage-collected) but a real, avoidable waste of memory and load time —
# exactly what the brief means by "avoid repeatedly loading... models
# should be loaded once where safe." Double-checked locking below.
_text_model_lock = threading.Lock()
_clip_model_lock = threading.Lock()


def _get_text_model():
    global _text_model
    if _text_model is None:
        with _text_model_lock:
            if _text_model is None:  # re-check: another thread may have won the race
                from sentence_transformers import SentenceTransformer
                print(f"[embeddings] loading text model {config.TEXT_EMBED_MODEL} on {config.DEVICE} ...")
                _text_model = SentenceTransformer(config.TEXT_EMBED_MODEL, device=config.DEVICE)
    return _text_model


def _get_clip_model():
    global _clip_model
    if _clip_model is None:
        with _clip_model_lock:
            if _clip_model is None:
                from sentence_transformers import SentenceTransformer
                print(f"[embeddings] loading CLIP model {config.CLIP_MODEL} on {config.DEVICE} ...")
                _clip_model = SentenceTransformer(config.CLIP_MODEL, device=config.DEVICE)
    return _clip_model


def embed_text(texts: List[str]) -> np.ndarray:
    if not texts:
        return np.zeros((0, config.TEXT_EMBED_DIM), dtype=np.float32)
    vecs = _get_text_model().encode(
        texts, normalize_embeddings=True, convert_to_numpy=True,
        batch_size=config.EMBED_BATCH_SIZE, show_progress_bar=False)
    return vecs.astype(np.float32)


def embed_clip_text(texts: List[str]) -> np.ndarray:
    if not texts:
        return np.zeros((0, config.CLIP_EMBED_DIM), dtype=np.float32)

    # CLIP supports only ~77 tokens, so trim long inputs.
    clipped = [
        " ".join(str(text).split()[:60])
        for text in texts
    ]

    vecs = _get_clip_model().encode(
        clipped,
        normalize_embeddings=True,
        convert_to_numpy=True,
        batch_size=config.EMBED_BATCH_SIZE,
        show_progress_bar=False,
    )

    return vecs.astype(np.float32)


def embed_clip_image(images: List[Image.Image]) -> np.ndarray:
    if not images:
        return np.zeros((0, config.CLIP_EMBED_DIM), dtype=np.float32)
    vecs = _get_clip_model().encode(
        images, normalize_embeddings=True, convert_to_numpy=True,
        batch_size=config.EMBED_BATCH_SIZE, show_progress_bar=False)
    return vecs.astype(np.float32)


def warmup() -> None:
    """Force-load both models (call at server startup to avoid first-query lag)."""
    _get_text_model()
    _get_clip_model()
