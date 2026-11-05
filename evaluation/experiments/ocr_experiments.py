"""
OCR Evaluation Experiments runner.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional
from evaluation.evaluators.ocr_evaluator import OCREvaluator


def run_ocr_experiments(benchmark_path: Optional[str | Path] = None) -> Dict[str, Any]:
    evaluator = OCREvaluator(benchmark_path=benchmark_path)
    return evaluator.evaluate_ocr()
