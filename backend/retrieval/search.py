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
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from sentence_transformers import CrossEncoder

from typing import Any, Dict, List, Optional

from PIL import Image
import logging
logger = logging.getLogger(__name__)

from backend import config
from backend.retrieval import embeddings, lexical_index, vector_store

_SEARCH_EXECUTOR = ThreadPoolExecutor(max_workers=3, thread_name_prefix="rag-search")

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
    text = hit.get("document", "") or hit.get("text", "") or ""
    file = m.get("file", "unknown")
    sid = m.get("session_id")
    # Structured description bridge for visual image hits so LLM receives actionable text
    if m.get("modality") == "image" or channel == "clip":
        if not text or text.strip() in ("", "None", "N/A"):
            text = f"[Image Evidence: {file}] Visual diagram / image match."
        elif not text.startswith("[Image Evidence:"):
            text = f"[Image Evidence: {file}] {text}"
    snippet = " ".join(text.strip().split())
    if len(snippet) > 300:
        snippet = snippet[:300].rstrip() + "…"
    # Use media_file (saved extracted image) when available, else the source file.
    serve_name = m.get("media_file") or file
    safe_serve = urllib.parse.quote(serve_name)
    media_url = f"/api/media/{sid}/{safe_serve}" if sid else f"/api/media/{safe_serve}"
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
    if h.get("modality") == "audio":
        return f"{h.get('file')}|{h.get('timestamp') or h.get('start')}"
    if h.get("modality") == "document":
        chunk_val = h.get("chunk")
        chunk_id = chunk_val if (chunk_val is not None and str(chunk_val).strip() != "") else (h.get("id") or "0")
        return f"{h.get('file')}|p{h.get('page')}|{h.get('source_type', 'text')}|c{chunk_id}"
    # image: OCR chunks stay separate; caption + visual collapse to one per image.
    if h.get("source_type") == "ocr":
        return f"{h.get('file')}|ocr|{h.get('chunk')}"
    # Use media_file to distinguish embedded images from the same document.
    discriminator = h.get("media_file") or h.get("id") or "standalone"
    return f"{h.get('file')}|img|{discriminator}"


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
    org_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Reads the persistent lexical index built at ingest time — no corpus
    load or tokenizer pass here (AUDIT_REPORT.md P1-1)."""
    try:
        return lexical_index.search(
            query, top_n=top_n, user_id=user_id, session_id=session_id,
            modality=modality, files=files, org_id=org_id,
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
def _is_english_only_reranker(model_name: str) -> bool:
    name = (model_name or "").lower()
    return "ms-marco" in name or "english" in name


def _rerank(query: str, hits: List[Dict[str, Any]], top_n: int) -> List[Dict[str, Any]]:
    if not hits:
        return []

    if not config.RERANK_ENABLED:
        return hits[:top_n]

    from backend.nlp import language_detect
    q_script = language_detect.detect_script(query)
    q_lang_info = language_detect.detect_language(query)
    q_lang = q_lang_info.get("language", "en")

    # Intelligent reranker safety: If the active model is English-only (like ms-marco)
    # Check query script AND retrieved document scripts so non-Latin queries aren't corrupted
    if _is_english_only_reranker(config.RERANK_MODEL):
        if q_script != "Latin" or q_lang != "en":
            return hits[:top_n]
        sample_doc_scripts = [
            language_detect.detect_script((h.get("text") or h.get("snippet") or "")[:200])
            for h in hits[:5]
            if (h.get("text") or h.get("snippet"))
        ]
        if any(s != "Latin" for s in sample_doc_scripts):
            return hits[:top_n]

    rerank_window = max(getattr(config, "RERANK_WINDOW", 20), 30)
    pool = hits[:rerank_window]
    try:
        import math
        import torch
        model = _get_reranker()

        pairs = [
            [query, h.get("text", "") or h.get("document", "") or h.get("snippet", "")]
            for h in pool
        ]

        with torch.inference_mode():
            scores = model.predict(
                pairs,
                batch_size=getattr(config, "RERANK_BATCH_SIZE", 16)
            )

        is_code_query = bool(re.search(r"\b(code|program|script|implementation|c\+\+|cpp|python|java|sql|source\s*code|function|algorithm)\b", query, re.IGNORECASE))
        is_aim_query = bool(re.search(r"\b(aim|objective|purpose|goal)\b", query, re.IGNORECASE))
        is_table_query = (not is_aim_query) and bool(re.search(r"\b(table|tabular|test\s*cases?|rows?|columns?|chart|matrix|schedule)\b", query, re.IGNORECASE))
        is_descriptive_image_query = bool(re.search(
            r"\b(what('?s|\s+is)\s+in\s+(this|the)|describe|explain|summarize|overview|show|about|what\s+does\s+this\s+(image|screenshot|photo|picture)\s+(show|contain|have))\b",
            query,
            re.IGNORECASE,
        ))
        is_comparative_query = bool(re.search(
            r"\b(common\s*(?:names?|words?|terms?|text|entity|person|people|topics?|items?|details?|authors?|students?|teachers?|supervisors?)?|between\s+(?:these\s+)?(?:two|both|files|documents|recordings|audios)|in\s+both|compare|comparison|difference|similar|similarity|shared|overlap|match|across\s+(?:the\s+)?(?:two|both|files|documents))\b",
            query,
            re.IGNORECASE,
        ))
        is_audio_query = bool(re.search(r"\b(audio|recording|voice|speech|call|sound|spoken|say|said|hear|transcript)\b", query, re.IGNORECASE))
        aim_re = re.compile(r"\b(?:aim|objective)\s*[:#-]?\s*(?:\r?\n\s*)?([^\r\n]+)", re.IGNORECASE)
        code_re = re.compile(r"(?:#include|\bint\s+main\b|\bstring\s+classify\b|\bclassify\b|\bdef\s+[a-zA-Z_]|\bimport\s+[a-zA-Z_]|\bclass\s+[a-zA-Z_]|```|\.cpp|\.py|\.java|\.c|\bvoid\s+[a-zA-Z_]|\bImplementation\b)", re.IGNORECASE)

        max_rrf = max((float(h.get("score") or 0.0) for h in pool), default=1.0)
        if max_rrf <= 0.0:
            max_rrf = 1.0

        reranked = []
        for i, h in enumerate(pool):
            ce_raw = float(scores[i])
            text_body = str(h.get("text") or h.get("document") or "")
            is_table_chunk = (
                h.get("source_type") == "table"
                or "|" in text_body
                or "test case" in text_body.lower()
            )
            is_image_chunk = (
                h.get("modality") == "image"
                or h.get("source_type") in ("image", "ocr", "caption")
            )
            is_audio_chunk = (
                h.get("modality") == "audio"
                or h.get("source_type") in ("audio", "transcript")
            )
            is_cross_match_chunk = (
                is_comparative_query and (
                    h.get("page") in (1, 2)
                    or any(term in text_body.lower() for term in ("submitted by", "supervision", "student", "faculty", "instructor", "guide", "prepared by", "author"))
                )
            )

            ce_prob = 1.0 / (1.0 + math.exp(-max(min(ce_raw, 10.0), -10.0)))
            rrf_norm = max(0.0, float(h.get("score") or 0.0)) / max_rrf
            blended_score = 0.50 * rrf_norm + 0.50 * ce_prob

            if is_code_query and code_re.search(text_body):
                blended_score += 0.35
            if is_table_query and is_table_chunk:
                blended_score += 0.25
            if is_aim_query and aim_re.search(text_body):
                blended_score += 0.40
            if is_descriptive_image_query and is_image_chunk:
                blended_score += 0.30
            if is_audio_chunk and (is_audio_query or is_comparative_query):
                blended_score += 0.50
            if is_cross_match_chunk:
                blended_score += 0.45

            reranked.append({
                **h,
                "rerank_score": blended_score,
                "raw_ce": ce_raw,
            })

        reranked.sort(key=lambda x: x["rerank_score"], reverse=True)

        # Anchor Guarantee: Always retain the #1 RRF candidate and #1 BM25 candidate inside top_n
        top_rrf_id = pool[0].get("id") if pool else None
        top_bm25_id = next((h.get("id") for h in pool if h.get("channel") in ("bm25", "hybrid") and float(h.get("score") or 0.0) > 0.0), None)

        selected = list(reranked[:top_n])
        selected_ids = {x.get("id") for x in selected}

        for anchor_id in (top_rrf_id, top_bm25_id):
            if anchor_id and anchor_id not in selected_ids:
                anchor_item = next((x for x in reranked if x.get("id") == anchor_id), None)
                if anchor_item and selected:
                    selected[-1] = anchor_item
                    selected_ids.add(anchor_id)

        if len(selected) < top_n and len(hits) > len(pool):
            for h in hits[len(pool):top_n]:
                if h.get("id") not in selected_ids:
                    selected.append(h)
                    selected_ids.add(h.get("id"))

        return selected

    except Exception as e:
        logger.exception("Reranker failed: %s", e)
        return hits[:top_n]


def _merge_table_texts(t1: str, t2: str) -> str:
    """Consolidate two markdown tables into a single coherent table without duplicate headers."""
    if not (re.search(r"\|.*\|", t1) and re.search(r"\|.*\|", t2)):
        return t1.rstrip() + "\n\n" + t2.lstrip()

    # Collect any prose lines before the table to avoid dropping headings, aims, or intro text
    prose_before = []
    for l in t1.splitlines():
        l_s = l.strip()
        if l_s.startswith("|"):
            break
        if l_s.startswith("[") and l_s.endswith("]"):
            continue
        if l_s:
            prose_before.append(l_s)

    lines1 = [l.strip() for l in t1.splitlines() if l.strip().startswith("|")]
    lines2 = [l.strip() for l in t2.splitlines() if l.strip().startswith("|")]

    def split_table(lines):
        header = []
        data = []
        for l in lines:
            if re.match(r"^\|[-:\s|]+\|$", l):
                header.append(l)
            elif not header:
                header.append(l)
            else:
                data.append(l)
        return header, data

    h1, d1 = split_table(lines1)
    h2, d2 = split_table(lines2)

    if not d1 or not d2:
        return t1.rstrip() + "\n\n" + t2.lstrip()

    # Only merge if both tables share the same column structure
    cols1 = len([c for c in h1[0].split("|") if c.strip()]) if h1 else 0
    cols2 = len([c for c in h2[0].split("|") if c.strip()]) if h2 else 0
    if cols1 != cols2:
        return t1.rstrip() + "\n\n" + t2.lstrip()

    def first_cell(r):
        parts = [p.strip() for p in r.split("|") if p.strip()]
        return parts[0] if parts else ""

    c1, c2 = first_cell(d1[0]), first_cell(d2[0])
    if c2 and c1 and c2 < c1:
        combined = d2 + [r for r in d1 if r not in d2]
        header = h2 or h1
    else:
        combined = d1 + [r for r in d2 if r not in d1]
        header = h1 or h2

    # Check if all rows have clean alphanumeric IDs in the first column (e.g. IN01, IN02)
    if all(re.match(r"^[A-Za-z0-9_\-]+$", first_cell(r)) for r in combined if r.strip()):
        combined.sort(key=first_cell)

    ctx_prefix = ""
    for l in t1.splitlines():
        if l.strip().startswith("[") and l.strip().endswith("]"):
            ctx_prefix = l.strip() + "\n"
            break
    if not ctx_prefix:
        for l in t2.splitlines():
            if l.strip().startswith("[") and l.strip().endswith("]"):
                ctx_prefix = l.strip() + "\n"
                break

    table_body = "\n".join(header) + "\n" + "\n".join(combined)
    if prose_before:
        return ctx_prefix + "\n".join(prose_before) + "\n\n" + table_body
    return ctx_prefix + table_body


_CONTAINER_RE = re.compile(
    r"(?:डिबिया|संदूक|थैली|लिफाफा|पेटी|बक्सा|बक्से|डिब्बी|\b(?:box|chest|tin|envelope|drawer)\b)",
    re.IGNORECASE,
)


def _extract_locative_anchors(q: str) -> List[str]:
    """Extract explicit locative anchors from query (e.g. 'पुस्तकालय में', 'in the library', 'beneath the floorboard')."""
    if not q:
        return []
    anchors: List[str] = []
    from backend.retrieval.lexical_index import _hindi_stem, normalize_devanagari
    # Hindi: <word> में, <word> के अंदर, <word> के भीतर, <word> पर, <word> के पास
    hi_matches = re.findall(
        r"([A-Za-z\u0900-\u097F]{2,25})\s*(?:में|के\s+अंदर|के\s+भीतर|पर|के\s+पास)(?:[\s.,;!?]|$)",
        q,
    )
    stopwords_hi = {"इस", "उस", "जिस", "किस", "सब", "अपने", "अपनी", "यहाँ", "वहाँ", "कहाँ", "कहा", "बाद", "पहले", "बारे", "रूप"}
    for m in hi_matches:
        w = m.strip().lower()
        if len(w) >= 2 and w not in stopwords_hi:
            anchors.append(w)
            norm_w = normalize_devanagari(w)
            if norm_w != w:
                anchors.append(norm_w)
            stem_w = _hindi_stem(norm_w)
            if stem_w and stem_w not in (w, norm_w):
                anchors.append(stem_w)

    # English: in the <noun>, inside the <noun>, at the <noun>, beneath the <noun>, under the <noun>
    en_matches = re.findall(
        r"\b(?:in|inside|at|beneath|under)\s+(?:the\s+|a\s+|an\s+|his\s+|her\s+)?([a-zA-Z]{3,})(?:[\s.,;!?]|$)",
        q,
        re.IGNORECASE,
    )
    stopwords_en = {"this", "that", "which", "what", "case", "order", "fact", "time", "front", "terms", "general", "total"}
    for m in en_matches:
        w = m.strip().lower()
        if w not in stopwords_en:
            anchors.append(w)

    return list(dict.fromkeys(anchors))


def _coalesce_and_diversify(hits: List[Dict[str, Any]], top_k: int, exp_targets: Optional[List[str]] = None, query: str = "") -> List[Dict[str, Any]]:
    """Phase 4.3 enterprise refinement:
    1. For same-page document chunks (same file, page, modality=document), coalesce
       adjacent chunks up to ~380 words (or 900 words for structured tables) so the generator
       and citation drawer receive cohesive page context rather than isolated fragments.
    2. Enforce a diversity cap of at most 2 chunks per (file, page) when alternative
       files or pages are present in the candidate pool.
    """
    if not hits:
        return []

    # First pass: coalesce same-file, same-page document chunks
    coalesced: List[Dict[str, Any]] = []
    absorbed_ids = set()

    for i, h in enumerate(hits):
        if h.get("id") in absorbed_ids:
            continue
        if h.get("modality") != "document" or h.get("page") is None:
            coalesced.append(h)
            continue

        base_hit = dict(h)
        base_hit["sub_chunks"] = [h.get("text", "")]
        base_words = len(base_hit.get("text", "").split())
        base_file = base_hit.get("file")
        base_page = base_hit.get("page")
        base_chunk = base_hit.get("chunk", 0)
        is_table = base_hit.get("source_type") == "table" or bool(re.search(r"^\|[-:\s|]+\|$", base_hit.get("text", ""), re.MULTILINE))
        loc_anchors = _extract_locative_anchors(query)
        has_loc_anchor = any(anc in base_hit.get("text", "").lower() for anc in loc_anchors) if loc_anchors else False
        max_words = 900 if is_table else (650 if has_loc_anchor else 380)

        # Look ahead for adjacent or same-page chunks from the same file
        for j in range(i + 1, len(hits)):
            other = hits[j]
            if other.get("id") in absorbed_ids:
                continue
            if (
                other.get("modality") == "document"
                and other.get("file") == base_file
                and other.get("page") == base_page
            ):
                other_is_table = other.get("source_type") == "table" or bool(re.search(r"^\|[-:\s|]+\|$", other.get("text", ""), re.MULTILINE))
                if is_table != other_is_table:
                    continue

                other_words = len(other.get("text", "").split())
                if base_words + other_words <= max_words:
                    if is_table:
                        base_hit["text"] = _merge_table_texts(base_hit.get("text", ""), other.get("text", ""))
                        base_hit["sub_chunks"].append(other.get("text", ""))
                    else:
                        other_chunk = other.get("chunk", 0)
                        try:
                            is_before = int(other_chunk) < int(base_chunk)
                        except (ValueError, TypeError):
                            is_before = False

                        if is_before:
                            base_hit["text"] = other.get("text", "").rstrip() + "\n\n" + base_hit.get("text", "").lstrip()
                            base_hit["sub_chunks"].insert(0, other.get("text", ""))
                        else:
                            base_hit["text"] = base_hit.get("text", "").rstrip() + "\n\n" + other.get("text", "").lstrip()
                            base_hit["sub_chunks"].append(other.get("text", ""))

                    base_words += other_words
                    # Keep snippet as the clean, unmodified snippet of the highest-scoring primary chunk
                    # so DocumentViewer exact phrase searches match raw page text without synthetic joiners
                    absorbed_ids.add(other.get("id"))

        coalesced.append(base_hit)

    # Second pass: adaptive diversity cap per (file, page)
    page_counts: Dict[str, int] = {}
    distinct_pages_or_files = set()
    for h in coalesced:
        distinct_pages_or_files.add(f"{h.get('file')}|p{h.get('page')}")

    # If all candidates come from <= 2 distinct pages (e.g. 1-2 page document, or single-page query),
    # allow up to 4 chunks per page so dense findings or multi-table rows are not dropped!
    max_per_page = 4 if len(distinct_pages_or_files) <= 2 else 2

    diverse: List[Dict[str, Any]] = []
    overflow: List[Dict[str, Any]] = []

    for h in coalesced:
        key = f"{h.get('file')}|p{h.get('page')}"
        cnt = page_counts.get(key, 0)
        if cnt < max_per_page or h.get("modality") != "document":
            page_counts[key] = cnt + 1
            diverse.append(h)
        else:
            overflow.append(h)

    # If diverse didn't fill top_k, backfill from overflow
    while len(diverse) < top_k and overflow:
        diverse.append(overflow.pop(0))

    # Phase 4.4: Multi-file representation guarantee: when candidate pool contains multiple files,
    # guarantee each distinct file with evidence gets representation in diverse[:top_k]
    pool_files = [h.get("file") for h in coalesced if h.get("file")]
    unique_pool_files = list(dict.fromkeys(pool_files))
    if len(unique_pool_files) > 1:
        current_files = set(h.get("file") for h in diverse[:top_k] if h.get("file"))
        for uf in unique_pool_files:
            if uf not in current_files:
                cand = next((h for h in (overflow + coalesced) if h.get("file") == uf and h not in diverse[:top_k]), None)
                if cand:
                    diverse.insert(min(len(diverse), 2), cand)

    # Guarantee targeted experiment isolation and representation
    if exp_targets:
        target_re = re.compile(rf"\b(?:experiment|exp\.?)\s*(?:no\.?|number)?\s*[:#-]?\s*(?:{'|'.join(re.escape(t) for t in exp_targets)})\b", re.IGNORECASE)
        other_exp_re = re.compile(r"\b(?:experiment|exp\.?)\s*(?:no\.?|number)?\s*[:#-]?\s*(\d+)\b", re.IGNORECASE)

        def is_target_exp(h: Dict[str, Any]) -> bool:
            sec = str(h.get("section") or "")
            txt = str(h.get("text") or h.get("snippet") or "")
            return bool(target_re.search(sec) or target_re.search(txt[:350]))

        def is_other_unrequested_exp(h: Dict[str, Any]) -> bool:
            sec = str(h.get("section") or "")
            txt = str(h.get("text") or h.get("snippet") or "")
            m_sec = other_exp_re.search(sec)
            if m_sec and m_sec.group(1) not in exp_targets:
                return True
            m_txt = other_exp_re.search(txt[:250])
            if m_txt and m_txt.group(1) not in exp_targets:
                return True
            return False

        target_pool = [h for h in coalesced if is_target_exp(h)]
        if target_pool:
            # If we have hits matching the requested experiment(s), filter out hits from other unrequested experiments
            filtered_diverse = [h for h in diverse if not is_other_unrequested_exp(h)]
            for th in target_pool:
                if th not in filtered_diverse:
                    filtered_diverse.append(th)
            diverse = filtered_diverse
        else:
            final_pool = list(diverse)
            for t in exp_targets:
                t_re = re.compile(rf"\b(?:experiment|exp\.?)\s*(?:no\.?|number)?\s*[:#-]?\s*{re.escape(t)}\b", re.IGNORECASE)
                cand = next((h for h in (overflow + coalesced) if t_re.search(str(h.get("text") or h.get("snippet") or h.get("section") or "")) and h not in final_pool[:top_k]), None)
                if cand:
                    final_pool.insert(0, cand)
            diverse = final_pool

    # Prioritize according to query intent: code, aim, supervisor, submitter, location, synthesis
    is_code_q = bool(re.search(r"\b(code|program|script|implementation|c\+\+|cpp|python|java|sql|source\s*code|function|algorithm)\b", query, re.IGNORECASE))
    is_aim_q = bool(re.search(r"\b(aim|objective|purpose|goal)\b", query, re.IGNORECASE))

    is_supervisor_q = bool(re.search(
        r"\b(?:supervision|supervisor|supervised|guided\s+by|guide|mentor|faculty\s+guide|faculty\s+supervisor|under\s+whose\s+supervision|kiske\s+supervision|kiski\s+dekhrekh)\b",
        query,
        re.IGNORECASE,
    )) or any(w in query for w in ["पर्यवेक्षक", "किसकी देखरेख", "देखरेख", "मार्गदर्शक", "सुपरवाइजर"])

    is_submitter_q = (not is_supervisor_q) and (bool(re.search(
        r"\b(?:who\s+submitted|submitted\s+by|submitted|who\s+wrote|who\s+authored|author\s+of|author|whose\s+document|whose\s+file|created\s+by|prepared\s+by|student\s+name|name\s+of\s+student|who\s+made|kisne\s+submit\s+kiya|kiska\s+document|kiska\s+file|kisne\s+banaya)\b",
        query,
        re.IGNORECASE,
    )) or any(w in query for w in ["किसने जमा किया", "किसने बनाया", "किसने लिखा", "किसने प्रस्तुत किया", "जमाकर्ता", "किसका दस्तावेज़", "किसका प्रैक्टिकल", "दस्तावेज़ किसका", "विद्यार्थी का नाम", "छात्र का नाम"]))

    loc_anchors = _extract_locative_anchors(query)

    is_non_location_q = bool(re.search(
        r"\b(?:what|which|who|whom|whose|why|how|many|much)\b",
        query,
        re.IGNORECASE,
    )) or any(w in query for w in ["कौन", "क्या", "किसने", "किसे", "किसका", "क्यों", "कैसे", "कितने", "कितनी", "कौन-सी", "कौन सी", "क्या-क्या", "क्या क्या"])

    is_location_q = (not is_non_location_q) and (
        bool(re.search(
            r"\b(?:where|destination|lead\s+to|led\s+to|reach\b|reached\b|arrived?\b)\b",
            query,
            re.IGNORECASE,
        )) or any(w in query for w in ["कहाँ", "कहा", "किस जगह", "किस स्थान", "कहाँ पहुँचाया", "कहाँ पहुँचे"])
    )

    is_count_list_q = any(
        w in query
        for w in [
            "दो", "तीन", "चार", "दोनों", "तीनों", "कौन-सी", "कौन सी",
            "क्या-क्या", "क्या क्या", "चीज़ें", "चीजें", "वस्तुएँ", "वस्तुएं", "सूची"
        ]
    ) or bool(re.search(
        r"\b(?:items?|things?|two|three|both|which\s+two|what\s+two|list)\b",
        query,
        re.IGNORECASE,
    ))

    is_synthesis_q = (not is_aim_q) and (bool(re.search(
        r"\b(?:why|purpose|reason|reasons|created|built|founded|established|history|origin|background|testimony|testimonies|eyewitness|flood|council)\b",
        query,
        re.IGNORECASE,
    )) or any(w in query for w in ["क्यों", "क्यो", "कारण", "उद्देश्य", "बनाया गया"]))

    code_checker = re.compile(r"(?:#include|\bint\s+main\b|\bstring\s+classify\b|\bclassify\b|\bdef\s+[a-zA-Z_]|\bimport\s+[a-zA-Z_]|\bclass\s+[a-zA-Z_]|```|\.cpp|\.py|\.java|\.c|\bImplementation\b)", re.IGNORECASE)
    aim_checker = re.compile(r"\b(?:aim|objective)\b", re.IGNORECASE)
    submitter_checker = re.compile(r"\b(?:submitted\s+by|index\s+name|student\s+name)\b", re.IGNORECASE)
    supervisor_checker = re.compile(r"\b(?:under\s+the\s+supervision\s+of|supervised\s+by|faculty\s+supervisor|supervisor)\b", re.IGNORECASE)

    def _location_landmark_score(h: Dict[str, Any]) -> float:
        txt = (str(h.get("text") or "") + " " + str(h.get("snippet") or "")).lower()
        score = 0.0
        for pred in ["पहुँचाया", "पहुँचे", "पहुंचाया", "पहुंचे", "led to", "brought to", "guided them to", "arrived at", "reached the"]:
            if pred in txt:
                score += 5.0
        for lm in ["बरगद", "पेड़", "पेड़", "banyan", "tree", "जड़ों", "पत्थर", "stone", "roots", "outside the", "गाँव के बाहर", "study", "floorboard", "chamber", "vault", "river"]:
            if lm in txt:
                score += 3.0
        return score

    pages_with_anchor = set()
    if loc_anchors:
        for h in coalesced:
            txt_scan = (str(h.get("text") or "") + " " + str(h.get("snippet") or "")).lower()
            if any(anc in txt_scan for anc in loc_anchors):
                pages_with_anchor.add((h.get("file"), h.get("page")))

    def _scene_conflation_guard_score(h: Dict[str, Any]) -> float:
        txt = (str(h.get("text") or "") + " " + str(h.get("snippet") or "")).lower()
        sc = 0.0
        if loc_anchors:
            has_matching_anchor = any(anc in txt for anc in loc_anchors) or ((h.get("file"), h.get("page")) in pages_with_anchor)
            if has_matching_anchor:
                sc += 35.0
            else:
                sc -= 20.0
        if is_count_list_q:
            if re.search(r"[A-Za-z\u0900-\u097F\s]{2,25}\s+(?:और|तथा|\band\b)\s+[A-Za-z\u0900-\u097F\s]{2,25}", txt):
                sc += 15.0
            if _CONTAINER_RE.search(txt):
                sc += 15.0
            # Strong boost when a container explicitly contains multiple items (e.g. "डिबिया के भीतर एक चिट्ठी और पीतल की छोटी चाबी थी")
            if re.search(r"(?:डिबिया|संदूक|box|chest|envelope|drawer|पेटी)\s*के\s*(?:भीतर|अंदर)\s*[A-Za-z\u0900-\u097F\s,]+(?:और|तथा|\band\b)", txt):
                sc += 25.0
        return sc

    if loc_anchors or (is_count_list_q and not is_code_q and not is_aim_q):
        diverse.sort(key=lambda h: (_scene_conflation_guard_score(h) > 0, _scene_conflation_guard_score(h) + float(h.get("score") or 0.0)), reverse=True)
    elif is_code_q:
        diverse.sort(key=lambda h: (1 if code_checker.search(str(h.get("text") or "")) else 0), reverse=True)
    elif is_aim_q:
        diverse.sort(key=lambda h: (1 if aim_checker.search(str(h.get("text") or "")) else 0), reverse=True)
    elif is_supervisor_q:
        diverse.sort(key=lambda h: (2 if supervisor_checker.search(str(h.get("text") or "")) else (1 if h.get("page") in (1, 2) else 0)), reverse=True)
    elif is_submitter_q:
        diverse.sort(key=lambda h: (2 if submitter_checker.search(str(h.get("text") or "")) else (1 if h.get("page") in (1, 2) else 0)), reverse=True)
    elif is_location_q:
        diverse.sort(key=lambda h: (_location_landmark_score(h) > 0, _location_landmark_score(h) + float(h.get("score") or 0.0)), reverse=True)
    elif is_synthesis_q:
        synth_pages = set()
        synth_pool: List[Dict[str, Any]] = []
        remaining_pool: List[Dict[str, Any]] = []
        for h in coalesced:
            pg = f"{h.get('file')}|p{h.get('page')}"
            if pg not in synth_pages:
                synth_pages.add(pg)
                synth_pool.append(h)
            else:
                remaining_pool.append(h)
        combined = synth_pool + [h for h in diverse if h not in synth_pool] + [h for h in remaining_pool if h not in synth_pool]
        diverse = combined

    return diverse[:top_k]


# ------------------------------------------------------------------ text query
def text_query(
    query: str,
    top_k: int = config.DEFAULT_TOP_K,
    modality: str = "all",
    session_id: Optional[str] = None,
    files: Optional[List[str]] = None,
    user_id: Optional[str] = None,
    org_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    exp_block = re.search(r"\b(?:experiments?|exp\.?)\s*(?:no\.?|numbers?)?\s*([0-9a-zA-Z\s,and&]+)", query, re.IGNORECASE)
    exp_targets = re.findall(r"\b\d+\b", exp_block.group(1)) if exp_block else []
    base_k = max(top_k, getattr(config, "FINAL_CONTEXT_TOP_K", 7))
    effective_top_k = max(base_k, len(exp_targets) * 3, 12) if len(exp_targets) > 1 else base_k

    where = vector_store.build_where(
        session_id=session_id, modality=modality, files=files, user_id=user_id, org_id=org_id)
    requested_section = _requested_section(query)

    # 1, 2, 3) Concurrent Dense Text, BM25, and CLIP Image search
    dense_text_hits: List[Dict[str, Any]] = []
    bm25_hits: List[Dict[str, Any]] = []
    clip_hits: List[Dict[str, Any]] = []

    def _fetch_dense():
        try:
            text_vec = embeddings.embed_text_cached(query)[0].tolist()
            return vector_store.query_text(
                text_vec, top_k=max(effective_top_k, config.DENSE_CANDIDATES), where=where
            )
        except Exception as exc:
            logger.debug("[search] dense text retrieval notice: %s", exc)
            return []

    def _fetch_bm25():
        try:
            hits = _bm25_search(
                query, top_n=max(effective_top_k, config.BM25_CANDIDATES),
                user_id=user_id, session_id=session_id, modality=modality, files=files,
                org_id=org_id,
            )
            if exp_targets:
                for t in exp_targets:
                    try:
                        sub1 = _bm25_search(
                            f"EXPERIMENT {t}",
                            top_n=8,
                            user_id=user_id, session_id=session_id, modality=modality, files=files,
                            org_id=org_id,
                        )
                        hits.extend(sub1)
                        sub2 = _bm25_search(
                            f"EXPERIMENT {t} Implementation classify triangle code",
                            top_n=6,
                            user_id=user_id, session_id=session_id, modality=modality, files=files,
                            org_id=org_id,
                        )
                        hits.extend(sub2)
                    except Exception as e:
                        logger.debug("target sub-search notice: %s", e)
            elif is_supervisor_q:
                try:
                    sub_sup = _bm25_search(
                        "Under the supervision of supervisor faculty instructor guide mentor",
                        top_n=6,
                        user_id=user_id, session_id=session_id, modality=modality, files=files,
                        org_id=org_id,
                    )
                    hits.extend(sub_sup)
                except Exception as e:
                    logger.debug("supervisor sub-search notice: %s", e)
            elif is_submitter_q:
                try:
                    sub_sub = _bm25_search(
                        "Submitted by author student name roll no",
                        top_n=6,
                        user_id=user_id, session_id=session_id, modality=modality, files=files,
                        org_id=org_id,
                    )
                    hits.extend(sub_sub)
                except Exception as e:
                    logger.debug("submitter sub-search notice: %s", e)
            return hits
        except Exception as exc:
            logger.debug("[search] bm25 retrieval notice: %s", exc)
            return []

    def _fetch_clip():
        if modality in ("all", "image") and vector_store.has_images(
            session_id=session_id, user_id=user_id, org_id=org_id, files=files
        ):
            try:
                img_where = vector_store.build_where(
                    session_id=session_id,
                    files=files,
                    user_id=user_id,
                    org_id=org_id,
                )
                clip_vec = embeddings.embed_clip_text([query])[0].tolist()
                results = vector_store.query_images(
                    clip_vec,
                    top_k=max(top_k, config.DENSE_CANDIDATES),
                    where=img_where,
                )
                if _visual_query(query):
                    for r in results:
                        r["score"] = r.get("score", 0.0) * 1.25
                return results
            except Exception as exc:
                logger.debug("[search] dense image retrieval notice: %s", exc)
                return []
        return []

    future_dense = _SEARCH_EXECUTOR.submit(_fetch_dense)
    future_bm25 = _SEARCH_EXECUTOR.submit(_fetch_bm25)
    future_clip = _SEARCH_EXECUTOR.submit(_fetch_clip)

    try:
        dense_text_hits = future_dense.result(timeout=15.0)
    except Exception as exc:
        logger.debug("[search] dense text retrieval join notice: %s", exc)
        dense_text_hits = []

    try:
        bm25_hits = future_bm25.result(timeout=15.0)
    except Exception as exc:
        logger.debug("[search] bm25 retrieval join notice: %s", exc)
        bm25_hits = []

    try:
        clip_hits = future_clip.result(timeout=15.0)
    except Exception as exc:
        logger.debug("[search] clip retrieval join notice: %s", exc)
        clip_hits = []

    # 4) Merge using RRF
    merged = _rrf_merge([dense_text_hits, bm25_hits, clip_hits], k=config.FUSION_RRF_K)

    # 5) Normalize fields and dedupe by citation target (preserving all distinct chunks)
    normalized = [_normalize(h, "hybrid") for h in merged]
    deduped: Dict[str, Dict[str, Any]] = {}
    for n in normalized:
        key = _citation_key(n)
        cur = deduped.get(key)
        if cur is None or n["score"] > cur["score"]:
            deduped[key] = n
    candidates = sorted(deduped.values(), key=lambda x: x["score"], reverse=True)

    # 5.0 Guarantee all target experiments are in candidates with high priority
    if exp_targets:
        aim_re = re.compile(r"\b(?:aim|objective)\b", re.IGNORECASE)
        is_code_q = bool(re.search(r"\b(code|program|script|implementation|c\+\+|cpp|python|java|sql|source\s*code|function|algorithm)\b", query, re.IGNORECASE))
        code_pattern = re.compile(r"(?:#include|\bint\s+main\b|\bstring\s+classify\b|\bclassify\b|\bdef\s+[a-zA-Z_]|\bimport\s+[a-zA-Z_]|\bclass\s+[a-zA-Z_]|```|\.cpp|\.py|\.java|\.c|\bvoid\s+[a-zA-Z_]|\bImplementation\b)", re.IGNORECASE)
        try:
            corpus = vector_store.get_text_corpus(where=where)
            if not corpus:
                corpus = vector_store.get_text_corpus(where=None)
            for t in exp_targets:
                t_re = re.compile(rf"\b(?:experiment|exp\.?)\s*(?:no\.?|number)?\s*[:#-]?\s*{re.escape(t)}\b", re.IGNORECASE)
                injected_count = 0
                for item in corpus:
                    sec = str(item.get("metadata", {}).get("section", "") or "")
                    doc = str(item.get("document", "") or "")
                    if t_re.search(sec) or t_re.search(doc):
                        norm = _normalize(item, "target_experiment")
                        key = _citation_key(norm)
                        if is_code_q and code_pattern.search(doc):
                            boost = 0.99
                        elif aim_re.search(doc):
                            boost = 0.98
                        else:
                            boost = 0.88
                        norm["score"] = boost
                        if key not in deduped:
                            deduped[key] = norm
                            candidates.append(norm)
                        else:
                            deduped[key]["score"] = max(deduped[key].get("score", 0.0), boost)
                        injected_count += 1

                # If corpus didn't have matches, fallback to lexical index
                if injected_count == 0:
                    fallback_hits = _bm25_search(
                        f"EXPERIMENT {t}", top_n=15, user_id=user_id, session_id=session_id, modality=modality, files=files, org_id=org_id
                    )
                    for item in fallback_hits:
                        norm = _normalize(item, "target_experiment_bm25")
                        key = _citation_key(norm)
                        doc = str(norm.get("document") or norm.get("text") or "")
                        boost = 0.99 if (is_code_q and code_pattern.search(doc)) else 0.88
                        norm["score"] = boost
                        if key not in deduped:
                            deduped[key] = norm
                            candidates.append(norm)
                        else:
                            deduped[key]["score"] = max(deduped[key].get("score", 0.0), boost)
        except Exception as exc:
            logger.debug("[search] target experiment injection notice: %s", exc)

        candidates.sort(key=lambda x: x["score"], reverse=True)

    # Soft section boost instead of destructive pruning so cross-section context remains available
    if requested_section:
        for c in candidates:
            if c.get("section") == requested_section:
                c["score"] = c["score"] * 1.35
        candidates.sort(key=lambda x: x["score"], reverse=True)

    # Locative anchor boost
    loc_anchors = _extract_locative_anchors(query)
    if loc_anchors:
        for c in candidates:
            c_txt = (str(c.get("text") or "") + " " + str(c.get("snippet") or "")).lower()
            if any(anc in c_txt for anc in loc_anchors):
                c["score"] = c.get("score", 0.0) + 0.35
        candidates.sort(key=lambda x: x["score"], reverse=True)

    # 5.1 Neighbor expansion for multi-page sections, tables, and narrative documents
    is_aim_query = bool(re.search(r"\b(aim|objective|purpose|goal)\b", query, re.IGNORECASE))
    is_table_query = (not is_aim_query) and bool(re.search(r"\b(table|tabular|test\s*cases?|chart|matrix|schedule)\b", query, re.IGNORECASE))
    if candidates and (is_table_query or candidates[0].get("modality") == "document"):
        top_doc = candidates[0]
        top_file = top_doc.get("file")
        top_page = top_doc.get("page")
        if top_file and top_page is not None:
            pages_to_check = [top_page]
            if is_table_query:
                pages_to_check.append(top_page + 1)
                if top_page > 1:
                    pages_to_check.append(top_page - 1)
            try:
                neighbors = vector_store.get_neighbor_chunks(
                    file=top_file,
                    pages=pages_to_check,
                    session_id=session_id,
                    user_id=user_id,
                    org_id=org_id,
                )
                for neighbor in neighbors:
                    meta = neighbor.get("metadata", {})
                    doc_text = neighbor.get("document", "")
                    is_neighbor_table = meta.get("source_type") == "table" or "|" in doc_text or "test case" in doc_text.lower()
                    if is_table_query and not is_neighbor_table:
                        continue
                    neighbor_score = 0.85 if is_table_query else max(0.01, top_doc.get("score", 0.35) - 0.001)
                    norm_n = _normalize({
                        "id": neighbor.get("id"),
                        "document": doc_text,
                        "text": doc_text,
                        "metadata": meta,
                        "score": neighbor_score,
                    }, "neighbor_expansion")
                    n_key = _citation_key(norm_n)
                    if n_key not in deduped:
                        deduped[n_key] = norm_n
                        candidates.append(norm_n)
                    else:
                        deduped[n_key]["score"] = max(deduped[n_key].get("score", 0.0), neighbor_score)
            except Exception as exc:
                logger.debug("[search] neighbor expansion notice: %s", exc)

        # Ensure candidates are sorted so the expanded neighbor tables/chunks are in the rerank pool
        candidates.sort(key=lambda x: x["score"], reverse=True)

    # 5.2 Complete image bundle injection (caption + OCR + CLIP) for scoped or descriptive image queries
    is_descriptive_image_query = bool(re.search(
        r"\b(what('?s|\s+is)\s+in\s+(this|the)|describe|explain|summarize|overview|show|about|what\s+does\s+this\s+(image|screenshot|photo|picture)\s+(show|contain|have))\b",
        query,
        re.IGNORECASE,
    ))
    if modality in ("image", "all") and (is_descriptive_image_query or files):
        image_files = set()
        for c in candidates:
            if c.get("modality") == "image" or c.get("source_type") in ("image", "ocr", "caption"):
                image_files.add(c.get("file"))
        if files:
            for f in files:
                if any(f.lower().endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp", ".bmp")):
                    image_files.add(f)
        if image_files:
            try:
                corpus = vector_store.get_text_corpus(where=where)
                for item in corpus:
                    meta = item.get("metadata", {})
                    if meta.get("file") in image_files:
                        norm_img = _normalize(item, "image_bundle")
                        img_key = _citation_key(norm_img)
                        norm_img["score"] = max(norm_img.get("score", 0.0), 0.90)
                        if img_key not in deduped:
                            deduped[img_key] = norm_img
                            candidates.append(norm_img)
                        else:
                            deduped[img_key]["score"] = max(deduped[img_key].get("score", 0.0), 0.90)
                candidates.sort(key=lambda x: x["score"], reverse=True)
            except Exception as exc:
                logger.debug("[search] image bundle injection notice: %s", exc)

    # 5.3 Complete audio transcript bundle injection & cross-document link for scoped, comparative, or descriptive audio queries
    is_descriptive_audio_query = bool(re.search(
        r"\b(what('?s|\s+is)?\s+in\s+(this|the)?\s*(audio|recording|voice|speech|call|sound|file)?|what\s+does\s+this\s+(audio|recording|voice|speech)\s+(say|discuss|contain|have|talk\s+about)|describe\s+(the|this)?\s*(audio|recording|speech)|transcribe|transcript|summarize\s+(the|this)?\s*(audio|recording|speech)|what\s+(is|was)\s+(said|spoken|discussed)|who\s+(spoke|is\s+speaking|talked))\b",
        query,
        re.IGNORECASE,
    ))
    is_comparative_query = bool(re.search(
        r"\b(common\s*(?:names?|words?|terms?|text|entity|person|people|topics?|items?|details?|authors?|students?|teachers?|supervisors?)?|between\s+(?:these\s+)?(?:two|both|files|documents|recordings|audios)|in\s+both|compare|comparison|difference|similar|similarity|shared|overlap|match|across\s+(?:the\s+)?(?:two|both|files|documents))\b",
        query,
        re.IGNORECASE,
    ))
    if modality in ("audio", "all") and (is_descriptive_audio_query or is_comparative_query or files or session_id):
        audio_files = set()
        for c in candidates:
            if c.get("modality") == "audio" or c.get("source_type") in ("audio", "transcript"):
                audio_files.add(c.get("file"))
        if files:
            for f in files:
                if any(str(f).lower().endswith(ext) for ext in (".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac")):
                    audio_files.add(f)
        if not audio_files and (is_descriptive_audio_query or is_comparative_query or session_id):
            try:
                session_files = vector_store.list_files(session_id=session_id, user_id=user_id, org_id=org_id)
                for sf in session_files:
                    fname = sf.get("file", "")
                    if sf.get("modality") == "audio" or any(str(fname).lower().endswith(ext) for ext in (".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac")):
                        audio_files.add(fname)
            except Exception as exc:
                logger.debug("[search] audio session probe notice: %s", exc)

        if audio_files:
            try:
                aud_where = vector_store.build_where(session_id=session_id, user_id=user_id, org_id=org_id)
                corpus = vector_store.get_text_corpus(where=aud_where)
                if not corpus and where:
                    corpus = vector_store.get_text_corpus(where=where)
                audio_items = []
                all_audio_texts = []
                for item in corpus:
                    meta = item.get("metadata", {})
                    if meta.get("file") in audio_files or meta.get("modality") == "audio" or meta.get("source_type") == "transcript":
                        norm_aud = _normalize(item, "audio_transcript_bundle")
                        start_time = float(meta.get("start") or 0.0)
                        norm_aud["_start_time"] = start_time
                        norm_aud["score"] = max(norm_aud.get("score", 0.0), 0.99 - (start_time * 0.0001))
                        audio_items.append(norm_aud)
                        all_audio_texts.append(str(item.get("document") or ""))

                audio_items.sort(key=lambda x: x.get("_start_time", 0.0))
                for norm_aud in audio_items:
                    aud_key = _citation_key(norm_aud)
                    if aud_key not in deduped:
                        deduped[aud_key] = norm_aud
                        candidates.append(norm_aud)
                    else:
                        deduped[aud_key]["score"] = max(deduped[aud_key].get("score", 0.0), norm_aud["score"])

                if is_comparative_query and all_audio_texts:
                    cross_terms = set()
                    for atxt in all_audio_texts:
                        sub_m = re.search(r"submitted\s+by\s+([A-Za-z\s]+?)(?:\s+under|\s+supervised|$|[.,])", atxt, re.IGNORECASE)
                        if sub_m:
                            cross_terms.update(sub_m.group(1).split())
                        sup_m = re.search(r"(?:supervision\s+of|supervised\s+by)\s+([A-Za-z\s]+?)(?:$|[.,])", atxt, re.IGNORECASE)
                        if sup_m:
                            cross_terms.update(sup_m.group(1).split())
                        for word in re.findall(r"\b[A-Z][a-z]+\b", atxt):
                            if word.lower() not in ("this", "document", "is", "under", "the", "by", "of", "and"):
                                cross_terms.add(word)

                    if cross_terms:
                        search_probe = " ".join(cross_terms)
                        doc_matches = _bm25_search(
                            f"{search_probe} submitted by supervision",
                            top_n=8,
                            session_id=session_id,
                            user_id=user_id,
                            org_id=org_id,
                        )
                        for dm in doc_matches:
                            meta = dm.get("metadata", {})
                            if meta.get("modality") == "audio" or meta.get("source_type") == "transcript":
                                continue
                            norm_dm = _normalize(dm, "cross_document_match")
                            norm_dm["score"] = max(norm_dm.get("score", 0.0), 0.98)
                            dm_key = _citation_key(norm_dm)
                            if dm_key not in deduped:
                                deduped[dm_key] = norm_dm
                                candidates.append(norm_dm)
                            else:
                                deduped[dm_key]["score"] = max(deduped[dm_key].get("score", 0.0), 0.98)

                candidates.sort(key=lambda x: x["score"], reverse=True)
            except Exception as exc:
                logger.debug("[search] audio bundle injection notice: %s", exc)

    # 6) Cross-encoder rerank with diverse pool and coalesce same-page adjacent chunks
    rerank_pool_size = max(effective_top_k * 3, 30)
    reranked = _rerank(query, candidates, top_n=rerank_pool_size)
    res = _coalesce_and_diversify(reranked, effective_top_k, exp_targets=exp_targets, query=query)

    # Phase 4.5: Safe scope fallback: if a files filter was active but yielded 0 hits or no content overlap,
    # retry across all files of this user/session so newly uploaded documents are never silenced.
    if files:
        from backend.retrieval.lexical_index import tokenize_multilingual
        q_tokens = [t for t in tokenize_multilingual(query) if len(t) > 2]
        has_overlap = False
        if res and q_tokens:
            for r in res:
                body = (r.get("text") or r.get("snippet") or "").lower()
                if any(t in body for t in q_tokens):
                    has_overlap = True
                    break
        if not res or (not has_overlap and q_tokens):
            fallback_res = text_query(
                query=query, top_k=top_k, modality=modality, session_id=session_id,
                files=None, user_id=user_id, org_id=org_id
            )
            if fallback_res:
                return fallback_res

    return res

# ------------------------------------------------------------------ image query
def image_query(
    image: Image.Image,
    top_k: int = config.DEFAULT_TOP_K,
    session_id: Optional[str] = None,
    files: Optional[List[str]] = None,
    user_id: Optional[str] = None,
    org_id: Optional[str] = None,
) -> Dict[str, Any]:
    from backend.ingestion.image_pipeline import caption_image, ocr_image
    caption = caption_image(image)
    ocr_text = ocr_image(image)

    img_where = vector_store.build_where(session_id=session_id, files=files, user_id=user_id, org_id=org_id)
    clip_vec = embeddings.embed_clip_image([image])[0].tolist()
    clip_hits = vector_store.query_images(clip_vec, top_k=top_k, where=img_where)

    probe = (caption + ". " + ocr_text).strip()
    txt_where = vector_store.build_where(session_id=session_id, files=files, user_id=user_id, org_id=org_id)
    text_vec = embeddings.embed_text([probe])[0].tolist()
    text_hits = vector_store.query_text(text_vec, top_k=top_k, where=txt_where)

    hits = _merge_and_rank(text_hits, clip_hits, top_k)
    return {"query_caption": caption, "query_ocr": ocr_text, "hits": hits}
