"""
Phase 3C — Multi-hop reasoning.

For complex questions that need facts from several places ("Compare the
revenue in the 2022 report with the target mentioned in the CEO's speech"),
a single retrieval often misses one side. Multi-hop:

  1. Decomposes the question into <= N focused sub-questions (one LLM call).
  2. Runs the EXISTING retrieval pipeline (search.text_query) once per
     sub-question — nothing in that pipeline is modified.
  3. Unions + dedupes the hits (by id), renumbers citations.
  4. Synthesizes one grounded, cited answer over the combined context.

This module is pure orchestration on top of existing pieces (search + router
+ answer helpers). It is only invoked when the caller passes multihop=True
(gated by config.MULTIHOP_ENABLED at the endpoint).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend import config
from backend.generation import answer as answer_mod 
from backend.generation import prompt_templates
from backend.generation.providers import router
from backend.retrieval import search

_DECOMPOSE_SYSTEM = (
    "You are a question-decomposition assistant. "
    "Break the user's question into a small number of simpler, standalone "
    "sub-questions that must each be answered to fully answer the original. "
    "If the question is already simple, return it unchanged as a single item. "
    "Return ONE sub-question per line, no numbering, no extra text."
)


def _decompose(query: str, provider: Optional[str],
               user_id: Optional[str]) -> List[str]:
    try:
        raw = router.generate(_DECOMPOSE_SYSTEM, query,
                              provider=provider, user_id=user_id)
    except Exception:
        return [query]
    subs: List[str] = []
    for line in (raw or "").splitlines():
        line = re.sub(r"^\s*[-*\d.\)]+\s*", "", line).strip()
        if line:
            subs.append(line)
    subs = subs[:config.MULTIHOP_MAX_SUBQUESTIONS]
    return subs or [query]


def _union_hits(hit_lists: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Merge hits from all sub-questions, dedupe by id, keep best score."""
    merged: Dict[str, Dict[str, Any]] = {}
    for hits in hit_lists:
        for h in hits:
            hid = h.get("id")
            if hid is None:
                continue
            cur = merged.get(hid)
            if cur is None or (h.get("score") or 0) > (cur.get("score") or 0):
                merged[hid] = h
    return sorted(merged.values(),
                  key=lambda x: x.get("score") or 0.0, reverse=True)


def multihop_answer(
    query: str,
    top_k: int = config.DEFAULT_TOP_K,
    modality: str = "all",
    session_id: Optional[str] = None,
    files: Optional[List[str]] = None,
    user_id: Optional[str] = None,
    history: Optional[List[Dict[str, str]]] = None,
    provider: Optional[str] = None,
    session_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Decompose -> retrieve per sub-question -> synthesize one cited answer."""
    subquestions = _decompose(query, provider, user_id)

    hit_lists: List[List[Dict[str, Any]]] = []
    for sub in subquestions:
        hits = search.text_query(
            sub, top_k=top_k, modality=modality,
            session_id=session_id, files=files, user_id=user_id,
        )
        hit_lists.append(hits)

    combined = _union_hits(hit_lists)[: max(top_k, config.DEFAULT_TOP_K)]

    if not combined:
        return {
            "answer": prompt_templates.MISSING_CONTEXT_MESSAGE,
            "citations": [], "used_llm": False,
            "faithfulness_warning": False, "subquestions": subquestions,
        }

    # Reuse the standard grounded-answer path over the combined context so
    # citations, confidence, audit, and faithfulness behave identically.
    result = answer_mod.answer_query(
        query, combined, history=history, provider=provider,
        user_id=user_id, session_dir=session_dir,
    )
    result["subquestions"] = subquestions
    result["retrieved"] = combined
    return result
