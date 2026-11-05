"""
OCR Evaluator module (Requirement 6).
Evaluates CER, WER, and downstream retrieval Recall@5 comparing PaddleOCR vs Tesseract.
If verified ground truth benchmark dataset is missing, marks NOT RUN without fabricating.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from evaluation.metrics.ocr_metrics import calculate_ocr_metrics_suite
from evaluation.schemas.dataset_schema import OCRBenchmarkItem

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BENCHMARK_PATH = REPO_ROOT / "evaluation" / "datasets" / "ocr" / "ocr_eval_benchmark.json"


def _resolve_path(path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else REPO_ROOT / candidate


class OCREvaluator:
    """Evaluates OCR engines against human-verified transcriptions."""

    def __init__(self, benchmark_path: Optional[str | Path] = None):
        self.benchmark_path = _resolve_path(benchmark_path or DEFAULT_BENCHMARK_PATH)

    def evaluate_ocr(self) -> Dict[str, Any]:
        """
        Executes OCR benchmark comparison if dataset is available.
        Otherwise reports NOT_RUN with clear rationale.
        """
        if not self.benchmark_path.is_file():
            return {
                "status": "NOT_RUN",
                "reason": (
                    f"OCR benchmark dataset not found at '{self.benchmark_path}'. "
                    f"Manually verified image transcription ground truth is required. Data will not be fabricated."
                ),
                "paddleocr": None,
                "tesseract": None,
                "downstream_retrieval_impact": None,
            }

        # If file exists, load and evaluate
        with self.benchmark_path.open("r", encoding="utf-8") as f:
            raw = json.load(f)

        if not raw:
            return {
                "status": "NOT_RUN",
                "reason": "OCR benchmark dataset is empty. Human-verified transcriptions required.",
            }

        items = [OCRBenchmarkItem.from_dict(d) for d in raw]
        from PIL import Image
        from backend.ingestion import image_pipeline

        paddle_pairs = []
        tesseract_pairs = []
        failures = []
        paddle_unavailable = False
        for item in items:
            image_path = _resolve_path(item.image_path)
            if not image_path.is_file():
                failures.append({"sample_id": item.sample_id, "reason": f"Image not found: {image_path}"})
                continue
            try:
                image = Image.open(image_path).convert("RGB")
                if not paddle_unavailable:
                    try:
                        paddle_pairs.append((item.ground_truth_transcription, image_pipeline._ocr_paddleocr(image)))
                    except Exception as exc:
                        paddle_unavailable = True
                        failures.append({"sample_id": item.sample_id, "engine": "paddleocr", "reason": str(exc)})
                try:
                    tesseract_pairs.append((item.ground_truth_transcription, image_pipeline._ocr_tesseract(image)))
                except Exception as exc:
                    failures.append({"sample_id": item.sample_id, "engine": "tesseract", "reason": str(exc)})
            except Exception as exc:
                failures.append({"sample_id": item.sample_id, "reason": f"Image load failed: {exc}"})

        verified = all(item.verified_by_human for item in items)
        return {
            "status": "COMPLETED" if (paddle_pairs or tesseract_pairs) else "NOT_RUN",
            "samples_evaluated": max(len(paddle_pairs), len(tesseract_pairs)),
            "benchmark_dataset": str(self.benchmark_path),
            "ground_truth_verified": verified,
            "verification_warning": None if verified else "Dataset records are marked verified_by_human=false; metrics are computed but should not be treated as publication-grade ground truth.",
            "paddleocr": calculate_ocr_metrics_suite(paddle_pairs) if paddle_pairs else None,
            "tesseract": calculate_ocr_metrics_suite(tesseract_pairs) if tesseract_pairs else None,
            "failures": failures,
            "downstream_retrieval_impact": None,
        }
