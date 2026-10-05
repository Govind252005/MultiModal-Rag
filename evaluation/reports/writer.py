"""
Report writer (brief §79/§113/§120). Writes exactly what it's given —
if a metric wasn't computed, the caller passes None/"NOT RUN" and this
module prints that literally rather than a fabricated number (brief §113).
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def _fmt(v: Any) -> str:
    if v is None:
        return "NOT RUN"
    if isinstance(v, float):
        return f"{v:.4f}"
    return str(v)


def write_json(report: Dict[str, Any], out_dir: Path, filename: str = "summary.json") -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / filename
    path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return path


def write_csv(rows: list, out_dir: Path, filename: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / filename
    if not rows:
        path.write_text("", encoding="utf-8")
        return path
    # Union of every row's keys, not just the first row's — a real
    # evaluation run legitimately produces heterogeneous rows (a failed
    # question's row has an "error" field a successful one doesn't, or
    # vice versa). Using only rows[0]'s keys raised ValueError on the
    # very first row that didn't match — caught by actually running this
    # against mixed success/failure data, not by inspection.
    fieldnames: list = []
    seen = set()
    for row in rows:
        for k in row.keys():
            if k not in seen:
                seen.add(k)
                fieldnames.append(k)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, restval="")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def write_markdown_summary(report: Dict[str, Any], out_dir: Path,
                           filename: str = "summary.md") -> Path:
    lines = [
        f"# RAG Evaluation Report — {report.get('run_id', '')}",
        "",
        f"Generated: {report.get('timestamp', '')}",
        f"Dataset: {report.get('dataset_path', 'N/A')} "
        f"({report.get('num_questions', 'NOT RUN')} questions)",
        "",
        "## Configuration",
        "```",
        json.dumps(report.get("config", {}), indent=2),
        "```",
        "",
        "## Retrieval",
        "| Metric | Value |",
        "|---|---|",
    ]
    for k, v in (report.get("retrieval") or {}).items():
        if isinstance(v, dict):
            continue
        lines.append(f"| {k} | {_fmt(v)} |")
    lines += ["", "## Generation", "| Metric | Value |", "|---|---|"]
    for k, v in (report.get("generation") or {}).items():
        lines.append(f"| {k} | {_fmt(v)} |")
    lines += ["", "## Citations", "| Metric | Value |", "|---|---|"]
    for k, v in (report.get("citations") or {}).items():
        lines.append(f"| {k} | {_fmt(v)} |")
    lines += ["", "## Performance", "| Metric | Value |", "|---|---|"]
    for k, v in (report.get("performance") or {}).items():
        lines.append(f"| {k} | {_fmt(v)} |")
    if report.get("failures"):
        lines += ["", "## Failure Analysis", ""]
        for f in report["failures"]:
            lines.append(f"- **{f.get('question_id')}** ({f.get('failure_type', 'unknown')}): "
                         f"{f.get('detail', '')}")
    lines += [
        "", "## Honesty note",
        "Any metric shown as `NOT RUN` above was not computed in this run "
        "(e.g. the live backend wasn't reachable, or that category had no "
        "questions in the dataset) — it is not a zero and not an omission "
        "to fill in later with a guess.",
    ]
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / filename
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def print_terminal_summary(report: Dict[str, Any]) -> None:
    """brief §81 terminal format, filled in with whatever was actually
    computed — NOT RUN where it wasn't."""
    W = 60
    print("=" * W)
    print("        MULTIMODAL RAG EVALUATION".center(W))
    print("=" * W)
    print()
    print("Dataset:")
    print(f"    questions:              {report.get('num_questions', 'NOT RUN')}")
    print()
    print("RETRIEVAL")
    print("-" * W)
    for k, v in (report.get("retrieval") or {}).items():
        if isinstance(v, dict):
            continue
        print(f"{k + ':':<28}{_fmt(v):>10}")
    print()
    print("GENERATION")
    print("-" * W)
    for k, v in (report.get("generation") or {}).items():
        print(f"{k + ':':<28}{_fmt(v):>10}")
    print()
    print("CITATIONS")
    print("-" * W)
    for k, v in (report.get("citations") or {}).items():
        print(f"{k + ':':<28}{_fmt(v):>10}")
    print()
    print("PERFORMANCE")
    print("-" * W)
    for k, v in (report.get("performance") or {}).items():
        print(f"{k + ':':<28}{_fmt(v):>10}")
    print()
    print("REPORT:")
    print(f"{report.get('report_dir', 'NOT WRITTEN')}")
    print("=" * W)


def new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
