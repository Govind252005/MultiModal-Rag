"""
Generation Evaluator module.
Scores answer correctness, answer relevance, semantic faithfulness,
token-F1, exact match, and abstention accuracy using reproducible judges.
"""

from __future__ import annotations

import statistics
from typing import Any, Dict, List, Sequence
from evaluation.judges.answer_judge import AnswerJudge
from evaluation.judges.faithfulness_judge import FaithfulnessJudge
from evaluation.metrics.faithfulness_metrics import diagnostic_warning_rate
from evaluation.metrics.generation_metrics import exact_match, token_overlap_f1


class GenerationEvaluator:
    """Evaluates generation quality and semantic faithfulness across questions."""

    def __init__(self):
        self.answer_judge = AnswerJudge()
        self.faithfulness_judge = FaithfulnessJudge()

    def evaluate_generation(
        self,
        generation_results: Sequence[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        generation_results: List of dicts with:
          - question_id
          - question
          - ground_truth
          - generated_answer
          - retrieved_contexts: List[str]
          - answerable: bool
          - faithfulness_warning: bool
        """
        if not generation_results:
            return {"status": "NOT_RUN", "reason": "No generation results to evaluate"}

        correctness_scores = []
        relevance_scores = []
        faithfulness_scores = []
        token_f1s = []
        exact_matches = []
        warning_flags = []

        unanswerable_total = 0
        correctly_abstained = 0
        answerable_total = 0
        false_abstentions = 0

        per_question = []

        for item in generation_results:
            q = item.get("question", "")
            gt = item.get("ground_truth", "")
            gen = item.get("generated_answer") or ""
            answerable = bool(item.get("answerable", True))
            contexts = item.get("retrieved_contexts") or []
            warning = bool(item.get("faithfulness_warning", False))
            warning_flags.append(warning)

            # Answer Judge
            ans_res = self.answer_judge.judge_answer(q, gt, gen, answerable=answerable)
            correctness_scores.append(ans_res["correctness_score"])
            relevance_scores.append(ans_res["relevance_score"])

            # Token overlap & Exact match for answerable questions
            if answerable:
                answerable_total += 1
                if ans_res["verdict"] == "ABSTAINED" or not gen.strip():
                    false_abstentions += 1
                f1_val = token_overlap_f1(gen, gt)["f1"]
                token_f1s.append(f1_val)
                exact_matches.append(exact_match(gen, gt))
            else:
                unanswerable_total += 1
                if ans_res["verdict"] == "CORRECT_ABSTENTION":
                    correctly_abstained += 1

            # Faithfulness Judge
            faith_res = self.faithfulness_judge.judge_faithfulness(gen, contexts)
            faithfulness_scores.append(faith_res["faithfulness_score"])

            per_question.append({
                "question_id": item.get("question_id"),
                "correctness_score": ans_res["correctness_score"],
                "relevance_score": ans_res["relevance_score"],
                "faithfulness_score": faith_res["faithfulness_score"],
                "verdict": ans_res["verdict"],
                "answer_rationale": ans_res["rationale"],
                "faithfulness_rationale": faith_res["rationale"],
            })

        abstention_acc = (
            correctly_abstained / unanswerable_total if unanswerable_total > 0 else 1.0
        )
        abstention_recall = (
            correctly_abstained / unanswerable_total if unanswerable_total else 1.0
        )
        abstention_precision_denominator = correctly_abstained + false_abstentions
        abstention_precision = (
            correctly_abstained / abstention_precision_denominator
            if abstention_precision_denominator else 1.0
        )
        total_questions = answerable_total + unanswerable_total
        overall_abstention_accuracy = (
            (correctly_abstained + (answerable_total - false_abstentions)) / total_questions
            if total_questions else 1.0
        )

        return {
            "answer_correctness_mean": round(statistics.mean(correctness_scores), 4) if correctness_scores else None,
            "answer_relevance_mean": round(statistics.mean(relevance_scores), 4) if relevance_scores else None,
            "faithfulness_mean": round(statistics.mean(faithfulness_scores), 4) if faithfulness_scores else None,
            "token_f1_mean": round(statistics.mean(token_f1s), 4) if token_f1s else None,
            "exact_match_rate": round(statistics.mean(exact_matches), 4) if exact_matches else None,
            "abstention_accuracy": round(abstention_acc, 4),
            "abstention_precision": round(abstention_precision, 4),
            "abstention_recall": round(abstention_recall, 4),
            "correct_rejection_rate": round(abstention_recall, 4),
            "false_abstention_rate": round(
                false_abstentions / answerable_total if answerable_total else 0.0, 4
            ),
            "overall_abstention_accuracy": round(overall_abstention_accuracy, 4),
            "answerable_evaluated": answerable_total,
            "unanswerable_evaluated": unanswerable_total,
            "faithfulness_warning_rate": round(diagnostic_warning_rate(warning_flags), 4),
            "evaluated_answers": len(generation_results),
            "per_question": per_question,
        }
