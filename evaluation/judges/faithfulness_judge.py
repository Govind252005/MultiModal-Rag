"""
Semantic faithfulness judge.
Splits generated answer into constituent claims/sentences and verifies
empirical grounding against retrieved context snippets.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Sequence
from evaluation.metrics.generation_metrics import token_overlap_f1


def split_into_claims(text: str) -> List[str]:
    """Splits text into candidate factual sentences/claims."""
    cleaned = text.strip()
    if not cleaned:
        return []
    # Split on sentence terminals: ., !, ? followed by space or newline
    raw_sentences = re.split(r"(?<=[.!?])\s+", cleaned)
    claims = [s.strip() for s in raw_sentences if len(s.strip()) > 10]
    return claims if claims else [cleaned]


class FaithfulnessJudge:
    """Evaluates whether the claims in generated answers are grounded in retrieved evidence."""

    def __init__(self, claim_overlap_threshold: float = 0.40):
        self.claim_overlap_threshold = claim_overlap_threshold

    def judge_faithfulness(
        self,
        generated_answer: str,
        retrieved_contexts: Sequence[str],
    ) -> Dict[str, Any]:
        """
        Assesses grounding of generated answer in retrieved chunks.
        """
        if not generated_answer.strip():
            return {
                "faithfulness_score": 1.0,
                "total_claims": 0,
                "supported_claims": 0,
                "unsupported_claims": [],
                "rationale": "Empty answer has no ungrounded claims.",
            }

        claims = split_into_claims(generated_answer)
        if not claims:
            return {
                "faithfulness_score": 1.0,
                "total_claims": 0,
                "supported_claims": 0,
                "unsupported_claims": [],
                "rationale": "No substantive claims identified.",
            }

        if not retrieved_contexts:
            # If evidence is completely empty, any factual claim is ungrounded
            return {
                "faithfulness_score": 0.0,
                "total_claims": len(claims),
                "supported_claims": 0,
                "unsupported_claims": claims,
                "rationale": "No retrieved context was provided to support claims.",
            }

        combined_evidence = " ".join(retrieved_contexts).lower()
        supported = 0
        unsupported = []

        for claim in claims:
            # Check lexical/token grounding
            overlap = token_overlap_f1(claim, combined_evidence)
            # A claim is grounded if its content words have strong overlap with evidence
            if overlap["precision"] >= self.claim_overlap_threshold:
                supported += 1
            else:
                unsupported.append(claim)

        score = round(supported / len(claims), 4)

        return {
            "faithfulness_score": score,
            "total_claims": len(claims),
            "supported_claims": supported,
            "unsupported_claims": unsupported,
            "rationale": f"{supported}/{len(claims)} claims grounded in retrieved evidence (threshold={self.claim_overlap_threshold}).",
        }
