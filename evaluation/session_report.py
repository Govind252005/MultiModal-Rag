"""Read-only quality and operations reports for persisted chat sessions.

The application stores ordinary text-query metrics on assistant messages, but
does not persist the full retrieved-hit list in the session record. This
module therefore reports operational metrics unconditionally and marks
retrieval-quality metrics unavailable unless the required evidence is present.
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from evaluation.metrics.generation_metrics import exact_match, token_overlap_f1
from evaluation.metrics.citation_metrics import citation_precision


def _load_json(path: Path) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"{type(exc).__name__}: {exc}"
    if not isinstance(value, dict):
        return None, "session file must contain a JSON object"
    return value, None


def _number(values: Iterable[Any]) -> List[float]:
    return [float(value) for value in values if isinstance(value, (int, float))]


def _mean(values: List[float]) -> Optional[float]:
    return round(statistics.mean(values), 3) if values else None


def _percentile(values: List[float], percentile: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((percentile / 100) * (len(ordered) - 1)))
    return round(ordered[index], 3)


def _message_key(message: Dict[str, Any]) -> str:
    return json.dumps(
        {key: message.get(key) for key in ("role", "text", "ts", "provider", "model")},
        sort_keys=True,
        ensure_ascii=False,
    )


def _load_annotations(path: Optional[str]) -> Dict[str, Dict[str, Any]]:
    if not path:
        return {}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("annotation dataset must be a JSON array")
    result: Dict[str, Dict[str, Any]] = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        key = item.get("question_id") or item.get("id") or item.get("question")
        if key:
            result[str(key)] = item
    return result


def _match_annotation(user_message: Dict[str, Any], annotations: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    question_id = user_message.get("question_id")
    if question_id and str(question_id) in annotations:
        return annotations[str(question_id)]
    text = (user_message.get("text") or "").strip()
    for item in annotations.values():
        if text and text == str(item.get("question", "")).strip():
            return item
    return None


def analyze_session(path: Path, annotations: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Analyze one session without modifying or rewriting its source file."""
    data, error = _load_json(path)
    if error:
        return {"session_id": path.stem, "source": str(path), "status": "INVALID", "error": error}

    messages = data.get("messages")
    if not isinstance(messages, list):
        return {"session_id": data.get("id", path.stem), "source": str(path), "status": "INVALID", "error": "messages must be a list"}

    seen = set()
    clean_messages: List[Dict[str, Any]] = []
    duplicate_count = 0
    malformed_count = 0
    for message in messages:
        if not isinstance(message, dict) or not message.get("role"):
            malformed_count += 1
            continue
        key = _message_key(message)
        if key in seen:
            duplicate_count += 1
            continue
        seen.add(key)
        clean_messages.append(message)

    users = [m for m in clean_messages if m.get("role") == "user"]
    assistants = [m for m in clean_messages if m.get("role") == "assistant"]
    metrics = [m.get("metrics") for m in assistants if isinstance(m.get("metrics"), dict)]
    latencies = _number(m.get("total_latency_ms") for m in metrics)
    retrieval_latencies = _number(m.get("retrieval_ms") for m in metrics)
    generation_latencies = _number(m.get("generation_ms") for m in metrics)
    prompt_tokens = _number(m.get("prompt_tokens") for m in metrics)
    completion_tokens = _number(m.get("completion_tokens") for m in metrics)
    providers = Counter(str(m.get("provider")) for m in assistants if m.get("provider"))
    models = Counter(str(m.get("model")) for m in assistants if m.get("model"))
    failed = sum(1 for message in assistants if message.get("error") or message.get("status") == "error")

    quality: Dict[str, Any] = {
        "status": "NOT_RUN",
        "reason": "No annotation dataset was supplied.",
        "retrieval": {"status": "NOT_RUN", "reason": "Session messages do not persist retrieved chunk IDs."},
        "answer": {"status": "NOT_RUN", "reason": "Reference answers are required."},
        "citations": {"status": "NOT_RUN", "reason": "Required citation annotations are required."},
    }
    if annotations:
        answer_scores: List[float] = []
        token_scores: List[float] = []
        citation_scores: List[float] = []
        matched = 0
        for index, user_message in enumerate(m for m in clean_messages if m.get("role") == "user"):
            answer_message = next((m for m in clean_messages[index + 1:] if m.get("role") == "assistant"), None)
            annotation = _match_annotation(user_message, annotations)
            if not annotation or not answer_message:
                continue
            matched += 1
            reference = annotation.get("answer", annotation.get("expected_answer"))
            if reference:
                answer = answer_message.get("text", "")
                answer_scores.append(exact_match(answer, str(reference)))
                token_scores.append(token_overlap_f1(answer, str(reference))["f1"])
            required = annotation.get("required_citations") or []
            if required:
                cited = [c.get("file") for c in answer_message.get("citations", []) if isinstance(c, dict) and c.get("file")]
                citation_scores.append(citation_precision(cited, [item in required for item in cited]))
        quality = {
            "status": "PARTIAL" if matched < len(users) else "COMPLETED",
            "matched_queries": matched,
            "answer": {"status": "COMPLETED" if answer_scores else "NOT_RUN", "exact_match": _mean(answer_scores), "token_f1": _mean(token_scores)},
            "citations": {"status": "COMPLETED" if citation_scores else "NOT_RUN", "precision": _mean(citation_scores)},
            "retrieval": {"status": "NOT_RUN", "reason": "Session messages do not persist retrieved chunk IDs."},
        }

    return {
        "session_id": data.get("id", path.stem),
        "owner_id_present": bool(data.get("owner_id")),
        "source": str(path),
        "status": "OK",
        "title": data.get("title"),
        "created_at": data.get("created_at"),
        "updated_at": data.get("updated_at"),
        "counts": {"user_turns": len(users), "assistant_turns": len(assistants), "successful_generations": len(assistants) - failed, "failed_generations": failed, "malformed_messages": malformed_count, "duplicate_messages_ignored": duplicate_count},
        "providers": dict(providers),
        "models": dict(models),
        "latency_ms": {"mean_total": _mean(latencies), "p50_total": _percentile(latencies, 50), "p95_total": _percentile(latencies, 95), "mean_retrieval": _mean(retrieval_latencies), "mean_generation": _mean(generation_latencies)},
        "tokens": {"prompt_total": sum(prompt_tokens) if prompt_tokens else None, "completion_total": sum(completion_tokens) if completion_tokens else None},
        "quality": quality,
    }


