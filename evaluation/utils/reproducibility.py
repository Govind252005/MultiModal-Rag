"""
Reproducibility utilities: dataset hashing, seed management, run id generation.
"""

from __future__ import annotations

import hashlib
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def compute_file_hash(path: str | Path) -> str:
    """Computes SHA-256 hash of a file for exact tracking."""
    p = Path(path)
    if not p.is_file():
        return "file_not_found"
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def set_seed(seed: int = 42) -> None:
    """Sets random seeds for reproducibility."""
    random.seed(seed)
    try:
        import numpy as np  # type: ignore
        np.random.seed(seed)
    except Exception:
        pass
    try:
        import torch  # type: ignore
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
    except Exception:
        pass


def generate_run_id() -> str:
    """Generates an ISO-like formatted run timestamp."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
