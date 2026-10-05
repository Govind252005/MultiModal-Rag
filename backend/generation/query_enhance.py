"""
Phase 3A — Query enhancement (rewriting + HyDE).

Both functions are ADDITIVE wrappers: they call the LLM once to produce a
better search string, then the UNCHANGED retrieval pipeline uses that string.
Neither function touches ChromaDB, BM25, CLIP, RRF, or the cross-encoder.

query_rewrite(query, history, provider, user_id)
    Resolves pronouns / context-dependent references into a self-contained
    search query.  E.g. "and its price?" + history -> "What is the price of X?"

hyde_passage(query, provider, user_id)
    Generates a short hypothetical answer passage.  The caller embeds THAT
    passage instead of the raw query for the dense retrieval step (HyDE).
"""

from __future__ import annotations

from typing import List, Optional

from backend import config
from backend.generation.providers import router

_REWRITE_SYSTEM = (
    "You are a search-query rewriter. "
    "Given a conversation history and a follow-up question, rewrite the "
    "question into a single, self-contained search query that can be "
    "understood without the history. "
    "Output ONLY the rewritten query — no explanation, no quotes."
)

_HYDE_SYSTEM = (
    "You are a helpful assistant. "
    "Write a short, factual passage (2-4 sentences) that would directly "
    "answer the following question. "
    "Output ONLY the passage — no preamble, no citations."
)


def _call(system: str, user: str, provider: Optional[str],
          user_id: Optional[str]) -> str:
    try:
        return router.generate(system, user, provider=provider,
                               user_id=user_id).strip()
    except Exception:
        return ""


def query_rewrite(
    query: str,
    history: Optional[List[dict]] = None,
    provider: Optional[str] = None,
    user_id: Optional[str] = None,
) -> str:
    """Return a standalone version of *query* resolved against *history*.
    Falls back to the original query on any error."""
    if not config.QUERY_REWRITE_ENABLED:
        return query
    if not history:
        return query
    recent = history[-4:]
    history_text = "\n".join(
        f"{t.get('role','user').upper()}: {t.get('content','')}"
        for t in recent
    )
    user_msg = f"Conversation so far:\n{history_text}\n\nFollow-up: {query}"
    result = _call(_REWRITE_SYSTEM, user_msg, provider, user_id)
    return result if result else query


def hyde_passage(
    query: str,
    provider: Optional[str] = None,
    user_id: Optional[str] = None,
) -> str:
    """Return a hypothetical answer passage for *query* (HyDE).
    Falls back to the original query on any error."""
    if not config.HYDE_ENABLED:
        return query
    result = _call(_HYDE_SYSTEM, query, provider, user_id)
    return result if result else query
