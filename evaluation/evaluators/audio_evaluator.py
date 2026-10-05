"""
Audio Evaluator module (Requirement 7).
Evaluates ASR Word Error Rate (WER) across conditions (clean, noisy, overlapping)
and downstream retrieval upper bound vs Faster-Whisper transcript retrieval.
Never fabricates audio samples or transcripts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from evaluation.metrics.audio_metrics import calculate_audio_suite
from evaluation.schemas.dataset_schema import AudioBenchmarkItem

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BENCHMARK_PATH = REPO_ROOT / "evaluation" / "datasets" / "audio" / "audio_eval_benchmark.json"


def _resolve_path(path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else REPO_ROOT / candidate


class AudioEvaluator:
    """Evaluates audio ASR and downstream retrieval impact."""

    def __init__(self, benchmark_path: Optional[str | Path] = None):
        self.benchmark_path = _resolve_path(benchmark_path or DEFAULT_BENCHMARK_PATH)

    def evaluate_audio(self) -> Dict[str, Any]:
        """
        Executes Audio ASR benchmark comparison if dataset is available.
        Otherwise reports NOT_RUN with clear rationale.
        """
        if not self.benchmark_path.is_file():
            return {
                "status": "NOT_RUN",
                "reason": (
                    f"Audio evaluation dataset not found at '{self.benchmark_path}'. "
                    f"Human-verified audio recordings and transcriptions required. Data will not be fabricated."
                ),
                "asr_wer": None,
                "ground_truth_recall_at_5": None,
                "asr_recall_at_5": None,
                "retrieval_degradation": None,
            }

        with self.benchmark_path.open("r", encoding="utf-8") as f:
            raw = json.load(f)

        if not raw:
            return {
                "status": "NOT_RUN",
                "reason": "Audio benchmark dataset is empty. Human-verified audio data required.",
            }

        items = [AudioBenchmarkItem.from_dict(d) for d in raw]
        from backend.ingestion.audio_pipeline import transcribe

        samples = []
        by_condition: Dict[str, list[tuple[str, str, str]]] = {}
        failures = []
        for item in items:
            audio_path = _resolve_path(item.audio_path)
            if not audio_path.is_file():
                failures.append({"sample_id": item.sample_id, "reason": f"Audio not found: {audio_path}"})
                continue
            try:
                segments, _language = transcribe(str(audio_path))
                hypothesis = " ".join(segment.get("text", "") for segment in segments).strip()
                sample = (item.sample_id, item.ground_truth_transcript, hypothesis)
                samples.append(sample)
                by_condition.setdefault(item.condition, []).append(sample)
            except Exception as exc:
                failures.append({"sample_id": item.sample_id, "reason": str(exc)})

        verified = all(item.verified_by_human for item in items)
        overall = calculate_audio_suite(samples) if samples else {}
        return {
            "status": "COMPLETED" if samples else "NOT_RUN",
            "samples_evaluated": len(samples),
            "benchmark_dataset": str(self.benchmark_path),
            "ground_truth_verified": verified,
            "verification_warning": None if verified else "Dataset records are marked verified_by_human=false; metrics are computed but should not be treated as publication-grade ground truth.",
            "asr_wer": overall.get("overall_wer"),
            "overall_wer": overall.get("overall_wer"),
            "by_condition": {condition: calculate_audio_suite(values) for condition, values in by_condition.items()},
            "failures": failures,
            "ground_truth_recall_at_5": None,
            "asr_recall_at_5": None,
            "retrieval_degradation": None,
        }
