"""
Storage footprint monitoring for ChromaDB, SQLite indices, and caches.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Optional


def get_dir_size_bytes(path: str | Path) -> int:
    """Calculates total disk usage of a directory recursively."""
    p = Path(path)
    if not p.exists():
        return 0
    if p.is_file():
        return p.stat().st_size
    total = 0
    for root, _, files in os.walk(p):
        for f in files:
            fp = os.path.join(root, f)
            try:
                total += os.path.getsize(fp)
            except OSError:
                pass
    return total


def get_storage_footprint(chroma_dir: Optional[str | Path] = None) -> Dict[str, float]:
    """
    Returns storage footprints in MB.
    Locates ChromaDB persistence path automatically if not explicitly given.
    """
    if chroma_dir is None:
        try:
            import config
            chroma_dir = getattr(config, "CHROMA_DIR", "data/chroma")
        except Exception:
            chroma_dir = "data/chroma"

    chroma_path = Path(chroma_dir)
    bytes_used = get_dir_size_bytes(chroma_path)
    mb_used = round(bytes_used / (1024.0 * 1024.0), 2)

    return {
        "chromadb_size_mb": mb_used,
        "chromadb_path": str(chroma_path),
    }
