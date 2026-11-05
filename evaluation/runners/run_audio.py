"""
Runner for Audio evaluation.
"""

from __future__ import annotations

import argparse
from evaluation.experiments.audio_experiments import run_audio_experiments


def main():
    parser = argparse.ArgumentParser(description="Run Audio Evaluation Suite")
    parser.add_argument("--benchmark", default="evaluation/datasets/audio/audio_eval_benchmark.json")
    args = parser.parse_args()
    res = run_audio_experiments(args.benchmark)
    print(res)


if __name__ == "__main__":
    main()
