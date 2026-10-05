"""
Resource utilization snapshot (transformation brief §74).

CPU/RAM are always real (via `psutil`, a genuine new dependency — added
to backend/requirements.txt). GPU/VRAM are best-effort: shelling out to
`nvidia-smi` if it's on PATH, reporting `None`/"not available" otherwise
rather than a fabricated number. No `pynvml` dependency added — a
subprocess call to the same CLI the diagnostic script
(scripts/maintenance/diagnose_gpu.py) already uses is one fewer
dependency to keep in sync with the driver's own Python bindings version.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import Any, Dict, Optional

import psutil


def snapshot() -> Dict[str, Any]:
    """A point-in-time reading — call this repeatedly (e.g. once per
    second during a load test) to build a time series; this module
    intentionally does no sampling/averaging itself, matching brief
    §75's "record throughput/latency/CPU/RAM/VRAM/GPU utilization" for
    a caller-defined observation window."""
    vm = psutil.virtual_memory()
    return {
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "ram_used_gb": round(vm.used / (1024 ** 3), 2),
        "ram_total_gb": round(vm.total / (1024 ** 3), 2),
        "ram_percent": vm.percent,
        "disk_percent": psutil.disk_usage("/").percent,
        "gpu": _gpu_snapshot(),
    }


def _gpu_snapshot() -> Optional[Dict[str, Any]]:
    if not shutil.which("nvidia-smi"):
        return None
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total,memory.used,utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if out.returncode != 0:
            return None
        line = out.stdout.strip().splitlines()[0]
        vram_total, vram_used, util = (float(x.strip()) for x in line.split(","))
        return {
            "vram_used_mb": vram_used, "vram_total_mb": vram_total,
            "vram_percent": round(vram_used / vram_total * 100, 1) if vram_total else None,
            "gpu_utilization_percent": util,
        }
    except Exception:
        return None
