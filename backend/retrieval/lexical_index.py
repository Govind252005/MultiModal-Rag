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
    con = sqlite3.connect(str(_DB_PATH), timeout=30.0)
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
    con.commit()


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
        rows.append(
            (
                text or "",
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


def delete_by_file(file: str, session_id: Optional[str] = None) -> int:
    con = _connect()
    try:
        if session_id:
            cur = con.execute(
                "DELETE FROM lexical_index WHERE file = ? AND session_id = ?",
                (file, session_id),
            )
        else:
            cur = con.execute("DELETE FROM lexical_index WHERE file = ?", (file,))
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


def _fts_query(raw_query: str) -> Optional[str]:
    """Turn a free-text query into a safe FTS5 MATCH expression: every token
    quoted (so punctuation inside a token can never be parsed as FTS5 query
    syntax) and OR-joined (matches the previous BM25Okapi behaviour, which
    scored a document containing ANY query term, weighted by term rarity)."""
    import re

    tokens = re.findall(r"\w+", (raw_query or "").lower())
    if not tokens:
        return None
    escaped = ['"' + t.replace('"', '""') + '"' for t in tokens]
    return " OR ".join(escaped)


def search(
    query: str,
    top_n: int,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    modality: Optional[str] = None,
    files: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Return up to top_n hits in the same shape as
    vector_store.get_text_corpus() (id/document/metadata/score), ranked by
    SQLite FTS5's built-in BM25. Pure index read — no corpus scan, no
    tokenizer pass over stored documents."""
    match_expr = _fts_query(query)
    if match_expr is None:
        return []

    clauses = ["lexical_index MATCH ?"]
    params: List[Any] = [match_expr]

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
