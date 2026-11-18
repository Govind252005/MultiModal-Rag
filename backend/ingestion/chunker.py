"""
Enterprise Multilingual Document Chunker & Unicode Sentence Segmenter (Phase 4.2).

Supports:
- English, Latin, Germanic, Romance punctuation: . ! ?
- Hindi & Sanskrit Devanagari punctuation: । (U+0964 Danda), ॥ (U+0965 Double Danda)
- Arabic / Urdu punctuation: ؟ (U+061F), ۔ (U+06D4)
- CJK (Chinese, Japanese) punctuation: 。 (U+3002), ！ (U+FF01), ？ (U+FF1F)
- Unicode closing quotation marks and brackets: " ' ” “ ’ » ) ] }
- Abbreviation and decimal number protection.
- Preservation of Markdown headings, table blocks (| ... |), and paragraph boundaries.
- Configurable window size and overlap with sentence integrity preservation.
"""

from __future__ import annotations

import re
import unicodedata
from typing import List, Tuple

import numpy as np

from backend import config

# Terminal sentence characters across supported writing systems
_TERMINAL_PUNCT = {
    ".", "!", "?",
    "\u0964",  # । Hindi Danda
    "\u0965",  # ॥ Hindi Double Danda
    "\u061F",  # ؟ Arabic question mark
    "\u06D4",  # ۔ Arabic full stop
    "\u3002",  # 。 CJK full stop
    "\uFF01",  # ！ Fullwidth exclamation
    "\uFF1F",  # ？ Fullwidth question mark
    "\u0589",  # ։ Armenian full stop
    "\u1362",  # ። Ethiopic full stop
}

# Closing quotes/brackets that can follow a terminal punctuation mark
_CLOSING_DELIMS = {'"', "'", "”", "’", "»", ")", "]", "}", "）", "】", "”"}

# Standard abbreviations that should not trigger sentence boundaries
_COMMON_ABBREVIATIONS = {
    "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "vs", "inc", "ltd", "corp",
    "co", "e.g", "i.e", "approx", "dept", "govt", "jan", "feb", "mar", "apr",
    "aug", "sept", "oct", "nov", "dec", "no", "vol", "p", "pp", "al", "etc",
    "ph.d", "m.sc", "b.tech", "m.tech", "u.s", "u.k", "u.n", "e.u", "p.m", "a.m",
}


def _is_table_row(line: str) -> bool:
    """Check if a line represents a Markdown or text table row."""
    stripped = line.strip()
    return stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 2


def _is_code_like(text: str) -> bool:
    """Detect source code blocks that should remain atomic and not be split on periods."""
    stripped = text.strip()
    return bool(re.search(
        r"(?:#include|using\s+namespace|int\s+main|void\s+main|def\s+\w+\s*\(|class\s+\w+|public\s+static|std::|cout\s*<<|cin\s*>>|System\.out\.println)",
        stripped
    )) or (stripped.count("{") > 0 and stripped.count("{") == stripped.count("}"))


def _is_heading(line: str) -> bool:
    """Check if a line represents a Markdown heading or short section label."""
    stripped = line.strip()
    if stripped.startswith("#"):
        return True
    # Short lines with colon at end or all caps title
    if len(stripped.split()) <= 6 and (stripped.endswith(":") or (stripped.isupper() and len(stripped) > 3)):
        return True
    return False


