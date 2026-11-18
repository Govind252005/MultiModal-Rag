"""
Persistent lexical (keyword) index — SQLite FTS5.

WHY THIS FILE EXISTS (see AUDIT_REPORT.md, finding P1-1):
The previous implementation rebuilt a `rank_bm25.BM25Okapi` index from the
ENTIRE scoped text corpus on every single `/api/query` call
(`retrieval/search.py::_bm25_search`, old version). That is O(corpus size)
work per query and does not scale.

This module makes the lexical index persistent:
    ingest  -> index_add_chunks()   (index updated once, at write time)
    delete  -> index_delete_*()     (index updated once, at write time)
    query   -> search()             (index just READS; no corpus load, no
                                      tokenizer pass over documents at query time)

SQLite's FTS5 module ships its own BM25 ranking function (`bm25(table)`), so
we get real BM25 scoring without re-deriving it in Python, and the index is
durable across restarts (single file on disk, alongside the rest of this
app's local storage — consistent with the project's "offline, no extra
services required" design).

Concurrency: every call opens a short-lived connection in WAL mode. This is
adequate for a single-process local/desktop deployment (item #100/#101 in the
transformation brief calls for this kind of "load once, don't thrash" model
for heavy ML models; a lightweight SQLite connection per call is cheap enough
that a persistent pooled connection is not required here, and avoids
thread-safety pitfalls in a multi-worker FastAPI process).

Metadata note: this index intentionally duplicates a little data (the full
metadata dict, as JSON, in an UNINDEXED column) so `search()` can return the
exact same hit shape the rest of the pipeline (`_normalize()` in search.py)
already expects, without a second round-trip to Chroma.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend import config

_DB_PATH: Path = config.STORE_DIR / "lexical_index.sqlite3"
_lock = threading.Lock()  # guards schema creation only; SQLite handles the rest


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(str(_DB_PATH), timeout=30.0, check_same_thread=False)
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA synchronous=NORMAL;")
    return con


def _ensure_schema(con: sqlite3.Connection) -> None:
    con.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS lexical_index USING fts5(
            content,
            doc_id UNINDEXED,
            user_id UNINDEXED,
            session_id UNINDEXED,
            file UNINDEXED,
            modality UNINDEXED,
            meta_json UNINDEXED,
            tokenize = 'unicode61 remove_diacritics 2'
        );
        """
    )
    con.execute("CREATE TABLE IF NOT EXISTS lexical_meta (key TEXT PRIMARY KEY, value TEXT);")
    con.commit()


_REINDEX_VERSION = "v2_stemming"
_reindexed_checked = False


def reindex_from_storage(force: bool = False) -> int:
    """Re-tokenize all chunks in storage with the updated tokenize_multilingual and rebuild FTS5."""
    try:
        from backend.retrieval import vector_store
        corpus = vector_store.get_text_corpus()
        
        ids: List[str] = []
        docs: List[str] = []
        metas: List[Dict[str, Any]] = []

        if corpus:
            ids = [c["id"] for c in corpus]
            docs = [c["document"] for c in corpus]
            metas = [c["metadata"] for c in corpus]
        else:
            # Fallback to reading existing SQLite rows if Chroma is empty
            con = _connect()
            try:
                cur = con.execute("SELECT doc_id, content, meta_json FROM lexical_index")
                rows = cur.fetchall()
            finally:
                con.close()
            if rows:
                ids = [r[0] for r in rows]
                docs = [r[1].split("\n")[0] if "\n" in r[1] else r[1] for r in rows]
                metas = [json.loads(r[2]) if r[2] else {} for r in rows]

        if not ids:
            con = _connect()
            try:
                con.execute("CREATE TABLE IF NOT EXISTS lexical_meta (key TEXT PRIMARY KEY, value TEXT);")
                con.execute("INSERT OR REPLACE INTO lexical_meta (key, value) VALUES ('version', ?)", (_REINDEX_VERSION,))
                con.commit()
            finally:
                con.close()
            return 0

        # Reset lexical_index and re-index all chunks with updated multilingual stems
        con = _connect()
        try:
            con.execute("DELETE FROM lexical_index;")
            con.commit()
        finally:
            con.close()

        add_chunks(ids, docs, metas)

        con = _connect()
        try:
            con.execute("CREATE TABLE IF NOT EXISTS lexical_meta (key TEXT PRIMARY KEY, value TEXT);")
            con.execute("INSERT OR REPLACE INTO lexical_meta (key, value) VALUES ('version', ?)", (_REINDEX_VERSION,))
            con.commit()
        finally:
            con.close()

        print(f"[lexical_index] Reindexed {len(ids)} chunks with updated multilingual stemming.")
        return len(ids)
    except Exception as exc:
        print(f"[lexical_index] reindex_from_storage failed: {exc}")
        return 0


