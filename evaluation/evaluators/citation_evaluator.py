"""
Citation Evaluator module.
Evaluates the 4 distinct citation dimensions (Requirement 11):
1. Citation presence
2. Source-level citation precision
3. Claim-level citation accuracy
4. Citation completeness / claim coverage
"""

from __future__ import annotations

import statistics
from typing import Any, Dict, List, Sequence
from evaluation.judges.citation_judge import CitationJudge


class CitationEvaluator:
    """Evaluates citations strictly separating source precision from claim accuracy."""

    def __init__(self):
        self.citation_judge = CitationJudge()

    def evaluate_citations(
        self,
        citation_results: Sequence[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        citation_results: List of dicts with:
          - question_id
          - generated_answer
          - cited_files: List[str]
          - required_citations: List[str]
          - retrieved_items: List[Dict[str, Any]]
          - answerable: bool
        """
        if not citation_results:
            return {"status": "NOT_RUN", "reason": "No citation results to evaluate"}

        presence_flags = []
        source_precisions = []
        claim_accuracies = []
        completeness_scores = []
        per_question = []

        for item in citation_results:
            qid = item.get("question_id")
            gen = item.get("generated_answer") or ""
            cited = item.get("cited_files") or []
            req = item.get("required_citations") or []
            ret = item.get("retrieved_items") or []
            ans = bool(item.get("answerable", True))

            c_res = self.citation_judge.judge_citations(
                generated_answer=gen,
                cited_files=cited,
                required_citations=req,
                retrieved_items=ret,
                requires_evidence=ans,
                available_citations=item.get("available_citations") or [],
            )

            presence_flags.append(c_res["citation_present"])
            if req:
                source_precisions.append(c_res["source_level_precision"])
            claim_accuracies.append(c_res["claim_level_accuracy"])
            completeness_scores.append(c_res["citation_completeness"])

            per_question.append({
                "question_id": qid,
                **c_res,
            })

        presence_rate = sum(1 for p in presence_flags if p) / len(presence_flags) if presence_flags else 0.0

        return {
            "citation_presence_rate": round(presence_rate, 4),
            "source_level_precision_mean": round(statistics.mean(source_precisions), 4) if source_precisions else None,
            "claim_level_accuracy_mean": round(statistics.mean(claim_accuracies), 4) if claim_accuracies else None,
            "citation_completeness_mean": round(statistics.mean(completeness_scores), 4) if completeness_scores else None,
            "evaluated_questions": len(citation_results),
            "per_question": per_question,
        }
