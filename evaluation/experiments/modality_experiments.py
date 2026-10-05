"""
Modality and Cross-Modal Experiments runner.
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence
from evaluation.evaluators.modality_evaluator import ModalityEvaluator


def run_modality_experiments(
    question_results: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    evaluator = ModalityEvaluator()
    return evaluator.evaluate_modalities(question_results)