def discover_sessions(sessions_dir: Path, session_ids: Optional[List[str]] = None) -> Tuple[List[Path], List[Dict[str, Any]]]:
    invalid_requests: List[Dict[str, Any]] = []
    if session_ids:
        paths = [sessions_dir / f"{''.join(c for c in sid if c.isalnum() or c in '-_')}.json" for sid in session_ids]
    else:
        paths = sorted(sessions_dir.glob("*.json"))
    return paths, invalid_requests


def build_report(sessions_dir: Path, session_ids: Optional[List[str]] = None, annotations_path: Optional[str] = None) -> Dict[str, Any]:
    annotations = _load_annotations(annotations_path)
    paths, _ = discover_sessions(sessions_dir, session_ids)
    sessions = [analyze_session(path, annotations) for path in paths]
    valid = [item for item in sessions if item.get("status") == "OK"]
    assistant_count = sum(item.get("counts", {}).get("assistant_turns", 0) for item in valid)
    latencies = [item["latency_ms"]["mean_total"] for item in valid if item.get("latency_ms", {}).get("mean_total") is not None]
    return {
        "report_type": "chat_session_quality_and_operations",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sessions_dir": str(sessions_dir),
        "session_filter": session_ids or [],
        "annotation_file": annotations_path,
        "summary": {"sessions_discovered": len(sessions), "valid_sessions": len(valid), "invalid_sessions": len(sessions) - len(valid), "assistant_turns": assistant_count, "mean_session_turn_latency_ms": _mean(latencies)},
        "sessions": sessions,
    }


def render_markdown(report: Dict[str, Any]) -> str:
    summary = report["summary"]
    lines = ["# Chat Session Report", "", f"Generated: {report['generated_at']}", "", "## Summary", "", "| Field | Value |", "|---|---:|"]
    for key, value in summary.items():
        lines.append(f"| {key} | {value if value is not None else 'NOT RUN'} |")
    lines += ["", "## Sessions", "", "| Session | Status | User turns | Assistant turns | Failed | Provider/model |", "|---|---|---:|---:|---:|---|"]
    for item in report["sessions"]:
        counts = item.get("counts", {})
        providers = ", ".join(f"{key}: {value}" for key, value in item.get("providers", {}).items()) or "NOT RUN"
        lines.append(f"| {item.get('session_id')} | {item.get('status')} | {counts.get('user_turns', 'NOT RUN')} | {counts.get('assistant_turns', 'NOT RUN')} | {counts.get('failed_generations', 'NOT RUN')} | {providers} |")
        if item.get("error"):
            lines.append(f"| error | {item['error']} | | | | |")
    lines += ["", "Quality metrics are reported only when the supplied annotations contain the required evidence. Session records do not currently persist retrieved chunk IDs, so retrieval quality is `NOT RUN`." ]
    return "\n".join(lines) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze saved chat sessions without modifying them.")
    parser.add_argument("--sessions-dir", default=None, help="Session directory; defaults to backend.config.SESSIONS_DIR")
    parser.add_argument("--session-id", action="append", dest="session_ids", help="Analyze one session; repeat for multiple IDs")
    parser.add_argument("--annotations", help="Optional JSON QA annotation dataset")
    parser.add_argument("--output", required=True, help="Output JSON or Markdown path")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args(argv)
    if args.sessions_dir:
        sessions_dir = Path(args.sessions_dir)
    else:
        from backend import config
        sessions_dir = config.SESSIONS_DIR
    report = build_report(sessions_dir, args.session_ids, args.annotations)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if args.format == "markdown":
        output.write_text(render_markdown(report), encoding="utf-8")
    else:
        output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Session report: {output}")
    print(f"Sessions: {report['summary']['sessions_discovered']} | valid: {report['summary']['valid_sessions']} | invalid: {report['summary']['invalid_sessions']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())