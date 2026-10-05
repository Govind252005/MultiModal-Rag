from __future__ import annotations

import re
from typing import List

import numpy as np

from backend import config

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])")

def _split_sentences(text: str) -> List[str]:
    text = (text or "").strip()
    if not text:
        return []
    sents = [s.strip() for s in _SENT_SPLIT.split(text) if s.strip()]
    return sents if sents else [text]

def _word_chunks(text: str, size: int, overlap: int) -> List[str]:
    text = (text or "").strip()
    if not text:
        return []

    words = text.split()
    if len(words) <= size:
        return [text]

    chunks: List[str] = []
    step = max(1, size - overlap)
    for start in range(0, len(words), step):
        window = words[start:start + size]
        if not window:
            break
        chunks.append(" ".join(window))
        if start + size >= len(words):
            break
    return chunks

def _semantic_chunks(
    text: str,
    max_words: int,
    min_words: int,
    sim_threshold: float,
) -> List[str]:
    text = (text or "").strip()
    if not text:
        return []

    sentences = _split_sentences(text)
    if len(sentences) <= 1:
        return [text]

    # Lazy import to avoid heavy startup during module import.
    from backend.retrieval import embeddings
    sent_vecs = embeddings.embed_text(sentences)
    chunks: List[str] = []

    cur_sentences: List[str] = []
    cur_vecs: List[np.ndarray] = []
    cur_words = 0

    def flush():
        nonlocal cur_sentences, cur_vecs, cur_words
        if cur_sentences:
            chunks.append(" ".join(cur_sentences).strip())
        cur_sentences = []
        cur_vecs = []
        cur_words = 0

    for i, s in enumerate(sentences):
        w = len(s.split())
        v = sent_vecs[i]

        if not cur_sentences:
            cur_sentences.append(s)
            cur_vecs.append(v)
            cur_words = w
            continue

        centroid = np.mean(np.stack(cur_vecs, axis=0), axis=0)
        sim = float(np.dot(centroid, v))

        would_exceed = (cur_words + w) > max_words
        semantic_break = sim < sim_threshold and cur_words >= min_words

        if would_exceed or semantic_break:
            flush()

        cur_sentences.append(s)
        cur_vecs.append(v)
        cur_words += w

    flush()

    # Fallback safety for tiny segments
    safe: List[str] = []
    for c in chunks:
        if len(c.split()) < 20 and safe:
            safe[-1] = safe[-1] + " " + c
        else:
            safe.append(c)
    return safe

def chunk_text(
    text: str,
    size: int = config.CHUNK_SIZE_WORDS,
    overlap: int = config.CHUNK_OVERLAP_WORDS,
) -> List[str]:
    if config.CHUNKING_STRATEGY == "semantic":
        try:
            return _semantic_chunks(
                text=text,
                max_words=size,
                min_words=config.SEMANTIC_MIN_WORDS,
                sim_threshold=config.SEMANTIC_SIM_THRESHOLD,
            )
        except Exception:
            # Never block ingestion if semantic chunking fails.
            return _word_chunks(text, size=size, overlap=overlap)
    return _word_chunks(text, size=size, overlap=overlap)