"""
Provider Comparison Experiment (Requirement 18).
Runs Ollama vs Groq comparison on identical retrieval context.
Generates comparative metrics and summary report.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from evaluation.evaluators.provider_evaluator import ProviderEvaluator
from evaluation.providers.groq_provider import GroqEvalProvider
from evaluation.providers.ollama_provider import OllamaEvalProvider
from evaluation.reporting.csv_report import write_csv_rows
from evaluation.reporting.graph_generator import plot_provider_comparison


def run_provider_comparison(
    questions_with_retrieval: List[Dict[str, Any]],
    out_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Runs provider-independent retrieval once, then evaluates:
    1. Ollama generation
    2. Groq generation
    Produces side-by-side comparison metrics.
    """
    ollama_prov = OllamaEvalProvider()
    groq_prov = GroqEvalProvider()

    ollama_evaluator = ProviderEvaluator(ollama_prov)
    groq_evaluator = ProviderEvaluator(groq_prov)

    # 1. Ollama
    ollama_res = ollama_evaluator.evaluate_provider_generation(questions_with_retrieval)

    # 2. Groq
    groq_res = groq_evaluator.evaluate_provider_generation(questions_with_retrieval)

    comparison_data = {
        "status": "COMPLETED",
        "ollama": ollama_res,
        "groq": groq_res,
        "comparison_table": [],
    }

    # Build comparison rows
    o_gen = ollama_res.get("generation", {})
    g_gen = groq_res.get("generation", {})
    o_cit = ollama_res.get("citations", {})
    g_cit = groq_res.get("citations", {})
    o_usage = ollama_res.get("usage", {})
    g_usage = groq_res.get("usage", {})

    metrics_rows = [
        {"metric": "Answer Correctness (Mean)", "ollama": o_gen.get("answer_correctness_mean"), "groq": g_gen.get("answer_correctness_mean")},
        {"metric": "Answer Relevance (Mean)", "ollama": o_gen.get("answer_relevance_mean"), "groq": g_gen.get("answer_relevance_mean")},
        {"metric": "Semantic Faithfulness (Mean)", "ollama": o_gen.get("faithfulness_mean"), "groq": g_gen.get("faithfulness_mean")},
        {"metric": "Token F1 (Mean)", "ollama": o_gen.get("token_f1_mean"), "groq": g_gen.get("token_f1_mean")},
        {"metric": "Citation Presence Rate", "ollama": o_cit.get("citation_presence_rate"), "groq": g_cit.get("citation_presence_rate")},
        {"metric": "Claim Citation Accuracy", "ollama": o_cit.get("claim_level_accuracy_mean"), "groq": g_cit.get("claim_level_accuracy_mean")},
        {"metric": "Source Citation Precision", "ollama": o_cit.get("source_level_precision_mean"), "groq": g_cit.get("source_level_precision_mean")},
        {"metric": "Total Tokens Used", "ollama": o_usage.get("total_tokens"), "groq": g_usage.get("total_tokens")},
    ]

    comparison_data["comparison_table"] = metrics_rows

    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        # Write comparison CSV
        write_csv_rows(metrics_rows, out_dir / "provider_comparison.csv")
        # Write comparison JSON
        (out_dir / "provider_comparison.json").write_text(json.dumps(comparison_data, indent=2, default=str), encoding="utf-8")
        # Plot comparison graph
        plot_provider_comparison(ollama_res, groq_res, out_dir / "provider_comparison.png")

    return comparison_data
