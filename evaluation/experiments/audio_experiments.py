"""
Audio Evaluation Experiments runner.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional
from evaluation.evaluators.audio_evaluator import AudioEvaluator


def run_audio_experiments(benchmark_path: Optional[str | Path] = None) -> Dict[str, Any]:
    evaluator = AudioEvaluator(benchmark_path=benchmark_path)
    return evaluator.evaluate_audio()
