"""
Text report generator and terminal display formatter (Requirement 24).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional


def _fmt(val: Any) -> str:
    if val is None:
        return "NOT RUN"
    if isinstance(val, float):
        return f"{val:.4f}"
    return str(val)


def generate_text_summary(report_data: Dict[str, Any]) -> str:
    """Generates human-readable summary.txt string."""
    lines = []
    w = 60
    lines.append("=" * w)
    lines.append("RAG EVALUATION REPORT".center(w))
    lines.append("=" * w)
    lines.append(f"Provider       : {report_data.get('provider', 'N/A').upper()}")
    lines.append(f"Model          : {report_data.get('model', 'N/A')}")
    lines.append(f"Dataset        : {report_data.get('dataset_path', 'N/A')}")
    lines.append(f"Questions      : {report_data.get('num_questions', 'NOT RUN')}")
    lines.append(f"Errors         : {report_data.get('num_errors', 0)}")
    lines.append(f"Timestamp      : {report_data.get('timestamp', 'N/A')}")
    lines.append("")

    # Sections
    sections = [
        ("RETRIEVAL RESULTS", "retrieval"),
        ("GENERATION RESULTS", "generation"),
        ("CITATION RESULTS", "citations"),
        ("PERFORMANCE RESULTS", "performance"),
        ("RESOURCE UTILIZATION", "resources"),
        ("MODALITY BREAKDOWN", "modality"),
        ("OCR EVALUATION", "ocr"),
        ("AUDIO EVALUATION", "audio"),
        ("INGESTION BENCHMARK", "ingestion"),
        ("ABLATION EXPERIMENTS", "ablation"),
    ]

    for title, key in sections:
        data = report_data.get("metrics", {}).get(key) or report_data.get(key)
        lines.append("=" * w)
        lines.append(title)
        lines.append("-" * w)
        if not data or (isinstance(data, dict) and data.get("status") == "NOT_RUN"):
            reason = data.get("reason", "Dataset or prerequisite not available") if isinstance(data, dict) else "Not executed"
            lines.append(f"Status: NOT RUN ({reason})")
        elif isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, dict):
                    lines.append(f"  {k}:")
                    for sub_k, sub_v in v.items():
                        lines.append(f"    {sub_k + ':':<24} {_fmt(sub_v):>10}")
                else:
                    lines.append(f"  {k + ':':<28} {_fmt(v):>10}")
        elif isinstance(data, list):
            for item in data:
                lines.append(f"  - {item}")
        lines.append("")

    lines.append("=" * w)
    lines.append(f"Report Directory: {report_data.get('report_dir', 'N/A')}")
    lines.append("=" * w)

    return "\n".join(lines)


def write_text_report(report_data: Dict[str, Any], out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    content = generate_text_summary(report_data)
    out_path.write_text(content, encoding="utf-8")
    return out_path


def print_terminal_evaluation_results(report_data: Dict[str, Any]) -> None:
    """Prints terminal output following the exact formatting required in §24."""
    metrics = report_data.get("metrics") or {}
    if hasattr(metrics, "to_dict"):
        metrics = metrics.to_dict()

    w = 60

    print()
    print("=" * w)
    print("RETRIEVAL RESULTS")
    print("=" * w)
    print(f"{'Metric':<24}{'Value':>12}")
    print("-" * 36)
    retrieval = metrics.get("retrieval", {})
    if retrieval:
        for k in ["precision@1", "precision@3", "precision@5", "precision@10"]:
            print(f"{k.capitalize():<24}{_fmt(retrieval.get(k)):>12}")
        print()
        for k in ["recall@1", "recall@3", "recall@5", "recall@10"]:
            print(f"{k.capitalize():<24}{_fmt(retrieval.get(k)):>12}")
        print()
        for k in ["f1@1", "f1@3", "f1@5", "f1@10"]:
            if k in retrieval:
                print(f"{k.upper():<24}{_fmt(retrieval.get(k)):>12}")
        print()
        print(f"{'MRR':<24}{_fmt(retrieval.get('mrr')):>12}")
        print(f"{'MAP':<24}{_fmt(retrieval.get('map')):>12}")
        print(f"{'nDCG@5':<24}{_fmt(retrieval.get('ndcg@5')):>12}")
        print(f"{'nDCG@10':<24}{_fmt(retrieval.get('ndcg@10')):>12}")
        print(f"{'Hit@5':<24}{_fmt(retrieval.get('hit@5')):>12}")
        print(f"{'Hit@10':<24}{_fmt(retrieval.get('hit@10')):>12}")
        if retrieval.get("roc_auc") is not None:
            print(f"{'ROC-AUC (Relevance)':<24}{_fmt(retrieval.get('roc_auc')):>12}")
        if retrieval.get("pr_auc") is not None:
            print(f"{'PR-AUC (Relevance)':<24}{_fmt(retrieval.get('pr_auc')):>12}")
    else:
        print("Status: NOT RUN")

    print()
    print("=" * w)
    print("GENERATION RESULTS")
    print("=" * w)
    gen = metrics.get("generation", {})
    cit = metrics.get("citations", {})
    if gen:
        print(f"{'Answer Correctness':<28}{_fmt(gen.get('answer_correctness_mean')):>12}")
        print(f"{'Answer Relevance':<28}{_fmt(gen.get('answer_relevance_mean')):>12}")
        print(f"{'Faithfulness':<28}{_fmt(gen.get('faithfulness_mean')):>12}")
        print(f"{'Token F1':<28}{_fmt(gen.get('token_f1_mean')):>12}")
        print(f"{'Exact Match':<28}{_fmt(gen.get('exact_match_rate')):>12}")
        print(f"{'Abstention Accuracy':<28}{_fmt(gen.get('abstention_accuracy')):>12}")
        print(f"{'Faithfulness Warning (diag)':<28}{_fmt(gen.get('faithfulness_warning_rate')):>12}")
    else:
        print("Status: NOT RUN")

    print()
    print("=" * w)
    print("CITATIONS")
    print("=" * w)
    if cit:
        print(f"{'Citation Presence Rate':<32}{_fmt(cit.get('citation_presence_rate')):>12}")
        print(f"{'Source Citation Precision':<32}{_fmt(cit.get('source_level_precision_mean')):>12}")
        print(f"{'Claim Citation Accuracy':<32}{_fmt(cit.get('claim_level_accuracy_mean')):>12}")
        print(f"{'Citation Completeness':<32}{_fmt(cit.get('citation_completeness_mean')):>12}")
    else:
        print("Status: NOT RUN")

    print()
    print("=" * w)
    print("PERFORMANCE")
    print("=" * w)
    perf = metrics.get("performance", {})
    stages = perf.get("stages", {})
    if stages:
        print(f"{'Stage':<28}{'P50 (ms)':>12}{'P95 (ms)':>12}")
        print("-" * 52)
        stage_names = [
            ("query_preprocessing", "Query Preprocessing"),
            ("dense_retrieval", "Dense Retrieval"),
            ("bm25_retrieval", "BM25"),
            ("clip_retrieval", "CLIP"),
            ("rrf_fusion", "RRF"),
            ("deduplication", "Deduplication"),
            ("cross_encoder", "Cross Encoder"),
            ("llm_generation", "LLM Generation"),
            ("total_query_latency", "Total"),
        ]
        for key, label in stage_names:
            st = stages.get(key, {})
            p50 = st.get("P50")
            p95 = st.get("P95")
            print(f"{label:<28}{_fmt(p50):>12}{_fmt(p95):>12}")
    else:
        print(f"{'Query Latency P50 (ms)':<28}{_fmt(perf.get('query_latency_p50_ms')):>12}")
        print(f"{'Query Latency P95 (ms)':<28}{_fmt(perf.get('query_latency_p95_ms')):>12}")

    print()
    print("=" * w)
    print("RESOURCES")
    print("=" * w)
    res = metrics.get("resources", {})
    if res and res.get("status") != "NOT_RUN":
        print(f"{'CPU Mean (%)':<28}{_fmt(res.get('cpu_percent_mean')):>12}")
        print(f"{'RAM Mean (%)':<28}{_fmt(res.get('ram_percent_mean')):>12}")
        print(f"{'RAM Peak (GB)':<28}{_fmt(res.get('ram_used_gb_peak')):>12}")
        print(f"{'GPU Utilization Peak (%)':<28}{_fmt(res.get('gpu_utilization_peak')):>12}")
        print(f"{'VRAM Peak (MB)':<28}{_fmt(res.get('vram_used_mb_peak')):>12}")
        print(f"{'ChromaDB Footprint (MB)':<28}{_fmt(res.get('chromadb_size_mb')):>12}")
    else:
        print("Status: NOT RUN")

    print()
    print("=" * w)
    print("MODALITY & CROSS-MODAL")
    print("=" * w)
    mod = metrics.get("modality", {})
    if mod and mod.get("status") != "NOT_RUN":
        for m_name, m_stats in mod.get("modalities", {}).items():
            print(f"{m_name:<16} P@5={_fmt(m_stats.get('precision@5'))} R@5={_fmt(m_stats.get('recall@5'))} MRR={_fmt(m_stats.get('mrr'))} nDCG@5={_fmt(m_stats.get('ndcg@5'))}")
    else:
        print("Status: NOT RUN (pending modality benchmark expansion)")

    print()
    print("=" * w)
    print("OCR & AUDIO BENCHMARKS")
    print("=" * w)
    ocr = metrics.get("ocr", {})
    audio = metrics.get("audio", {})
    print(f"OCR Benchmark   : {ocr.get('status', 'NOT RUN')} ({ocr.get('reason', 'Dataset pending')})")
    print(f"Audio Benchmark : {audio.get('status', 'NOT RUN')} ({audio.get('reason', 'Dataset pending')})")

    print()
    print("=" * w)
    print("EVALUATION COMPLETE")
    print("=" * w)
    print(f"Provider       : {report_data.get('provider', 'N/A').upper()}")
    print(f"Model          : {report_data.get('model', 'N/A')}")
    print(f"Questions      : {report_data.get('num_questions', 0)}")
    print(f"Errors         : {report_data.get('num_errors', 0)}")
    print()
    print("Report:")
    print(f"{report_data.get('report_dir', 'N/A')}")
    print()
    print("Graphs:")
    print(f"{Path(report_data.get('report_dir', '')) / 'graphs'}")
    print()
    print("Paper tables:")
    print(f"{Path(report_data.get('report_dir', '')) / 'paper_tables'}")
    print("=" * w)
