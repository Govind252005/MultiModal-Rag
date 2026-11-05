"""
Accurate GPU and VRAM monitoring without fabricated values.
"""

from __future__ import annotations

import subprocess
from typing import Any, Dict, Optional


def sample_gpu() -> Optional[Dict[str, Any]]:
    """
    Returns GPU utilization and VRAM if measurable.
    Returns None if no GPU or tools are available. Never fabricates values.
    """
    # nvidia-smi reports actual device utilization. Prefer it to
    # torch.cuda.memory_allocated(), which cannot report SM utilization.
    try:
        cmd = [
            "nvidia-smi",
            "--query-gpu=name,utilization.gpu,memory.used",
            "--format=csv,noheader,nounits"
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=2)
        if res.returncode == 0 and res.stdout.strip():
            parts = res.stdout.strip().splitlines()[0].split(",")
            if len(parts) >= 3:
                gpu_util = float(parts[1].strip())
                mem_used = float(parts[2].strip())
                return {
                    "available": True,
                    "device_name": parts[0].strip(),
                    "gpu_utilization_percent": gpu_util,
                    "vram_used_mb": mem_used,
                }
    except Exception:
        pass

    # Fallback when nvidia-smi is unavailable. PyTorch cannot provide SM
    # utilization, so that field remains explicitly unmeasured.
    try:
        import torch  # type: ignore
        if torch.cuda.is_available():
            dev = 0
            vram_bytes = torch.cuda.memory_allocated(dev)
            return {
                "available": True,
                "device_name": torch.cuda.get_device_name(dev),
                "vram_used_mb": round(vram_bytes / (1024.0 * 1024.0), 1),
                "gpu_utilization_percent": None,
            }
    except Exception:
        pass

    return None