def _split_unicode_sentences(text: str) -> List[str]:
    """Segment a paragraph into clean sentences using Unicode boundary rules."""
    text = (text or "").strip()
    if not text:
        return []

    # If it's a table block, preserve all rows together
    lines = text.splitlines()
    if len(lines) > 1 and all(_is_table_row(l) for l in lines if l.strip()):
        return [text]

    # If it's a code block, preserve the code block intact
    if _is_code_like(text):
        return [text]
    if len(lines) > 1 and all(_is_table_row(l) for l in lines if l.strip()):
        return [text]

    sentences: List[str] = []
    n = len(text)
    start = 0
    i = 0

    while i < n:
        char = text[i]

        if char in _TERMINAL_PUNCT:
            # Check decimal numbers: e.g. "3.14" or "10.5%"
            if char == "." and i > 0 and i + 1 < n and text[i - 1].isdigit() and text[i + 1].isdigit():
                i += 1
                continue

            # Check abbreviations: inspect preceding word
            if char == ".":
                # Look backwards for word start
                w_start = i - 1
                while w_start >= 0 and (text[w_start].isalnum() or text[w_start] == "."):
                    w_start -= 1
                word = text[w_start + 1:i].lower()
                if word in _COMMON_ABBREVIATIONS:
                    i += 1
                    continue
                # Single letter initials: e.g. "John F. Kennedy" or "A. Smith"
                if len(word) == 1 and word.isalpha():
                    i += 1
                    continue

            # Include any immediately following closing quotes or brackets
            j = i + 1
            while j < n and text[j] in _CLOSING_DELIMS:
                j += 1

            # For Latin period '.', if followed by a lowercase letter after spaces, not a boundary (e.g. "approx. 5 miles in the...")
            if char == "." and j < n:
                k = j
                while k < n and (text[k].isspace() or text[k] in _CLOSING_DELIMS):
                    k += 1
                if k < n and text[k].islower():
                    i += 1
                    continue

            # Sentence boundary is valid if followed by whitespace or EOF
            if j >= n or text[j].isspace():
                sent = text[start:j].strip()
                if sent:
                    sentences.append(sent)
                # Skip whitespace to next sentence start
                while j < n and text[j].isspace():
                    j += 1
                start = j
                i = j
                continue

        i += 1

    # Add any remaining tail
    if start < n:
        tail = text[start:].strip()
        if tail:
            sentences.append(tail)

    return sentences if sentences else [text]


def _partition_structural_blocks(text: str) -> List[str]:
    """Split text into structural blocks (paragraphs, tables, headings)."""
    raw_blocks = re.split(r"\n\s*\n+", (text or "").strip())
    blocks: List[str] = []

    for b in raw_blocks:
        b = b.strip()
        if not b:
            continue
        # Check if block contains both a heading and a body
        lines = b.splitlines()
        if len(lines) > 1 and _is_heading(lines[0]):
            # Keep heading attached to following content or separate cleanly
            heading = lines[0].strip()
            rest = "\n".join(lines[1:]).strip()
            if rest:
                blocks.append(f"{heading}\n{rest}")
            else:
                blocks.append(heading)
        else:
            blocks.append(b)

    # Coalesce adjacent code-like blocks (e.g. helper function + int main()) up to 320 words
    coalesced_blocks: List[str] = []
    for b in blocks:
        if coalesced_blocks and _is_code_like(coalesced_blocks[-1]) and _is_code_like(b):
            combined = coalesced_blocks[-1] + "\n\n" + b
            if len(combined.split()) <= 320:
                coalesced_blocks[-1] = combined
                continue
        coalesced_blocks.append(b)

    return coalesced_blocks


def _pack_sentences(
    sentences: List[str],
    size: int,
    overlap: int,
) -> List[str]:
    """Pack segmented sentences into coherent chunks respecting word limits and overlap."""
    if not sentences:
        return []

    chunks: List[str] = []
    current_sentences: List[str] = []
    current_word_count = 0

    for s in sentences:
        words = s.split()
        w_count = len(words)

        # Handle massive run-on sentences larger than target chunk size
        if w_count > size:
            if current_sentences:
                chunks.append(" ".join(current_sentences))
                current_sentences = []
                current_word_count = 0

            # Sub-split long sentence on commas/clauses or word windows
            sub_step = max(1, size - overlap)
            for start_idx in range(0, w_count, sub_step):
                sub_win = words[start_idx:start_idx + size]
                if sub_win:
                    chunks.append(" ".join(sub_win))
                if start_idx + size >= w_count:
                    break
            continue

        if current_word_count + w_count > size and current_sentences:
            chunks.append(" ".join(current_sentences))

            # Calculate overlap sentences to carry forward
            if overlap > 0:
                overlap_sentences: List[str] = []
                overlap_words = 0
                for prev_s in reversed(current_sentences):
                    pw = len(prev_s.split())
                    if overlap_words + pw <= overlap:
                        overlap_sentences.insert(0, prev_s)
                        overlap_words += pw
                    else:
                        break
                current_sentences = list(overlap_sentences)
                current_word_count = overlap_words
            else:
                current_sentences = []
                current_word_count = 0

        current_sentences.append(s)
        current_word_count += w_count

    if current_sentences:
        chunks.append(" ".join(current_sentences))

    return chunks


