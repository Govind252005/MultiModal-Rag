import re
import json
from backend import config
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.generation import llm_client, prompt_templates
from backend.generation.providers import router


def _audit(user_id: Optional[str], query: str, result: Dict[str, Any]) -> None:
    if not user_id:
        return
    try:
        log_dir = Path(config.DATA_DIR) / "audit"
        log_dir.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "user_id": user_id,
            "query": query,
            "answer": result.get("answer", ""),
            "used_llm": result.get("used_llm", False),
            "citations": [
                {"index": c["index"], "file": c["file"], "score": c.get("score")}
                for c in result.get("citations", [])
            ],
        }
        with open(log_dir / f"{user_id}.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as exc:
        print(f"[audit] write failed: {exc}")


def _citation(index: int, hit: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "index": index,
        "id": hit.get("id"),
        "file": hit.get("file"),
        "modality": hit.get("modality"),
        "source_type": hit.get("source_type"),
        "page": hit.get("page"),
        "section": hit.get("section"),
        "start": hit.get("start"),
        "end": hit.get("end"),
        "timestamp": hit.get("timestamp"),
        "snippet": hit.get("snippet"),
        "media_url": hit.get("media_url"),
        "score": hit.get("score"),
        # brief §19: this is a relative min-max normalization across THIS
        # answer's own citations, not a calibrated probability — three
        # retrieval scores of 0.31/0.30/0.29 would map to 100/50/0 despite
        # being nearly identical. Named accordingly. "confidence" is kept
        # as a deprecated alias (identical value) purely so any other
        # existing consumer of this field doesn't break; new code should
        # read relative_relevance and should not present it as a
        # probability or calibrated confidence score.
        "relative_relevance": 0,
        "confidence": 0,
    }


def _add_confidence(citations: List[Dict[str, Any]]) -> None:
    scores = [c.get("score") or 0.0 for c in citations]
    if not scores:
        return
    mn, mx = min(scores), max(scores)
    rng = mx - mn if mx != mn else 1.0
    for c in citations:
        value = round(((c.get("score") or 0.0) - mn) / rng * 100)
        c["relative_relevance"] = value
        c["confidence"] = value  # deprecated alias — see _citation()'s comment


_CITATION_RE = re.compile(r"\[\d+\]")
_CITATION_INDEX_RE = re.compile(r"\[(\d+)\]")
_STYLE_ONLY_RE = re.compile(
    r"^\s*(table|json|markdown|bullet|bullets|list|format|tabular)\b",
    re.IGNORECASE,
)

_RESUME_HEADINGS = {
    "professional summary", "key expertise", "key skills", "education",
    "internships", "projects", "publications / research / white papers",
    "achievements", "personal interests / hobbies", "personal interests",
}


def _heading_section_answer(
    query: str, hits: List[Dict[str, Any]]
) -> Optional[str]:
    """Extract resume sections by heading without asking the LLM to summarize."""
    q = (query or "").lower()
    targets: List[str] = []
    if "achievement" in q:
        targets = ["achievements"]
    elif any(term in q for term in ("skill", "expertise", "technology", "technologies")):
        targets = ["key expertise", "key skills"]
    if not targets:
        return None

    for index, hit in enumerate(hits, start=1):
        text = str(hit.get("text") or hit.get("snippet") or "")
        lines = [line.strip() for line in text.splitlines()]
        for line_number, line in enumerate(lines):
            heading = re.sub(r"^[\-•*\s]+|[:\s]+$", "", line).lower()
            if heading not in targets:
                continue
            values: List[str] = []
            for candidate in lines[line_number + 1:]:
                normalized = re.sub(r"^[\-•*\s]+|[:\s]+$", "", candidate).lower()
                if normalized in _RESUME_HEADINGS:
                    break
                if candidate:
                    values.append(candidate)
            if values:
                return "\n".join(values) + f" [{index}]"
    return None


def _direct_field_answer(query: str, hits: List[Dict[str, Any]],
                         citations: List[Dict[str, Any]]) -> Optional[str]:
    """Answer unambiguous label/value questions without generative drift."""
    q = (query or "").lower()
    section_answer = _heading_section_answer(query, hits)
    if section_answer is not None:
        return section_answer
    field_patterns = []
    if "pan" in q:
        field_patterns.append(
            re.compile(r"\bpan\s*(?:no\.?|number)?\s*[:#-]?\s*"
                       r"([A-Z]{5}\d{4}[A-Z])\b", re.IGNORECASE)
        )
    if "invoice" in q and ("no" in q or "number" in q):
        field_patterns.append(
            re.compile(r"\binvoice\s*(?:no\.?|number)\s*[:#-]?\s*"
                       r"([A-Z0-9][A-Z0-9_/-]*)\b", re.IGNORECASE)
        )
    if "invoice" in q and re.search(r"to whom|issued to|billed to|recipient", q):
        field_patterns.append(
            re.compile(r"\b(?:issued\s+to|billed\s+to|bill\s+to|to)\s*"
                       r"[:#-]\s*([^\r\n]+)", re.IGNORECASE)
        )
    if "total" in q and ("amount" in q or "price" in q or "value" in q):
        field_patterns.append(
            re.compile(
                r"\b(?:total\s+amount|total|amount)\s*[:#-]?\s*"
                r"((?:Rs\.?|INR|₹)\s*[\d,]+(?:\s*/-)?|[\d,]+\s*(?:rupees|INR))",
                re.IGNORECASE,
            )
        )
    if "invoice" in q and re.search(r"reason|purpose|for", q):
        field_patterns.append(
            re.compile(
                r"\b(reasoning(?:\s+ssc)?|(?:reason|purpose|service|topic)\s*"
                r"(?:for\s+the\s+invoice)?\s*[:#-]\s*[^\r\n]+)",
                re.IGNORECASE,
            )
        )
    if "faculty supervisor" in q:
        field_patterns.append(
            re.compile(r"\bfaculty\s+supervisor\s*[:#-]?\s*"
                       r"([^\r\n]+)", re.IGNORECASE)
        )
    if "address" in q:
        address_pattern = re.compile(
            r"\baddress\s*[:#-]\s*([^\r\n]+)", re.IGNORECASE
        )
        bill_to_pattern = re.compile(
            r"\bbill\s+to\s*[:#-]\s*(?:[^\r\n]*?\b(?:ltd|limited|pvt\.?\s+ltd\.?)\.?\s*)?"
            r"([A-Z0-9][^\r\n]+)", re.IGNORECASE
        )
        for index, hit in enumerate(hits, start=1):
            text = str(hit.get("text") or hit.get("snippet") or "")
            sender = address_pattern.search(text)
            bill_to = bill_to_pattern.search(text)
            if sender or bill_to:
                values = []
                if sender:
                    values.append(f"Address: {sender.group(1).strip()}")
                if bill_to:
                    values.append(f"Bill To: {bill_to.group(1).strip()}")
                return "\n".join(values) + f" [{index}]"
    if "title" in q and ("project" in q or "document" in q):
        field_patterns.append(
            re.compile(r"\b(?:minor\s+project\s+)?title\s*[:#-]\s*"
                       r"([^\r\n]+)", re.IGNORECASE)
        )
    if "enrollment" in q:
        enrollment_pattern = re.compile(
            r"\b([A-Z][A-Z .'-]{2,})\s*\(?\s*"
            r"enrollment\s*(?:no\.?|number)\s*[:#-]?\s*"
            r"(\d{6,})\s*\)?", re.IGNORECASE
        )
        for index, hit in enumerate(hits, start=1):
            text = str(hit.get("text") or hit.get("snippet") or "")
            matches = enrollment_pattern.findall(text)
            if matches:
                values = [f"{name.strip()} — {number}" for name, number in matches]
                return "\n".join(values) + f" [{index}]"

    if not field_patterns:
        return None

    for index, hit in enumerate(hits, start=1):
        text = str(hit.get("text") or hit.get("snippet") or "")
        for pattern in field_patterns:
            match = pattern.search(text)
            if not match:
                continue
            value = match.group(1).strip().strip('"\'`')
            if value:
                return f"{value} [{index}]"
    return None


def _faithfulness_warning(text: str) -> bool:
    return not bool(_CITATION_RE.search(text))


def _needs_finalization(text: str) -> bool:
    """Detect visible chain-of-thought-style prose in model content."""
    return bool(llm_client._REASONING_MARKER_RE.search(text or ""))


def _enforce_clean_answer(text: str) -> str:
    """Never expose a draft that still contains visible model reasoning."""
    if _needs_finalization(text):
        return prompt_templates.MISSING_CONTEXT_MESSAGE
    cleaned = text.strip()
    if cleaned != prompt_templates.MISSING_CONTEXT_MESSAGE and not _CITATION_RE.search(cleaned):
        return prompt_templates.MISSING_CONTEXT_MESSAGE
    return cleaned


def _restrict_citations_to_answer(
    answer: str, citations: List[Dict[str, Any]]
) -> tuple[str, List[Dict[str, Any]]]:
    """Return only sources explicitly cited in the final answer.

    Retrieval candidates are evidence for generation, not automatically
    relevant answer sources. This prevents unrelated image chunks (for
    example, a signature crop) from being rendered in every response.
    Citation indexes are compacted so the remaining markers stay clickable.
    """
    if not citations or answer == prompt_templates.MISSING_CONTEXT_MESSAGE:
        return answer, []
    referenced = []
    for raw_index in _CITATION_INDEX_RE.findall(answer):
        index = int(raw_index)
        if index not in referenced and 1 <= index <= len(citations):
            referenced.append(index)
    if not referenced:
        return answer, []

    remap = {old: new for new, old in enumerate(referenced, start=1)}
    compacted = [dict(citations[old - 1]) for old in referenced]
    for new_index, citation in enumerate(compacted, start=1):
        citation["index"] = new_index
    compacted_answer = _CITATION_INDEX_RE.sub(
        lambda match: f"[{remap.get(int(match.group(1)), int(match.group(1)))}]",
        answer,
    )
    return compacted_answer, compacted


def _finalize_answer(draft: str, prompt: str, provider: Optional[str],
                    user_id: Optional[str], model: Optional[str]) -> str:
    if not _needs_finalization(draft):
        return draft
    final_prompt = (
        f"{prompt}\n\n"
        "Untrusted draft from a previous generation (do not copy its reasoning):\n"
        f"{draft}\n\n"
        "Rewrite this as the final answer only."
    )
    try:
        finalized = router.generate(
            prompt_templates.FINALIZE_SYSTEM_PROMPT,
            final_prompt,
            history=[], provider=provider, user_id=user_id, model=model,
        )
        return llm_client.clean_answer(finalized)
    except Exception:
        return draft


def _sanitize_history(history):
    cleaned = []
    for turn in history or []:
        content = (turn.get("content") or "").strip()
        if not content:
            continue
        low = content.lower()
        if _STYLE_ONLY_RE.match(content) or ("format" in low and len(low.split()) <= 8):
            continue
        cleaned.append({"role": turn.get("role", "user"), "content": content})
    return cleaned[-2 * config.HISTORY_TURNS:]


def _trim_history(history):
    return _sanitize_history(history)


def _image_paths_from_hits(hits: List[Dict[str, Any]], session_dir: Optional[Path]) -> List[str]:
    if session_dir is None:
        return []
    paths = []
    for h in hits:
        if h.get("modality") != "image":
            continue
        media_url = h.get("media_url", "")
        parts = media_url.rstrip("/").split("/")
        if parts:
            fname = parts[-1]
            p = session_dir / fname
            if p.exists():
                paths.append(str(p))
    return paths


def prepare_answer_context(
    query: str,
    hits: List[Dict[str, Any]],
    history: Optional[List[Dict[str, str]]] = None,
    session_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Build everything generation needs (system/user prompt, trimmed
    history, citations, resolved image paths) without actually calling the
    LLM. Shared by answer_query() (blocking) and the SSE streaming endpoint
    in main.py, so both paths build the exact same prompt/citations from
    the exact same retrieved evidence — no second, drifting implementation
    of "how we turn hits into a prompt" (brief §51A.16/§51A.28: one
    answer-generation interface)."""
    if not hits:
        return {"citations": [], "system": None, "user": None,
                "history": [], "image_paths": []}
    # brief §13: enforce the context token budget BEFORE building
    # citations, so the citation list the user sees never includes a
    # source that got dropped for budget reasons and was therefore never
    # actually shown to the LLM.
    hits = prompt_templates.truncate_hits_to_budget(hits)
    citations = [_citation(i, h) for i, h in enumerate(hits, start=1)]
    _add_confidence(citations)
    return {
        "system": prompt_templates.SYSTEM_PROMPT,
        "user": prompt_templates.build_user_prompt(query, hits),
        "history": [],
        "citations": citations,
        "image_paths": _image_paths_from_hits(hits, session_dir) or None,
    }


def answer_query(
    query: str,
    hits: List[Dict[str, Any]],
    history: Optional[List[Dict[str, str]]] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    user_id: Optional[str] = None,
    session_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    if not hits:
        return {
            "answer": prompt_templates.MISSING_CONTEXT_MESSAGE,
            "citations": [],
            "used_llm": False,
            "faithfulness_warning": False,
        }

    ctx = prepare_answer_context(query, hits, history, session_dir)

    direct = _direct_field_answer(query, hits, ctx["citations"])
    if direct is not None:
        direct, direct_citations = _restrict_citations_to_answer(
            direct, ctx["citations"]
        )
        result = {
            "answer": direct,
            "citations": direct_citations,
            "used_llm": False,
            "faithfulness_warning": False,
        }
        _audit(user_id, query, result)
        return result

    try:
        text = llm_client.clean_answer(router.generate(ctx["system"], ctx["user"], history=ctx["history"],
                               provider=provider, user_id=user_id,
                               image_paths=ctx["image_paths"], model=model))
        text = _enforce_clean_answer(
            _finalize_answer(text, ctx["user"], provider, user_id, model)
        )
        text, answer_citations = _restrict_citations_to_answer(text, ctx["citations"])
        used_llm = True
    except llm_client.LLMError as exc:
        top = hits[0]
        text = ("[LLM unavailable — showing top retrieved source]\n\n"
                f"{top.get('snippet', '')} [1]")
        used_llm = False

    result = {
        "answer": text,
        "citations": answer_citations if used_llm else ctx["citations"],
        "used_llm": used_llm,
        "faithfulness_warning": _faithfulness_warning(text) if used_llm else False,
    }
    _audit(user_id, query, result)
    return result


def extract_entities(
    query: str,
    hits: List[Dict[str, Any]],
    history: Optional[List[Dict[str, str]]] = None,
    provider: Optional[str] = None,
    user_id: Optional[str] = None,
    session_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    if not hits:
        return {
            "answer": "I could not find anything relevant in this chat's library.",
            "citations": [],
            "used_llm": False,
            "faithfulness_warning": False,
        }

    hits = prompt_templates.truncate_hits_to_budget(hits)  # brief §13
    citations = [_citation(i, h) for i, h in enumerate(hits, start=1)]
    _add_confidence(citations)
    system = prompt_templates.ENTITY_EXTRACTION_PROMPT
    user = (
        f"{prompt_templates.build_context(hits)}\n\n"
        f"Question: {query}\n\n"
        "Extract the requested entities from the sources. "
        "Return normal readable text unless JSON is explicitly requested."
    )
    trimmed = _trim_history(history)

    try:
        text = llm_client.clean_answer(router.generate(system, user, history=trimmed,
                               provider=provider, user_id=user_id)
        )
        used_llm = True
    except llm_client.LLMError as exc:
        top = hits[0]
        text = ("[LLM unavailable — showing top retrieved source]\n\n"
                f"{top.get('snippet', '')} [1]")
        used_llm = False

    result = {
        "answer": text,
        "citations": citations,
        "used_llm": used_llm,
        "faithfulness_warning": _faithfulness_warning(text) if used_llm else False,
    }
    _audit(user_id, query, result)
    return result


def summarize_document(
    query: str,
    hits: List[Dict[str, Any]],
    history: Optional[List[Dict[str, str]]] = None,
    provider: Optional[str] = None,
    user_id: Optional[str] = None,
    session_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    if not hits:
        return {
            "answer": "I could not find anything relevant in this chat's library.",
            "citations": [],
            "used_llm": False,
            "faithfulness_warning": False,
        }

    hits = prompt_templates.truncate_hits_to_budget(hits)  # brief §13
    citations = [_citation(i, h) for i, h in enumerate(hits, start=1)]
    _add_confidence(citations)
    system = prompt_templates.SUMMARY_PROMPT
    user = (
        f"{prompt_templates.build_context(hits)}\n\n"
        f"Question: {query}\n\n"
        "Write a concise summary using only the provided sources."
    )
    trimmed = _trim_history(history)

    try:
        text = llm_client.clean_answer(router.generate(system, user, history=trimmed,
                               provider=provider, user_id=user_id)
        )
        used_llm = True
    except llm_client.LLMError as exc:
        top = hits[0]
        text = ("[LLM unavailable — showing top retrieved source]\n\n"
                f"{top.get('snippet', '')} [1]\n\n(Reason: {exc})")
        used_llm = False

    result = {
        "answer": text,
        "citations": citations,
        "used_llm": used_llm,
        "faithfulness_warning": _faithfulness_warning(text) if used_llm else False,
    }
    _audit(user_id, query, result)
    return result
