"""
Runner for Ablation experiments.
"""

from __future__ import annotations

import argparse
from evaluation.experiments.baseline_experiments import run_baseline_experiments
from evaluation.schemas.dataset_schema import load_qa_dataset


def main():
    parser = argparse.ArgumentParser(description="Run Ablation Evaluation Suite")
    parser.add_argument("--dataset", default="evaluation/datasets/rag_test_dataset.json")
    args = parser.parse_args()
    ds = load_qa_dataset(args.dataset)
    res = run_baseline_experiments(ds)
    print(res)


if __name__ == "__main__":
    main()