def _semantic_chunks(
    text: str,
    max_words: int,
    min_words: int,
    sim_threshold: float,
) -> List[str]:
    """Cluster sentences into semantically cohesive passages."""
    text = (text or "").strip()
    if not text:
        return []

    blocks = _partition_structural_blocks(text)
    sentences: List[str] = []
    for block in blocks:
        sentences.extend(_split_unicode_sentences(block))

    if len(sentences) <= 1:
        return [text]

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

        min_w = min(min_words, max(3, max_words // 2))
        would_exceed = (cur_words + w) > max_words
        semantic_break = sim < sim_threshold and cur_words >= min_w

        if would_exceed or semantic_break:
            flush()

        cur_sentences.append(s)
        cur_vecs.append(v)
        cur_words += w

    flush()

    min_w = min(min_words, max(3, max_words // 2))
    safe: List[str] = []
    for c in chunks:
        if len(c.split()) < min_w and safe:
            safe[-1] = safe[-1] + " " + c
        else:
            safe.append(c)
    return safe


def _chunk_table_block(block: str, max_words: int = 280) -> List[str]:
    """Split a large Markdown table into chunks while propagating column headers to every chunk."""
    b_lines = [l.strip() for l in block.splitlines() if l.strip()]
    meta_prefix = "\n".join([l for l in b_lines if l.startswith("[") and l.endswith("]")])
    if meta_prefix:
        meta_prefix += "\n"
    table_rows = [l for l in b_lines if _is_table_row(l)]
    if len(table_rows) < 2:
        return [block]

    hdr = table_rows[0]
    sep = table_rows[1] if "---" in table_rows[1] else ("| " + " | ".join(["---"] * max(1, hdr.count("|") - 1)) + " |")
    data_rows = table_rows[2:] if "---" in table_rows[1] else table_rows[1:]

    if len(block.split()) > max_words and len(data_rows) > 1:
        chunks: List[str] = []
        cur_rows: List[str] = []
        cur_w = len((meta_prefix + hdr + "\n" + sep).split())
        for dr in data_rows:
            rw = len(dr.split())
            if cur_rows and (cur_w + rw > max_words):
                chunk_str = f"{meta_prefix}{hdr}\n{sep}\n" + "\n".join(cur_rows)
                chunks.append(chunk_str)
                cur_rows = [dr]
                cur_w = len((meta_prefix + hdr + "\n" + sep).split()) + rw
            else:
                cur_rows.append(dr)
                cur_w += rw
        if cur_rows:
            chunk_str = f"{meta_prefix}{hdr}\n{sep}\n" + "\n".join(cur_rows)
            chunks.append(chunk_str)
        return chunks
    return [block]


def chunk_text(
    text: str,
    size: int = config.CHUNK_SIZE_WORDS,
    overlap: int = config.CHUNK_OVERLAP_WORDS,
) -> List[str]:
    """Primary chunking entry point with Unicode and structure awareness."""
    text = (text or "").strip()
    if not text:
        return []

    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if lines and (_is_table_row(lines[0]) or any(_is_table_row(l) for l in lines[:3])):
        return _chunk_table_block(text, max_words=280)

    if config.CHUNKING_STRATEGY == "semantic":
        try:
            return _semantic_chunks(
                text=text,
                max_words=size,
                min_words=config.SEMANTIC_MIN_WORDS,
                sim_threshold=config.SEMANTIC_SIM_THRESHOLD,
            )
        except Exception:
            pass

    # Standard Unicode-aware sentence packing
    blocks = _partition_structural_blocks(text)
    all_chunks: List[str] = []

    for block in blocks:
        b_lines = [l.strip() for l in block.splitlines() if l.strip()]
        if b_lines and (_is_table_row(b_lines[0]) or any(_is_table_row(l) for l in b_lines[:3])):
            all_chunks.extend(_chunk_table_block(block, max_words=280))
        elif _is_code_like(block) and len(block.split()) <= 320:
            all_chunks.append(block)
        else:
            sentences = _split_unicode_sentences(block)
            packed = _pack_sentences(sentences, size=size, overlap=overlap)
            all_chunks.extend(packed)

    return all_chunks if all_chunks else [text]
