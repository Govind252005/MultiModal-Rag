"""
System and environment capture for reproducible evaluations.
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict


def get_git_commit() -> str:
    """Returns the current git commit hash, or 'unavailable'."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
        )
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass
    return "unavailable"


def get_gpu_info() -> Dict[str, Any]:
    """Captures GPU information accurately without guessing or fabricating."""
    info: Dict[str, Any] = {
        "available": False,
        "device_name": None,
        "cuda_version": None,
        "count": 0,
    }
    try:
        import torch  # type: ignore
        if torch.cuda.is_available():
            info["available"] = True
            info["count"] = torch.cuda.device_count()
            info["device_name"] = torch.cuda.get_device_name(0)
            info["cuda_version"] = torch.version.cuda
            return info
    except Exception:
        pass

    # Fallback check via nvidia-smi if torch is not installed in the current env
    try:
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
        )
        if res.returncode == 0 and res.stdout.strip():
            lines = res.stdout.strip().splitlines()
            info["available"] = True
            info["count"] = len(lines)
            info["device_name"] = lines[0].split(",")[0].strip()
            return info
    except Exception:
        pass

    return info


def capture_environment_metadata(backend_config: Any = None) -> Dict[str, Any]:
    """Collects complete reproducibility environment metadata."""
    gpu = get_gpu_info()

    env_meta = {
        "python_version": sys.version,
        "platform": platform.platform(),
        "processor": platform.processor(),
        "machine": platform.machine(),
        "os": os.name,
        "git_commit": get_git_commit(),
        "gpu": gpu,
    }

    # Extract backend model metadata if config module is provided or accessible
    if backend_config is not None:
        env_meta.update({
            "text_embed_model": getattr(backend_config, "TEXT_EMBED_MODEL", None),
            "clip_model": getattr(backend_config, "CLIP_MODEL", None),
            "rerank_model": getattr(backend_config, "RERANK_MODEL", None),
            "llm_model": getattr(backend_config, "LLM_MODEL", None),
            "groq_model": getattr(backend_config, "GROQ_MODEL", None),
            "whisper_model": getattr(backend_config, "WHISPER_MODEL", None),
            "ocr_engine": getattr(backend_config, "OCR_ENGINE", None),
            "default_top_k": getattr(backend_config, "DEFAULT_TOP_K", None),
            "chunk_size": getattr(backend_config, "CHUNK_SIZE", None),
            "chunk_overlap": getattr(backend_config, "CHUNK_OVERLAP", None),
        })
    else:
        try:
            import config as b_config
            env_meta.update({
                "text_embed_model": getattr(b_config, "TEXT_EMBED_MODEL", None),
                "clip_model": getattr(b_config, "CLIP_MODEL", None),
                "rerank_model": getattr(b_config, "RERANK_MODEL", None),
                "llm_model": getattr(b_config, "LLM_MODEL", None),
                "groq_model": getattr(b_config, "GROQ_MODEL", None),
                "whisper_model": getattr(b_config, "WHISPER_MODEL", None),
                "ocr_engine": getattr(b_config, "OCR_ENGINE", None),
                "default_top_k": getattr(b_config, "DEFAULT_TOP_K", None),
                "chunk_size": getattr(b_config, "CHUNK_SIZE", None),
                "chunk_overlap": getattr(b_config, "CHUNK_OVERLAP", None),
            })
        except Exception:
            pass

    return env_meta
