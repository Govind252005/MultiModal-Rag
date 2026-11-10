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

import re
from typing import List, Optional

from backend import config
from backend.generation.providers import router

_COREFERENCE_MARKERS = re.compile(
    r"\b(it|its|he|his|him|she|her|they|their|them|the second|the first|the former|the latter|the same)\b",
    re.IGNORECASE,
)

_CONTINUATION_START = re.compile(
    r"^(?:and|also|what about|how about|what of|more about|tell me more|elaborate)\b",
    re.IGNORECASE,
)

_STANDALONE_DOC_QUERY = re.compile(
    r"^(?:who\s+(?:is|was|are|were|submitted|wrote|signed|created|authored|prepared)|what\s+is\s+the\s+(?:invoice|total|amount|summary|title|date|aim|objective)|what\s+does\s+the\s+document|summarize|overview)\b",
    re.IGNORECASE,
)


def contextualize_followup_query(
    query: str, history: Optional[List[dict]] = None
) -> str:
    """Zero-latency heuristic coreference contextualizer for multi-turn search.
    Only activates on genuine coreference pronouns or explicit conversational continuations.
    Never corrupts standalone specific questions (e.g. 'Who submitted this document?')."""
    if not history or not query:
        return query
    clean_q = query.strip()

    # If it is a standalone complete document query without explicit person pronouns, do not rewrite
    if _STANDALONE_DOC_QUERY.search(clean_q) and not re.search(r"\b(he|his|him|she|her|they|their|them)\b", clean_q, re.IGNORECASE):
        return query

    needs_context = bool(_COREFERENCE_MARKERS.search(clean_q)) or bool(_CONTINUATION_START.search(clean_q))
    if not needs_context:
        return query

    prev_user_text = ""
    for turn in reversed(history):
        role = turn.get("role", "")
        text = turn.get("text", "") or turn.get("content", "")
        if role == "user" and text.strip():
            prev_user_text = text.strip()
            break

    if not prev_user_text:
        return query

    stop_words = {"what", "when", "where", "which", "who", "whom", "whose", "why", "how", "tell", "does", "have", "with", "this", "that", "from", "show", "give"}
    prev_tokens = [
        w for w in re.findall(r"\b[A-Za-z0-9_-]+\b", prev_user_text)
        if len(w) > 3 and w.lower() not in stop_words
    ]
    if not prev_tokens:
        return query

    context_hint = " ".join(prev_tokens[:4])
    return f"{context_hint} {clean_q}"

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
