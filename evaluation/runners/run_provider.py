"""
Runner for Provider evaluation (Ollama, Groq, Both).
"""

from __future__ import annotations

import argparse
from evaluation.experiments.provider_experiments import run_provider_comparison
from evaluation.providers.groq_provider import GroqEvalProvider
from evaluation.providers.ollama_provider import OllamaEvalProvider


def main():
    parser = argparse.ArgumentParser(description="Run Provider Evaluation Suite")
    parser.add_argument("--provider", choices=["ollama", "groq", "both"], default="ollama")
    args = parser.parse_args()
    if args.provider == "ollama":
        p = OllamaEvalProvider()
        print(f"Ollama provider initialized: {p.model}, available={p.is_available()}")
    elif args.provider == "groq":
        p = GroqEvalProvider()
        print(f"Groq provider initialized: {p.model}, available={p.is_available()}")
    else:
        print("Comparative provider evaluation selected.")


if __name__ == "__main__":
    main()
