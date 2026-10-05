"""
Markdown report generator for GitHub/publication summaries.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def _fmt(val: Any) -> str:
    if val is None:
        return "NOT RUN"
    if isinstance(val, float):
        return f"{val:.4f}"
    return str(val)


def generate_markdown_summary(report_data: Dict[str, Any]) -> str:
    lines = [
        f"# Multimodal RAG Evaluation Report — {report_data.get('run_id', '')}",
        "",
        f"**Timestamp:** {report_data.get('timestamp', 'N/A')}  ",
        f"**Provider:** {str(report_data.get('provider', 'N/A')).upper()}  ",
        f"**Model:** {report_data.get('model', 'N/A')}  ",
        f"**Dataset:** `{report_data.get('dataset_path', 'N/A')}` ({report_data.get('num_questions', 'NOT RUN')} questions)  ",
        f"**Errors:** {report_data.get('num_errors', 0)}  ",
        "",
        "## Configuration & Environment",
        "```json",
        json.dumps(report_data.get("config", {}), indent=2),
        "```",
        "",
    ]

    metrics = report_data.get("metrics") or {}
    if hasattr(metrics, "to_dict"):
        metrics = metrics.to_dict()

    # Retrieval
    ret = metrics.get("retrieval") or {}
    lines.append("## Retrieval Quality Metrics")
    lines.append("| Metric | Value |")
    lines.append("| :--- | :--- |")
    if ret:
        for k, v in ret.items():
            if not isinstance(v, (dict, list)):
                lines.append(f"| {k} | {_fmt(v)} |")
    else:
        lines.append("| Status | NOT RUN |")
    lines.append("")

    # Generation
    gen = metrics.get("generation") or {}
    lines.append("## Generation & Faithfulness Metrics")
    lines.append("| Metric | Value |")
    lines.append("| :--- | :--- |")
    if gen:
        for k, v in gen.items():
            if not isinstance(v, (dict, list)):
                lines.append(f"| {k} | {_fmt(v)} |")
    else:
        lines.append("| Status | NOT RUN |")
    lines.append("")

    # Citations
    cit = metrics.get("citations") or {}
    lines.append("## Citation Dimensions (Requirement 11)")
    lines.append("| Citation Dimension | Value |")
    lines.append("| :--- | :--- |")
    if cit:
        for k, v in cit.items():
            if not isinstance(v, (dict, list)):
                lines.append(f"| {k} | {_fmt(v)} |")
    else:
        lines.append("| Status | NOT RUN |")
    lines.append("")

    # Performance
    perf = metrics.get("performance") or {}
    stages = perf.get("stages", {})
    lines.append("## Latency & Stage-wise Performance")
    if stages:
        lines.append("| Stage | P50 (ms) | P75 (ms) | P90 (ms) | P95 (ms) | P99 (ms) |")
        lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
        for stage, p_vals in stages.items():
            lines.append(f"| {stage} | {_fmt(p_vals.get('P50'))} | {_fmt(p_vals.get('P75'))} | {_fmt(p_vals.get('P90'))} | {_fmt(p_vals.get('P95'))} | {_fmt(p_vals.get('P99'))} |")
    elif perf:
        lines.append("| Metric | Value |")
        lines.append("| :--- | :--- |")
        for k, v in perf.items():
            if not isinstance(v, dict):
                lines.append(f"| {k} | {_fmt(v)} |")
    lines.append("")

    # Resources
    res = metrics.get("resources") or {}
    lines.append("## System Resources")
    lines.append("| Resource Metric | Value |")
    lines.append("| :--- | :--- |")
    if res and res.get("status") != "NOT_RUN":
        for k, v in res.items():
            if not isinstance(v, (dict, list)):
                lines.append(f"| {k} | {_fmt(v)} |")
    else:
        lines.append("| Status | NOT RUN |")
    lines.append("")

    # Modality
    mod = metrics.get("modality") or {}
    lines.append("## Modality Breakdown")
    if mod and mod.get("modalities"):
        lines.append("| Modality | P@5 | R@5 | F1@5 | MRR | nDCG@5 | Hit@5 | Samples |")
        lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
        for m_name, m_data in mod.get("modalities", {}).items():
            lines.append(f"| {m_name} | {_fmt(m_data.get('precision@5'))} | {_fmt(m_data.get('recall@5'))} | {_fmt(m_data.get('f1@5'))} | {_fmt(m_data.get('mrr'))} | {_fmt(m_data.get('ndcg@5'))} | {_fmt(m_data.get('hit@5'))} | {m_data.get('count', 'N/A')} |")
    else:
        lines.append(f"Status: {mod.get('status', 'NOT RUN')} ({mod.get('reason', 'Dataset pending')})")
    lines.append("")

    # Failures
    failures = report_data.get("failures", [])
    if failures:
        lines.append("## Failures & Errors")
        for f in failures:
            lines.append(f"- **{f.get('question_id')}** [{f.get('error_type', 'error')}]: {f.get('error', f.get('detail', ''))}")
        lines.append("")

    lines.append("---")
    lines.append("*Note: Metrics marked `NOT RUN` reflect missing datasets or unperformed experiments without synthetic data fabrication.*")
    return "\n".join(lines)


def write_markdown_report(report_data: Dict[str, Any], out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    md = generate_markdown_summary(report_data)
    out_path.write_text(md, encoding="utf-8")
    return out_path