def ensure_reindexed() -> None:
    """Ensure existing chunks are indexed with the latest tokenize_multilingual stemming."""
    global _reindexed_checked
    if _reindexed_checked:
        return
    with _lock:
        if _reindexed_checked:
            return
        con = _connect()
        try:
            con.execute("CREATE TABLE IF NOT EXISTS lexical_meta (key TEXT PRIMARY KEY, value TEXT);")
            cur = con.execute("SELECT value FROM lexical_meta WHERE key = 'version'")
            row = cur.fetchone()
            if not row or row[0] != _REINDEX_VERSION:
                reindex_from_storage()
            _reindexed_checked = True
        except Exception as exc:
            print(f"[lexical_index] ensure_reindexed check error: {exc}")
            _reindexed_checked = True
        finally:
            con.close()


def init() -> None:
    """Idempotent; call at startup and lazily on first use."""
    with _lock:
        con = _connect()
        try:
            _ensure_schema(con)
        finally:
            con.close()


init()


# ------------------------------------------------------------------ writing
def add_chunks(
    ids: List[str],
    documents: List[str],
    metadatas: List[Dict[str, Any]],
) -> None:
    """Index newly-ingested text chunks. Called right after
    vector_store.add_text_chunks() so the lexical and dense indexes never
    drift apart."""
    if not ids:
        return
    rows = []
    for doc_id, text, meta in zip(ids, documents, metadatas):
        meta = meta or {}
        raw_content = text or ""
        extra_terms = [t for t in tokenize_multilingual(raw_content) if t not in raw_content.lower()]
        content_to_index = raw_content + ("\n" + " ".join(extra_terms) if extra_terms else "")
        rows.append(
            (
                content_to_index,
                doc_id,
                meta.get("user_id", ""),
                meta.get("session_id", ""),
                meta.get("file", ""),
                meta.get("modality", ""),
                json.dumps(meta, ensure_ascii=False),
            )
        )
    con = _connect()
    try:
        con.executemany(
            """
            INSERT INTO lexical_index
                (content, doc_id, user_id, session_id, file, modality, meta_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        con.commit()
    finally:
        con.close()


def delete_by_ids(ids: List[str]) -> int:
    if not ids:
        return 0
    con = _connect()
    try:
        cur = con.executemany(
            "DELETE FROM lexical_index WHERE doc_id = ?", [(i,) for i in ids]
        )
        con.commit()
        return cur.rowcount if cur.rowcount is not None and cur.rowcount > 0 else len(ids)
    finally:
        con.close()


def delete_by_file(
    file: str,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    org_id: Optional[str] = None,
) -> int:
    con = _connect()
    try:
        clauses = ["file = ?"]
        params: List[Any] = [file]
        if session_id:
            clauses.append("session_id = ?")
            params.append(session_id)
        if user_id:
            clauses.append("user_id = ?")
            params.append(user_id)
        sql = f"DELETE FROM lexical_index WHERE {' AND '.join(clauses)}"
        cur = con.execute(sql, tuple(params))
        con.commit()
        return cur.rowcount or 0
    finally:
        con.close()


def delete_by_session(session_id: str) -> int:
    con = _connect()
    try:
        cur = con.execute(
            "DELETE FROM lexical_index WHERE session_id = ?", (session_id,)
        )
        con.commit()
        return cur.rowcount or 0
    finally:
        con.close()


def reset() -> None:
    con = _connect()
    try:
        con.execute("DELETE FROM lexical_index;")
        con.commit()
    finally:
        con.close()


# ------------------------------------------------------------------ reading
_MATCH_SPECIAL = set('"*^$():')


_QUERY_SYNONYMS = {
    "discovered": ["found", "find", "uncovered", "noticed"],
    "discover": ["found", "find", "uncovered", "noticed"],
    "profession": ["clockmaker", "occupation", "job", "career", "work", "role", "title", "archivist", "engineer", "doctor", "lawyer", "teacher"],
    "occupation": ["profession", "job", "career", "work", "clockmaker", "role"],
    "job": ["profession", "occupation", "career", "work", "clockmaker", "role"],
}


_DEVANAGARI_NUKTA_MAP = {
    "\u0958": "\u0915",  # क़ -> क
    "\u0959": "\u0916",  # ख़ -> ख
    "\u095A": "\u0917",  # ग़ -> ग
    "\u095B": "\u091C",  # ज़ -> ज
    "\u095C": "\u0921",  # ड़ -> ड
    "\u095D": "\u0922",  # ढ़ -> ढ
    "\u095E": "\u092B",  # फ़ -> फ
    "\u095F": "\u092F",  # य़ -> य
}


def normalize_devanagari(text: str) -> str:
    """Normalize Devanagari nukta characters and strip combining nuktas."""
    if not text:
        return ""
    for k, v in _DEVANAGARI_NUKTA_MAP.items():
        text = text.replace(k, v)
    text = text.replace("\u093C", "")  # strip combining nukta
    return text


def _hindi_stem(tok: str) -> Optional[str]:
    """Lightweight Hindi stemmer stripping common inflections and anusvara/chandrabindu."""
    import re
    if not any("\u0900" <= c <= "\u097F" for c in tok):
        return None
    tok_norm = normalize_devanagari(tok)
    # Strip trailing anusvara/chandrabindu
    tok_norm = re.sub(r"[\u0901\u0902]+$", "", tok_norm)
    # Ordered suffixes to strip
    suffixes = ["ियों", "िया", "ाओं", "ीं", "ें", "ों", "ा", "ी", "े", "ो"]
    for sfx in suffixes:
        if tok_norm.endswith(sfx):
            stem = tok_norm[:-len(sfx)]
            if len(stem) >= 2:
                return stem
    if len(tok_norm) >= 2 and tok_norm != tok:
        return tok_norm
    return None


def tokenize_multilingual(text: str) -> List[str]:
    """Tokenize text preserving Indic scripts, Arabic, CJK, accented Latin, and technical codes.
    For Devanagari tokens, emits both the surface token and normalized/stemmed forms."""
    import re
    if not text:
        return []
    # Normalize curly apostrophes/quotes
    clean_text = re.sub(r"[\u2018\u2019\u02BC`]", "'", text)
    # Strip English possessive suffixes so Mira's -> Mira, grandfather's -> grandfather, town's -> town
    clean_text = re.sub(r"([A-Za-z0-9]+)'s\b", r"\1", clean_text, flags=re.IGNORECASE)
    pattern = re.compile(
        r"[\u0900-\u0D7F]+|"                   # All Indic scripts (Devanagari, Bengali, Gurmukhi, Gujarati, etc.)
        r"[\u0600-\u06FF\u0750-\u077F]+|"      # Arabic and extended Arabic
        r"[\u0400-\u04FF]+|"                   # Cyrillic
        r"[\u4E00-\u9FFF\u3400-\u4DBF]|"       # CJK Ideographs
        r"[A-Za-z0-9\u00C0-\u024F]+(?:[.\-_/][A-Za-z0-9\u00C0-\u024F]+)*(?:\+\+|[+\-%])?" # Alphanumeric, code, units
    )
    tokens = pattern.findall(clean_text.lower())
    result: List[str] = []
    seen = set()
    for t in tokens:
        if (
            len(t) > 1
            or t.isdigit()
            or any("\u4E00" <= c <= "\u9FFF" or "\u3400" <= c <= "\u4DBF" for c in t)
            or any("\u0900" <= c <= "\u0D7F" for c in t)
        ):
            if t not in seen:
                seen.add(t)
                result.append(t)
            # Emit normalized nukta form if different
            norm_t = normalize_devanagari(t)
            if norm_t != t and norm_t not in seen and len(norm_t) > 1:
                seen.add(norm_t)
                result.append(norm_t)
            # Emit Hindi stem if applicable
            stem = _hindi_stem(t)
            if stem and stem not in seen and len(stem) >= 2:
                seen.add(stem)
                result.append(stem)
    return result


def _fts_query(raw_query: str) -> Optional[str]:
    """Turn a free-text query into a safe FTS5 MATCH expression with synonym expansion."""
    tokens = tokenize_multilingual(raw_query)
    if not tokens:
        return None
    # Filter out bare punctuation tokens that might break FTS5 MATCH syntax
    clean_tokens = [t.strip("\"'*^$():") for t in tokens if t.strip("\"'*^$():")]
    if not clean_tokens:
        return None

    expanded = list(clean_tokens)
    for t in clean_tokens:
        syns = _QUERY_SYNONYMS.get(t.lower())
        if syns:
            for s in syns:
                if s not in expanded:
                    expanded.append(s)

    escaped = ['"' + t.replace('"', '""') + '"' for t in expanded]
    return " OR ".join(escaped)


def search(
    query: str,
    top_n: int,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    modality: Optional[str] = None,
    files: Optional[List[str]] = None,
    org_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return up to top_n hits in the same shape as
    vector_store.get_text_corpus() (id/document/metadata/score), ranked by
    SQLite FTS5's built-in BM25. Pure index read — no corpus scan, no
    tokenizer pass over stored documents."""
    ensure_reindexed()
    match_expr = _fts_query(query)
    if match_expr is None:
        return []

    clauses = ["lexical_index MATCH ?"]
    params: List[Any] = [match_expr]

    if org_id:
        clauses.append("COALESCE(json_extract(meta_json, '$.org_id'), 'default_org') = ?")
        params.append(org_id)
    if user_id:
        clauses.append("user_id = ?")
        params.append(user_id)
    if session_id:
        clauses.append("session_id = ?")
        params.append(session_id)
    if modality and modality != "all":
        clauses.append("modality = ?")
        params.append(modality)
    if files:
        placeholders = ",".join("?" for _ in files)
        clauses.append(f"file IN ({placeholders})")
        params.extend(files)

    sql = (
        "SELECT doc_id, content, meta_json, bm25(lexical_index) AS rank "
        "FROM lexical_index WHERE " + " AND ".join(clauses) +
        " ORDER BY rank LIMIT ?"
    )
    params.append(top_n)

    con = _connect()
    try:
        cur = con.execute(sql, params)
        out: List[Dict[str, Any]] = []
        for doc_id, content, meta_json, rank in cur.fetchall():
            try:
                meta = json.loads(meta_json) if meta_json else {}
            except (TypeError, ValueError):
                meta = {}
            # FTS5's bm25(): lower/more-negative = more relevant. Flip the
            # sign so this channel's "score" convention (higher = better)
            # matches the dense-search and CLIP channels for RRF merging.
            out.append(
                {
                    "id": doc_id,
                    "document": content or "",
                    "metadata": meta,
                    "score": -float(rank),
                }
            )
        return out
    except sqlite3.OperationalError:
        # Malformed MATCH expression (should be rare given the quoting above)
        # — fail soft, same as the previous implementation's try/except.
        return []
    finally:
        con.close()


def stats() -> Dict[str, int]:
    con = _connect()
    try:
        (count,) = con.execute("SELECT COUNT(*) FROM lexical_index").fetchone()
        return {"lexical_items": int(count)}
    finally:
        con.close()
