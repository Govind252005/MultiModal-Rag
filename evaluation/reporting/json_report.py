"""
JSON report serialization.
Writes summary.json, raw_results.json, config.json, and environment.json.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


def write_json_file(data: Any, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    return out_path


def save_json_bundle(
    report_dict: Dict[str, Any],
    raw_results: List[Dict[str, Any]],
    config_dict: Dict[str, Any],
    env_dict: Dict[str, Any],
    out_dir: Path,
) -> None:
    write_json_file(report_dict, out_dir / "summary.json")
    write_json_file(raw_results, out_dir / "raw_results.json")
    write_json_file(config_dict, out_dir / "config.json")
    write_json_file(env_dict, out_dir / "environment.json")
