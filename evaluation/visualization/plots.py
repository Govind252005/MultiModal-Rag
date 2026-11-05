"""
Graph generation (brief §80/§118/§119). Every function here takes the
already-computed metric numbers and draws+saves one PNG. Nothing in this
file invents data — if the caller has no data for a metric, don't call
the corresponding plot function (the runner checks this; see
evaluation/runner/run_eval.py).
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Sequence

import matplotlib
matplotlib.use("Agg")  # headless — this runs in a terminal/CI, not a notebook
import matplotlib.pyplot as plt


def _save(fig, out_dir: Path, filename: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / filename
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_at_k_curve(values_by_k: Dict[int, float], title: str, ylabel: str,
                    out_dir: Path, filename: str) -> Path:
    ks = sorted(values_by_k.keys())
    vals = [values_by_k[k] for k in ks]
    fig, ax = plt.subplots(figsize=(5, 3.5))
    ax.plot(ks, vals, marker="o")
    ax.set_xlabel("K")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.set_ylim(0, 1.05)
    ax.grid(True, alpha=0.3)
    return _save(fig, out_dir, filename)


def plot_bar_comparison(labels: Sequence[str], values: Sequence[float], title: str,
                        ylabel: str, out_dir: Path, filename: str) -> Path:
    fig, ax = plt.subplots(figsize=(5, 3.5))
    ax.bar(labels, values)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.set_ylim(0, max(1.05, max(values) * 1.1 if values else 1.0))
    ax.grid(True, axis="y", alpha=0.3)
    fig.autofmt_xdate(rotation=30)
    return _save(fig, out_dir, filename)


def plot_roc_curve(fpr: Sequence[float], tpr: Sequence[float], auc: float,
                   out_dir: Path, filename: str) -> Path:
    fig, ax = plt.subplots(figsize=(4.5, 4.5))
    ax.plot(fpr, tpr, label=f"ROC (AUC = {auc:.3f})")
    ax.plot([0, 1], [0, 1], linestyle="--", color="gray", label="Random")
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.set_title("ROC Curve")
    ax.legend(loc="lower right")
    ax.grid(True, alpha=0.3)
    return _save(fig, out_dir, filename)


def plot_latency_percentiles(percentiles: Dict[str, float], out_dir: Path,
                             filename: str, title: str = "Query Latency") -> Path:
    labels = list(percentiles.keys())
    values = [percentiles[k] for k in labels]
    fig, ax = plt.subplots(figsize=(5, 3.5))
    ax.bar(labels, values, color="#4a7ba6")
    ax.set_ylabel("Latency (ms)")
    ax.set_title(title)
    ax.grid(True, axis="y", alpha=0.3)
    return _save(fig, out_dir, filename)


def plot_resource_usage(series: Dict[str, List[float]], out_dir: Path,
                        filename: str, title: str = "Resource Usage") -> Path:
    fig, ax = plt.subplots(figsize=(5.5, 3.5))
    for name, values in series.items():
        ax.plot(range(len(values)), values, label=name)
    ax.set_xlabel("Sample")
    ax.set_ylabel("Usage (%)")
    ax.set_title(title)
    ax.legend()
    ax.grid(True, alpha=0.3)
    return _save(fig, out_dir, filename)
