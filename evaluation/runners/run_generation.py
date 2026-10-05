"""
Runner for Generation-only evaluation.
"""

from __future__ import annotations

import argparse
from evaluation.evaluators.generation_evaluator import GenerationEvaluator
from evaluation.schemas.dataset_schema import load_qa_dataset


def run_generation_suite(dataset_path: str, backend_caller=None) -> dict:
    dataset = load_qa_dataset(dataset_path)
    evaluator = GenerationEvaluator()
    generation_records = []
    if backend_caller:
        for item in dataset:
            resp = backend_caller(item.question)
            generation_records.append({
                "question_id": item.question_id,
                "question": item.question,
                "ground_truth": item.answer,
                "generated_answer": resp.get("answer", ""),
                "retrieved_contexts": [h.get("text", "") for h in resp.get("retrieved", [])],
                "answerable": item.answerable,
                "faithfulness_warning": resp.get("faithfulness_warning", False),
            })
    return evaluator.evaluate_generation(generation_records)


def main():
    parser = argparse.ArgumentParser(description="Run Generation Evaluation Suite")
    parser.add_argument("--dataset", default="evaluation/datasets/rag_test_dataset.json")
    args = parser.parse_args()
    res = run_generation_suite(args.dataset)
    print(res)


if __name__ == "__main__":
    main()
