"""
Runner for Retrieval-only experiments.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from evaluation.evaluators.retrieval_evaluator import RetrievalEvaluator
from evaluation.schemas.dataset_schema import load_qa_dataset


def run_retrieval_suite(dataset_path: str, backend_caller=None) -> dict:
    dataset = load_qa_dataset(dataset_path)
    evaluator = RetrievalEvaluator()

    retrieved_items = []
    if backend_caller:
        for item in dataset:
            resp = backend_caller(item.question)
            retrieved_items.append({
                "question_id": item.question_id,
                "retrieved_ids": [h.get("id") for h in resp.get("retrieved", [])],
                "relevant_ids": item.relevant_chunk_ids,
            })

    return evaluator.evaluate_retrieval(retrieved_items)


def main():
    parser = argparse.ArgumentParser(description="Run Retrieval Evaluation Suite")
    parser.add_argument("--dataset", default="evaluation/datasets/rag_test_dataset.json")
    args = parser.parse_args()
    res = run_retrieval_suite(args.dataset)
    print(res)


if __name__ == "__main__":
    main()
