"""
Master Evaluation CLI entrypoint (Requirement 1, 16, 17, 18, 30).
Supports:
    python evaluation/run_eval.py --provider ollama --all
    python evaluation/run_eval.py --provider groq --all
    python evaluation/run_eval.py --provider both --all

Also supports individual experiment groups:
    --experiment retrieval
    --experiment generation
    --experiment citation
    --experiment performance
    --experiment ocr
    --experiment audio
    --experiment modality
    --experiment ablation

And self-test mode:
    python evaluation/run_eval.py --self-test
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add project root and backend to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from evaluation.runners.run_all import MasterEvaluationRunner


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Research-Grade Multimodal RAG Evaluation System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--provider",
        choices=["ollama", "groq", "both"],
        default="ollama",
        help="LLM provider to evaluate (default: ollama)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all evaluation dimensions and experiments",
    )
    parser.add_argument(
        "--experiment",
        choices=[
            "retrieval",
            "generation",
            "citation",
            "performance",
            "ocr",
            "audio",
            "modality",
            "ablation",
        ],
        default=None,
        help="Run a specific experiment group",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run pipeline with synthetic data to verify metrics, reports, and graphs without live backend",
    )
    parser.add_argument(
        "--dataset",
        default="evaluation/datasets/rag_test_dataset.json",
        help="Path to evaluation dataset JSON",
    )
    parser.add_argument(
        "--session-id",
        default="real-eval-v1",
        help="Target session ID for live queries",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Backend base URL",
    )
    parser.add_argument(
        "--token",
        default=None,
        help="Authorization Bearer token for live backend",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Top-K cutoff for retrieval evaluation",
    )

    args = parser.parse_args()

    # If --token is not supplied and not in self-test mode, inform user if required
    # But allow self-test mode or prompt if live queries fail
    runner = MasterEvaluationRunner(
        provider_name=args.provider,
        dataset_path=args.dataset,
        session_id=args.session_id,
        base_url=args.base_url,
        token=args.token,
        top_k=args.top_k,
        self_test=args.self_test,
        experiment_filter=args.experiment,
    )

    runner.run()


if __name__ == "__main__":
    main()
