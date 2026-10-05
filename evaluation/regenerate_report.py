"""Regenerate reports from an existing evaluation result directory.

This module deliberately imports no provider, backend-generation, or HTTP
client code. It preserves the saved summary/raw results and marks metrics
that cannot be recomputed from the saved evidence instead of rerunning work.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, List

from evaluation.reporting.markdown_report import write_markdown_report


def load_bundle(input_path: Path) -> Dict[str, Any]:
    root = input_path if input_path.is_dir() else input_path.parent
    summary_path = input_path / "summary.json" if input_path.is_dir() else input_path
    if not summary_path.is_file():
        raise ValueError(f"summary.json not found at {summary_path}")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if not isinstance(summary, dict):
        raise ValueError("summary.json must contain an object")
    raw_path = root / "raw_results.json"
    raw_results = []
    if raw_path.is_file():
        raw_results = json.loads(raw_path.read_text(encoding="utf-8"))
        if not isinstance(raw_results, list):
            raise ValueError("raw_results.json must contain an array")
    return {"root": root, "summary": summary, "raw_results": raw_results}


def regenerate(input_path: Path, output_dir: Path) -> Dict[str, Any]:
    bundle = load_bundle(input_path)
    source = bundle["summary"]
    report = dict(source)
    report["report_type"] = "regenerated_from_saved_results"
    report["regenerated_at"] = datetime.now(timezone.utc).isoformat()
    report["regenerated_from"] = str(bundle["root"])
    report["regeneration"] = {
        "providers_called": False,
        "inference_rerun": False,
        "retrieval_rerun": False,
        "raw_results_preserved": bool(bundle["raw_results"]),
        "limitations": [
            "Only metrics and fields already present in summary.json are reproduced.",
            "Metrics requiring missing retrieved IDs, references, or provider traces remain unavailable.",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    (output_dir / "raw_results.json").write_text(json.dumps(bundle["raw_results"], indent=2, default=str), encoding="utf-8")
    write_markdown_report(report, output_dir / "summary.md")
    return report


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Regenerate reports without providers, retrieval, or inference.")
    parser.add_argument("--input", required=True, help="Evaluation run directory or summary.json")
    parser.add_argument("--output", required=True, help="New output directory")
    args = parser.parse_args(argv)
    report = regenerate(Path(args.input), Path(args.output))
    print(f"Regenerated report: {args.output}")
    print(f"Provider: {report.get('provider', 'NOT RUN')} | model: {report.get('model', 'NOT RUN')}")
    print("Providers called: no")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())