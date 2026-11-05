"""
Resource monitoring and metric aggregation.
Monitors CPU, RAM, VRAM, GPU utilization, and ChromaDB storage footprint.
Never reports unmeasured GPU/VRAM values.
"""

from __future__ import annotations

import statistics
from typing import Any, Dict, List, Optional, Sequence


def aggregate_resource_samples(
    samples: Sequence[Dict[str, Any]]
) -> Dict[str, Any]:
    """Aggregates a sequence of resource snapshots."""
    if not samples:
        return {
            "cpu_percent_mean": None,
            "cpu_percent_peak": None,
            "ram_percent_mean": None,
            "ram_percent_peak": None,
            "ram_used_gb_peak": None,
            "gpu_utilization_mean": None,
            "gpu_utilization_peak": None,
            "vram_used_mb_peak": None,
            "chromadb_size_mb": None,
        }

    cpu_vals = [s["cpu_percent"] for s in samples if s.get("cpu_percent") is not None]
    ram_pct = [s["ram_percent"] for s in samples if s.get("ram_percent") is not None]
    ram_gb = [s["ram_used_gb"] for s in samples if s.get("ram_used_gb") is not None]

    gpu_util = []
    vram_mb = []
    for s in samples:
        gpu = s.get("gpu")
        if isinstance(gpu, dict):
            if gpu.get("gpu_utilization_percent") is not None:
                gpu_util.append(gpu["gpu_utilization_percent"])
            if gpu.get("vram_used_mb") is not None:
                vram_mb.append(gpu["vram_used_mb"])

    chroma_sizes = [s["chromadb_size_mb"] for s in samples if s.get("chromadb_size_mb") is not None]

    return {
        "cpu_percent_mean": round(statistics.mean(cpu_vals), 1) if cpu_vals else None,
        "cpu_percent_peak": round(max(cpu_vals), 1) if cpu_vals else None,
        "ram_percent_mean": round(statistics.mean(ram_pct), 1) if ram_pct else None,
        "ram_percent_peak": round(max(ram_pct), 1) if ram_pct else None,
        "ram_used_gb_peak": round(max(ram_gb), 2) if ram_gb else None,
        "gpu_utilization_mean": round(statistics.mean(gpu_util), 1) if gpu_util else None,
        "gpu_utilization_peak": round(max(gpu_util), 1) if gpu_util else None,
        "vram_used_mb_peak": round(max(vram_mb), 1) if vram_mb else None,
        "chromadb_size_mb": round(chroma_sizes[-1], 2) if chroma_sizes else None,
        "num_samples": len(samples),
    }
