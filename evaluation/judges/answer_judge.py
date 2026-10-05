"""
Answer correctness and relevance judge.
Provides deterministic, reproducible judging without fabricated scores.
Computes token-F1, semantic overlap, and optional embedding similarity.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from evaluation.metrics.generation_metrics import (
    exact_match,
    is_abstention,
    normalize_answer,
    rouge_l_score,
    token_overlap_f1,
)


class AnswerJudge:
    """
    Evaluates:
    1. Answer Correctness: Degree to which generated answer matches ground truth.
    2. Answer Relevance: Degree to which generated answer addresses the question.
    """

    def __init__(self, semantic_threshold: float = 0.65):
        self.semantic_threshold = semantic_threshold
        self._embedder = None
        self._attempted_embedder_load = False

    def _get_embedder(self):
        if not self._attempted_embedder_load:
            self._attempted_embedder_load = True
            try:
                from sentence_transformers import SentenceTransformer
                import config
                model_name = getattr(config, "TEXT_EMBED_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
                # Evaluation must not unexpectedly block on a model download.
                # If the model is already cached, use it; otherwise the
                # deterministic token/ROUGE fallback below remains valid.
                self._embedder = SentenceTransformer(model_name, local_files_only=True)
            except Exception:
                self._embedder = None
        return self._embedder

    def _compute_cosine_sim(self, text1: str, text2: str) -> Optional[float]:
        embedder = self._get_embedder()
        if embedder is None:
            return None
        try:
            import numpy as np
            vecs = embedder.encode([text1, text2])
            norm1 = np.linalg.norm(vecs[0])
            norm2 = np.linalg.norm(vecs[1])
            if norm1 == 0 or norm2 == 0:
                return 0.0
            return float(np.dot(vecs[0], vecs[1]) / (norm1 * norm2))
        except Exception:
            return None

    def judge_answer(
        self,
        question: str,
        ground_truth: str,
        generated: str,
        answerable: bool = True
    ) -> Dict[str, Any]:
        """
        Judges correctness and relevance deterministically.
        Returns a dict with:
        - correctness_score (0.0 to 1.0)
        - relevance_score (0.0 to 1.0)
        - verdict ('CORRECT', 'PARTIALLY_CORRECT', 'INCORRECT', 'ABSTAINED')
        - rationale
        """
        gen_clean = generated.strip()
        ref_clean = ground_truth.strip()

        # Handle unanswerable questions
        if not answerable:
            abstained = is_abstention(gen_clean)
            if abstained:
                return {
                    "correctness_score": 1.0,
                    "relevance_score": 1.0,
                    "verdict": "CORRECT_ABSTENTION",
                    "rationale": "Correctly abstained on an unanswerable question.",
                }
            else:
                return {
                    "correctness_score": 0.0,
                    "relevance_score": 0.5,
                    "verdict": "FAILED_ABSTENTION",
                    "rationale": "Failed to abstain on an unanswerable question; hallucinated an answer.",
                }

        # Handle empty generation
        if not gen_clean:
            return {
                "correctness_score": 0.0,
                "relevance_score": 0.0,
                "verdict": "INCORRECT",
                "rationale": "Generated answer is empty.",
            }

        # Exact match check
        em = exact_match(gen_clean, ref_clean)
        if em == 1.0:
            return {
                "correctness_score": 1.0,
                "relevance_score": 1.0,
                "verdict": "CORRECT",
                "rationale": "Exact match with ground truth.",
            }

        # Token overlap and ROUGE-L
        tok_f1 = token_overlap_f1(gen_clean, ref_clean)["f1"]
        rouge = rouge_l_score(gen_clean, ref_clean)["f1"]

        # Relevance to question (token overlap)
        q_rel = token_overlap_f1(gen_clean, question)["f1"]
        relevance_score = round(min(1.0, max(q_rel, tok_f1 * 0.8 + 0.2)), 4)

        # Semantic cosine similarity if embedder available
        cos_sim = self._compute_cosine_sim(gen_clean, ref_clean)
        if cos_sim is not None:
            # Hybrid combination of semantic cosine similarity and token overlap
            composite = 0.7 * max(0.0, cos_sim) + 0.3 * tok_f1
        else:
            composite = 0.5 * tok_f1 + 0.5 * rouge

        composite = round(min(1.0, max(0.0, composite)), 4)

        if composite >= 0.75:
            verdict = "CORRECT"
        elif composite >= 0.40:
            verdict = "PARTIALLY_CORRECT"
        else:
            verdict = "INCORRECT"

        rationale = f"Token-F1={tok_f1:.3f}, ROUGE-L={rouge:.3f}"
        if cos_sim is not None:
            rationale += f", Embedding-Sim={cos_sim:.3f}"

        return {
            "correctness_score": composite,
            "relevance_score": relevance_score,
            "verdict": verdict,
            "rationale": rationale,
        }
