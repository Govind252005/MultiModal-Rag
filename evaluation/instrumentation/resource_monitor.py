"""
Consolidated system resource monitor.
Takes point-in-time snapshots of CPU, RAM, VRAM, and ChromaDB storage footprint.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional
import psutil

from evaluation.instrumentation.gpu_monitor import sample_gpu
from evaluation.instrumentation.storage_monitor import get_storage_footprint


class ResourceMonitor:
    """Manages periodic or per-question resource sampling."""

    def __init__(self, chroma_dir: Optional[str] = None):
        self.chroma_dir = chroma_dir
        self.samples: list[Dict[str, Any]] = []

    def snapshot(self) -> Dict[str, Any]:
        """Takes an exact system resource snapshot."""
        vm = psutil.virtual_memory()
        cpu_pct = psutil.cpu_percent(interval=None)
        ram_pct = vm.percent
        ram_used_gb = round((vm.total - vm.available) / (1024.0 ** 3), 2)

        gpu_info = sample_gpu()
        storage = get_storage_footprint(self.chroma_dir)

        snap = {
            "cpu_percent": cpu_pct,
            "ram_percent": ram_pct,
            "ram_used_gb": ram_used_gb,
            "gpu": gpu_info,
            "chromadb_size_mb": storage.get("chromadb_size_mb"),
        }
        self.samples.append(snap)
        return snap

    def get_all_samples(self) -> list[Dict[str, Any]]:
        return list(self.samples)

    def clear(self) -> None:
        self.samples.clear()
