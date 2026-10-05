"""
Paper Table Generator (Requirement 23).
Generates research paper tables in CSV, Markdown, and PNG:
- Table 5: Baseline retrieval
- Table 6: Hybrid retrieval
- Table 7: Cross-encoder / reranking
- Table 8: Modality-wise retrieval
- Table 9: Generation / citation / faithfulness
- Table 11: Performance / resource metrics
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def _fmt(v: Any) -> str:
    if v is None:
        return "NOT RUN"
    if isinstance(v, float):
        return f"{v:.4f}"
    return str(v)


def _render_table_png(
    title: str,
    headers: List[str],
    rows: List[List[str]],
    out_path: Path,
) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(max(7, len(headers) * 1.5), max(2.5, len(rows) * 0.45 + 1.2)))
    ax.axis("off")
    ax.set_title(title, fontsize=12, fontweight="bold", pad=12)

    table = ax.table(
        cellText=rows,
        colLabels=headers,
        loc="center",
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1.2, 1.4)

    # Style header row
    for j in range(len(headers)):
        table[(0, j)].set_facecolor("#2c3e50")
        table[(0, j)].get_text().set_color("white")
        table[(0, j)].get_text().set_weight("bold")

    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return out_path


def _save_table(
    title: str,
    headers: List[str],
    rows: List[List[str]],
    base_name: str,
    out_dir: Path,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. CSV
    csv_path = out_dir / f"{base_name}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)

    # 2. Markdown
    md_path = out_dir / f"{base_name}.md"
    lines = [f"### {title}", "", "| " + " | ".join(headers) + " |", "| " + " | ".join([":---:"] * len(headers)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(c) for c in row) + " |")
    md_path.write_text("\n".join(lines), encoding="utf-8")

    # 3. PNG
    png_path = out_dir / f"{base_name}.png"
    _render_table_png(title, headers, rows, png_path)


def generate_paper_tables(report_data: Dict[str, Any], out_dir: Path) -> None:
    metrics = report_data.get("metrics") or {}
    if hasattr(metrics, "to_dict"):
        metrics = metrics.to_dict()

    ret = metrics.get("retrieval") or {}
    gen = metrics.get("generation") or {}
    cit = metrics.get("citations") or {}
    perf = metrics.get("performance") or {}
    res = metrics.get("resources") or {}
    mod = metrics.get("modality") or {}
    abl = metrics.get("ablation") or {}

    # -------------------------------------------------------------
    # Table 5: Baseline Retrieval
    # -------------------------------------------------------------
    t5_headers = ["Configuration", "P@1", "P@5", "R@1", "R@5", "MRR", "MAP", "nDCG@5"]
    t5_rows = []
    # If ablation experiments have B1 (BM25) and B2 (Dense)
    abl_runs = {e.get("experiment_id"): e for e in abl.get("experiments", [])} if isinstance(abl.get("experiments"), list) else {}

    b1 = abl_runs.get("B1", {})
    b1_m = b1.get("retrieval_metrics", {})
    t5_rows.append([
        "BM25 Only (B1)",
        _fmt(b1_m.get("precision@1")),
        _fmt(b1_m.get("precision@5")),
        _fmt(b1_m.get("recall@1")),
        _fmt(b1_m.get("recall@5")),
        _fmt(b1_m.get("mrr")),
        _fmt(b1_m.get("map")),
        _fmt(b1_m.get("ndcg@5")),
    ])

    b2 = abl_runs.get("B2", {})
    b2_m = b2.get("retrieval_metrics", {})
    t5_rows.append([
        "Dense Only (B2)",
        _fmt(b2_m.get("precision@1")),
        _fmt(b2_m.get("precision@5")),
        _fmt(b2_m.get("recall@1")),
        _fmt(b2_m.get("recall@5")),
        _fmt(b2_m.get("mrr")),
        _fmt(b2_m.get("map")),
        _fmt(b2_m.get("ndcg@5")),
    ])
    _save_table("Table 5: Baseline Retrieval", t5_headers, t5_rows, "table_05_baseline_retrieval", out_dir)

    # -------------------------------------------------------------
    # Table 6: Hybrid Retrieval (B3, B4, B4')
    # -------------------------------------------------------------
    t6_headers = ["Hybrid Pipeline", "P@5", "R@5", "F1@5", "MRR", "MAP", "nDCG@5", "Hit@5"]
    t6_rows = []
    b3 = abl_runs.get("B3", {})
    b3_m = b3.get("retrieval_metrics", {})
    t6_rows.append([
        "Dense + BM25 (B3)",
        _fmt(b3_m.get("precision@5")),
        _fmt(b3_m.get("recall@5")),
        _fmt(b3_m.get("f1@5")),
        _fmt(b3_m.get("mrr")),
        _fmt(b3_m.get("map")),
        _fmt(b3_m.get("ndcg@5")),
        _fmt(b3_m.get("hit@5")),
    ])

    b4 = abl_runs.get("B4", {})
    b4_m = b4.get("retrieval_metrics", {})
    t6_rows.append([
        "Dense + BM25 + CLIP (B4)",
        _fmt(b4_m.get("precision@5")),
        _fmt(b4_m.get("recall@5")),
        _fmt(b4_m.get("f1@5")),
        _fmt(b4_m.get("mrr")),
        _fmt(b4_m.get("map")),
        _fmt(b4_m.get("ndcg@5")),
        _fmt(b4_m.get("hit@5")),
    ])

    b4p = abl_runs.get("B4_prime", {})
    b4p_m = b4p.get("retrieval_metrics", {})
    t6_rows.append([
        "Dense + BM25 + CLIP + RRF (B4')",
        _fmt(b4p_m.get("precision@5")),
        _fmt(b4p_m.get("recall@5")),
        _fmt(b4p_m.get("f1@5")),
        _fmt(b4p_m.get("mrr")),
        _fmt(b4p_m.get("map")),
        _fmt(b4p_m.get("ndcg@5")),
        _fmt(b4p_m.get("hit@5")),
    ])
    _save_table("Table 6: Hybrid Retrieval Fusion", t6_headers, t6_rows, "table_06_hybrid_retrieval", out_dir)

    # -------------------------------------------------------------
    # Table 7: Cross-Encoder / Reranking (B5 vs non-reranked)
    # -------------------------------------------------------------
    t7_headers = ["Stage", "P@5", "R@5", "MRR", "MAP", "nDCG@5", "Latency P50 (ms)"]
    t7_rows = [
        [
            "Pre-Reranked (B4')",
            _fmt(b4p_m.get("precision@5")),
            _fmt(b4p_m.get("recall@5")),
            _fmt(b4p_m.get("mrr")),
            _fmt(b4p_m.get("map")),
            _fmt(b4p_m.get("ndcg@5")),
            _fmt(b4p.get("latency_metrics", {}).get("P50")),
        ],
        [
            "Full Reranked (B5)",
            _fmt(ret.get("precision@5")),
            _fmt(ret.get("recall@5")),
            _fmt(ret.get("mrr")),
            _fmt(ret.get("map")),
            _fmt(ret.get("ndcg@5")),
            _fmt(perf.get("stages", {}).get("cross_encoder", {}).get("P50") or perf.get("query_latency_p50_ms")),
        ],
    ]
    _save_table("Table 7: Cross-Encoder Reranking Impact", t7_headers, t7_rows, "table_07_reranking_impact", out_dir)

    # -------------------------------------------------------------
    # Table 8: Modality-wise Retrieval
    # -------------------------------------------------------------
    t8_headers = ["Modality Slice", "Questions", "P@5", "R@5", "MRR", "nDCG@5", "Hit@5"]
    t8_rows = []
    mod_items = mod.get("modalities", {})
    if mod_items:
        for m_name, m_data in mod_items.items():
            t8_rows.append([
                m_name.upper(),
                str(m_data.get("count", 0)),
                _fmt(m_data.get("precision@5")),
                _fmt(m_data.get("recall@5")),
                _fmt(m_data.get("mrr")),
                _fmt(m_data.get("ndcg@5")),
                _fmt(m_data.get("hit@5")),
            ])
    else:
        t8_rows.append(["Overall Corpus", str(report_data.get("num_questions", 0)), _fmt(ret.get("precision@5")), _fmt(ret.get("recall@5")), _fmt(ret.get("mrr")), _fmt(ret.get("ndcg@5")), _fmt(ret.get("hit@5"))])
    _save_table("Table 8: Modality-wise Retrieval Evaluation", t8_headers, t8_rows, "table_08_modality_retrieval", out_dir)

    # -------------------------------------------------------------
    # Table 9: Generation, Citation, and Faithfulness
    # -------------------------------------------------------------
    t9_headers = ["Dimension / Metric", "Value"]
    t9_rows = [
        ["Answer Correctness (Mean)", _fmt(gen.get("answer_correctness_mean"))],
        ["Answer Relevance (Mean)", _fmt(gen.get("answer_relevance_mean"))],
        ["Semantic Faithfulness (Mean)", _fmt(gen.get("faithfulness_mean"))],
        ["Citation Presence Rate", _fmt(cit.get("citation_presence_rate"))],
        ["Source-level Citation Precision", _fmt(cit.get("source_level_precision_mean"))],
        ["Claim-level Citation Accuracy", _fmt(cit.get("claim_level_accuracy_mean"))],
        ["Citation Completeness (Coverage)", _fmt(cit.get("citation_completeness_mean"))],
        ["Abstention Accuracy", _fmt(gen.get("abstention_accuracy"))],
    ]
    _save_table("Table 9: Generation, Faithfulness, and Citation Quality", t9_headers, t9_rows, "table_09_generation_citations", out_dir)

    # -------------------------------------------------------------
    # Table 11: Performance & Resource Footprint
    # -------------------------------------------------------------
    t11_headers = ["System Dimension", "Measurement", "Value"]
    t11_rows = [
        ["End-to-End Latency", "P50", f"{_fmt(perf.get('query_latency_p50_ms'))} ms"],
        ["End-to-End Latency", "P95", f"{_fmt(perf.get('query_latency_p95_ms'))} ms"],
        ["Dense Retrieval", "P50", f"{_fmt(perf.get('stages', {}).get('dense_retrieval', {}).get('P50'))} ms"],
        ["BM25 Retrieval", "P50", f"{_fmt(perf.get('stages', {}).get('bm25_retrieval', {}).get('P50'))} ms"],
        ["Cross-Encoder Rerank", "P50", f"{_fmt(perf.get('stages', {}).get('cross_encoder', {}).get('P50'))} ms"],
        ["LLM Generation", "P50", f"{_fmt(perf.get('stages', {}).get('llm_generation', {}).get('P50'))} ms"],
        ["System CPU", "Peak %", f"{_fmt(res.get('cpu_percent_peak'))} %"],
        ["System RAM", "Peak GB", f"{_fmt(res.get('ram_used_gb_peak'))} GB"],
        ["GPU Utilization", "Peak %", f"{_fmt(res.get('gpu_utilization_peak'))} %"],
        ["GPU VRAM", "Peak MB", f"{_fmt(res.get('vram_used_mb_peak'))} MB"],
        ["ChromaDB Vector Store", "Footprint", f"{_fmt(res.get('chromadb_size_mb'))} MB"],
    ]
    _save_table("Table 11: End-to-End Latency and Resource Utilization", t11_headers, t11_rows, "table_11_performance_resources", out_dir)
