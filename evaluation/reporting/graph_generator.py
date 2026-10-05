"""
Graph Generator using matplotlib.
Produces clean, publication-ready figures for evaluation reports (Requirement 22).
Never plots fabricated data for unperformed experiments.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def _save(fig, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_path


def plot_precision_recall_k(
    precision_k: Dict[int, float],
    recall_k: Dict[int, float],
    f1_k: Dict[int, float],
    out_path: Path,
) -> Optional[Path]:
    ks = sorted(set(precision_k.keys()) | set(recall_k.keys()))
    if not ks:
        return None

    p_vals = [precision_k.get(k, 0.0) for k in ks]
    r_vals = [recall_k.get(k, 0.0) for k in ks]
    f_vals = [f1_k.get(k, 0.0) for k in ks]

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(ks, p_vals, marker="o", label="Precision@K", color="#1f77b4", linewidth=2)
    ax.plot(ks, r_vals, marker="s", label="Recall@K", color="#2ca02c", linewidth=2)
    if f1_k:
        ax.plot(ks, f_vals, marker="^", label="F1@K", color="#ff7f0e", linestyle="--", linewidth=1.5)

    for i, k in enumerate(ks):
        ax.annotate(f"{p_vals[i]:.2f}", (k, p_vals[i]), textcoords="offset points", xytext=(0, 6), ha="center", fontsize=8)
        ax.annotate(f"{r_vals[i]:.2f}", (k, r_vals[i]), textcoords="offset points", xytext=(0, -12), ha="center", fontsize=8)

    ax.set_xlabel("Cutoff K", fontsize=11)
    ax.set_ylabel("Score", fontsize=11)
    ax.set_title("Precision, Recall & F1 at Rank K", fontsize=12, fontweight="bold")
    ax.set_ylim(-0.05, 1.1)
    ax.set_xticks(ks)
    ax.legend(loc="lower right")
    ax.grid(True, linestyle=":", alpha=0.6)
    return _save(fig, out_path)


def plot_ranking_metrics(
    metrics: Dict[str, float],
    out_path: Path,
) -> Optional[Path]:
    """Plots MRR, MAP, nDCG@5, nDCG@10, Hit@5, Hit@10."""
    target_keys = ["mrr", "map", "ndcg@5", "ndcg@10", "hit@5", "hit@10"]
    labels = []
    vals = []
    for k in target_keys:
        if k in metrics and metrics[k] is not None:
            labels.append(k.upper())
            vals.append(metrics[k])

    if not vals:
        return None

    fig, ax = plt.subplots(figsize=(6, 4))
    bars = ax.bar(labels, vals, color="#3470a3", edgecolor="black", width=0.55)
    ax.set_ylabel("Score", fontsize=11)
    ax.set_title("Ranking & Retrieval Metrics", fontsize=12, fontweight="bold")
    ax.set_ylim(0, max(1.1, max(vals) * 1.15 if vals else 1.0))
    ax.grid(True, axis="y", linestyle=":", alpha=0.6)

    for bar in bars:
        h = bar.get_height()
        ax.annotate(f"{h:.3f}", (bar.get_x() + bar.get_width() / 2, h), textcoords="offset points", xytext=(0, 4), ha="center", fontsize=9)

    return _save(fig, out_path)


def plot_roc_pr_curves(
    roc_pr_data: Dict[str, Any],
    out_dir: Path,
) -> None:
    if not roc_pr_data.get("applicable"):
        return

    fpr = roc_pr_data.get("fpr")
    tpr = roc_pr_data.get("tpr")
    auc = roc_pr_data.get("roc_auc", 0.0)

    if fpr and tpr:
        fig, ax = plt.subplots(figsize=(5, 5))
        ax.plot(fpr, tpr, color="#2b5c8f", lw=2, label=f"ROC (AUC = {auc:.3f})")
        ax.plot([0, 1], [0, 1], color="gray", linestyle="--", label="Random Chance")
        ax.set_xlabel("False Positive Rate", fontsize=10)
        ax.set_ylabel("True Positive Rate", fontsize=10)
        ax.set_title("ROC Curve (Relevance Classification)", fontsize=11, fontweight="bold")
        ax.legend(loc="lower right")
        ax.grid(True, linestyle=":", alpha=0.6)
        _save(fig, out_dir / "03_roc_curve.png")

    prec = roc_pr_data.get("precision_curve")
    rec = roc_pr_data.get("recall_curve")
    pr_auc = roc_pr_data.get("pr_auc", 0.0)
    if prec and rec:
        fig, ax = plt.subplots(figsize=(5, 5))
        ax.plot(rec, prec, color="#8b3a3a", lw=2, label=f"PR (AUC = {pr_auc:.3f})")
        ax.set_xlabel("Recall", fontsize=10)
        ax.set_ylabel("Precision", fontsize=10)
        ax.set_title("Precision-Recall Curve", fontsize=11, fontweight="bold")
        ax.legend(loc="lower left")
        ax.grid(True, linestyle=":", alpha=0.6)
        _save(fig, out_dir / "04_pr_curve.png")


def plot_stage_latencies(
    stages: Dict[str, Dict[str, float]],
    out_path: Path,
) -> Optional[Path]:
    if not stages:
        return None

    names = []
    p50s = []
    p95s = []

    for name, data in stages.items():
        if data.get("P50") is not None:
            names.append(name.replace("_", "\n"))
            p50s.append(data.get("P50", 0.0))
            p95s.append(data.get("P95", 0.0))

    if not names:
        return None

    import numpy as np
    x = np.arange(len(names))
    width = 0.35

    fig, ax = plt.subplots(figsize=(max(8, len(names) * 1.1), 4.5))
    rects1 = ax.bar(x - width / 2, p50s, width, label="P50", color="#4682b4")
    rects2 = ax.bar(x + width / 2, p95s, width, label="P95", color="#e07b54")

    ax.set_ylabel("Latency (ms)", fontsize=11)
    ax.set_title("Stage-wise Latency Breakdown (P50 vs P95)", fontsize=12, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(names, fontsize=8)
    ax.legend()
    ax.grid(True, axis="y", linestyle=":", alpha=0.6)

    return _save(fig, out_path)


def plot_generation_and_citations(
    gen_metrics: Dict[str, Any],
    cit_metrics: Dict[str, Any],
    out_path: Path,
) -> Optional[Path]:
    labels = []
    vals = []

    pairs = [
        ("Correctness", gen_metrics.get("answer_correctness_mean")),
        ("Relevance", gen_metrics.get("answer_relevance_mean")),
        ("Faithfulness", gen_metrics.get("faithfulness_mean")),
        ("Token F1", gen_metrics.get("token_f1_mean")),
        ("Citation Presence", cit_metrics.get("citation_presence_rate")),
        ("Source Precision", cit_metrics.get("source_level_precision_mean")),
        ("Claim Accuracy", cit_metrics.get("claim_level_accuracy_mean")),
        ("Citation Completeness", cit_metrics.get("citation_completeness_mean")),
    ]

    for label, v in pairs:
        if v is not None:
            labels.append(label)
            vals.append(v)

    if not vals:
        return None

    fig, ax = plt.subplots(figsize=(8, 4))
    bars = ax.barh(labels, vals, color="#5c9287", edgecolor="black")
    ax.set_xlim(0, 1.1)
    ax.set_xlabel("Score", fontsize=11)
    ax.set_title("Generation, Faithfulness & Citation Dimensions", fontsize=12, fontweight="bold")
    ax.grid(True, axis="x", linestyle=":", alpha=0.6)

    for bar in bars:
        w = bar.get_width()
        ax.annotate(f"{w:.3f}", (w, bar.get_y() + bar.get_height() / 2), xytext=(4, 0), textcoords="offset points", va="center", fontsize=8)

    return _save(fig, out_path)


def plot_resource_utilization(
    samples: Sequence[Dict[str, Any]],
    out_path: Path,
) -> Optional[Path]:
    if not samples:
        return None

    cpu = [s.get("cpu_percent") for s in samples if s.get("cpu_percent") is not None]
    ram = [s.get("ram_percent") for s in samples if s.get("ram_percent") is not None]

    if not cpu and not ram:
        return None

    fig, ax = plt.subplots(figsize=(6, 3.5))
    if cpu:
        ax.plot(range(len(cpu)), cpu, label="CPU %", color="#d95f02", lw=1.5)
    if ram:
        ax.plot(range(len(ram)), ram, label="RAM %", color="#7570b3", lw=1.5)

    ax.set_xlabel("Sample index", fontsize=10)
    ax.set_ylabel("Utilization (%)", fontsize=10)
    ax.set_title("System Resource Utilization Over Run", fontsize=11, fontweight="bold")
    ax.set_ylim(0, 105)
    ax.legend()
    ax.grid(True, linestyle=":", alpha=0.6)
    return _save(fig, out_path)


def plot_modality_comparison(
    modalities_data: Dict[str, Dict[str, float]],
    out_path: Path,
) -> Optional[Path]:
    if not modalities_data:
        return None

    mods = list(modalities_data.keys())
    p5 = [modalities_data[m].get("precision@5", 0.0) for m in mods]
    r5 = [modalities_data[m].get("recall@5", 0.0) for m in mods]
    mrr = [modalities_data[m].get("mrr", 0.0) for m in mods]

    import numpy as np
    x = np.arange(len(mods))
    width = 0.25

    fig, ax = plt.subplots(figsize=(6.5, 4))
    ax.bar(x - width, p5, width, label="Precision@5", color="#2b5c8f")
    ax.bar(x, r5, width, label="Recall@5", color="#469b61")
    ax.bar(x + width, mrr, width, label="MRR", color="#e8853b")

    ax.set_ylabel("Score", fontsize=11)
    ax.set_title("Retrieval Performance by Modality Slice", fontsize=12, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels([m.upper() for m in mods], fontsize=10)
    ax.set_ylim(0, 1.15)
    ax.legend()
    ax.grid(True, axis="y", linestyle=":", alpha=0.6)

    return _save(fig, out_path)


def plot_provider_comparison(
    ollama_metrics: Dict[str, Any],
    groq_metrics: Dict[str, Any],
    out_path: Path,
) -> Optional[Path]:
    """Plots comparative metrics for Ollama vs Groq."""
    metrics_to_compare = [
        ("Answer Correctness", "answer_correctness_mean"),
        ("Answer Relevance", "answer_relevance_mean"),
        ("Faithfulness", "faithfulness_mean"),
        ("Token F1", "token_f1_mean"),
    ]

    labels = []
    o_vals = []
    g_vals = []

    o_gen = ollama_metrics.get("generation", {})
    g_gen = groq_metrics.get("generation", {})

    for name, key in metrics_to_compare:
        v1 = o_gen.get(key)
        v2 = g_gen.get(key)
        if v1 is not None or v2 is not None:
            labels.append(name)
            o_vals.append(v1 or 0.0)
            g_vals.append(v2 or 0.0)

    if not labels:
        return None

    import numpy as np
    x = np.arange(len(labels))
    width = 0.35

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(x - width / 2, o_vals, width, label="Ollama (qwen3:4b)", color="#3b6e8c")
    ax.bar(x + width / 2, g_vals, width, label="Groq (llama-3.3-70b)", color="#e07246")

    ax.set_ylabel("Score", fontsize=11)
    ax.set_title("Provider Comparison: Ollama vs Groq", fontsize=12, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylim(0, 1.15)
    ax.legend()
    ax.grid(True, axis="y", linestyle=":", alpha=0.6)

    return _save(fig, out_path)


def generate_all_plots(report_data: Dict[str, Any], out_dir: Path) -> List[Path]:
    """Generates all applicable plots for the run."""
    created = []
    metrics = report_data.get("metrics") or {}
    if hasattr(metrics, "to_dict"):
        metrics = metrics.to_dict()

    ret = metrics.get("retrieval") or {}
    perf = metrics.get("performance") or {}
    gen = metrics.get("generation") or {}
    cit = metrics.get("citations") or {}
    res = metrics.get("resources") or {}
    mod = metrics.get("modality") or {}

    # 1. Precision & Recall @ K
    p_k = {k: ret.get(f"precision@{k}") for k in [1, 3, 5, 10] if ret.get(f"precision@{k}") is not None}
    r_k = {k: ret.get(f"recall@{k}") for k in [1, 3, 5, 10] if ret.get(f"recall@{k}") is not None}
    f1_k = {k: ret.get(f"f1@{k}") for k in [1, 3, 5, 10] if ret.get(f"f1@{k}") is not None}
    p1 = plot_precision_recall_k(p_k, r_k, f1_k, out_dir / "01_precision_recall_at_k.png")
    if p1:
        created.append(p1)

    # 2. Ranking metrics
    p2 = plot_ranking_metrics(ret, out_dir / "02_ranking_metrics.png")
    if p2:
        created.append(p2)

    # 3. ROC / PR Curves
    # The curve data is stored under retrieval.roc_pr_details. Passing the
    # whole retrieval aggregate makes the plotter see no `applicable` flag.
    curve_data = ret.get("roc_pr_details") or {}
    before = set(out_dir.glob("03_roc_curve.png")) | set(out_dir.glob("04_pr_curve.png"))
    plot_roc_pr_curves(curve_data, out_dir)
    after = set(out_dir.glob("03_roc_curve.png")) | set(out_dir.glob("04_pr_curve.png"))
    created.extend(sorted(after - before))

    # 4. Latencies
    stages = perf.get("stages", {})
    p4 = plot_stage_latencies(stages, out_dir / "05_stage_latencies.png")
    if p4:
        created.append(p4)

    # 5. Generation & Citations
    p5 = plot_generation_and_citations(gen, cit, out_dir / "06_generation_and_citations.png")
    if p5:
        created.append(p5)

    # 6. Resources
    samples = report_data.get("resource_samples", [])
    p6 = plot_resource_utilization(samples, out_dir / "07_resource_usage.png")
    if p6:
        created.append(p6)

    # 7. Modality breakdown
    m_items = mod.get("modalities", {})
    p7 = plot_modality_comparison(m_items, out_dir / "08_modality_comparison.png")
    if p7:
        created.append(p7)

    return created
