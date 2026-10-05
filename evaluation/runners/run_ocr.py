"""
Runner for OCR evaluation.
"""

from __future__ import annotations

import argparse
from evaluation.experiments.ocr_experiments import run_ocr_experiments


def main():
    parser = argparse.ArgumentParser(description="Run OCR Evaluation Suite")
    parser.add_argument("--benchmark", default="evaluation/datasets/ocr/ocr_eval_benchmark.json")
    args = parser.parse_args()
    res = run_ocr_experiments(args.benchmark)
    print(res)


if __name__ == "__main__":
    main()
