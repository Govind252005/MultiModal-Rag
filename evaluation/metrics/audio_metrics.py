"""
Audio ASR evaluation metrics: Word Error Rate (WER) and downstream retrieval impact.
"""

from __future__ import annotations

from typing import Dict, List, Sequence
from evaluation.metrics.ocr_metrics import levenshtein_distance


def audio_word_error_rate(reference: str, hypothesis: str) -> float:
    """
    WER = edit_distance(reference_words, hypothesis_words) / len(reference_words).
    Case-insensitive, normalized punctuation.
    """
    import re
    def norm(s: str) -> List[str]:
        s = s.lower()
        s = re.sub(r"[^\w\s]", "", s)
        return s.split()

    ref_words = norm(reference)
    hyp_words = norm(hypothesis)
    if not ref_words:
        return 0.0 if not hyp_words else 1.0

    dist = levenshtein_distance(ref_words, hyp_words)
    return dist / len(ref_words)


def calculate_audio_suite(
    samples: Sequence[tuple[str, str, str]]
) -> Dict[str, Any]:
    """
    Takes a sequence of (sample_id, ground_truth, asr_hypothesis).
    Computes per-condition and overall WER.
    """
    if not samples:
        return {"overall_wer": 0.0, "samples": 0}

    total_wer = 0.0
    for _, gt, hyp in samples:
        total_wer += audio_word_error_rate(gt, hyp)

    return {
        "overall_wer": round(total_wer / len(samples), 4),
        "samples": len(samples),
    }
