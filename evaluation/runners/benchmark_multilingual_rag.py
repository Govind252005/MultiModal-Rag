"""
Benchmark runner for Multilingual and Cross-Lingual RAG evaluation (Phase 4.1).
Computes Recall@K, Precision@K, MRR, NDCG@K, Latencies, and Answer Quality
across English, Hindi, Hinglish, Spanish, French, German, and Arabic scenarios.
"""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Set

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from backend import config
from backend.retrieval import embeddings, lexical_index, search, vector_store
from backend.generation import answer as answer_mod


def dcg_at_k(r: List[int], k: int) -> float:
    r = list(r)[:k]
    if not r:
        return 0.0
    return sum(rel / math.log2(idx + 2) for idx, rel in enumerate(r))


def ndcg_at_k(retrieved: List[str], relevant: Set[str], k: int) -> float:
    r = [1 if item in relevant else 0 for item in retrieved[:k]]
    actual_dcg = dcg_at_k(r, k)
    ideal_r = [1] * min(len(relevant), k)
    ideal_dcg = dcg_at_k(ideal_r, k)
    if ideal_dcg == 0:
        return 0.0
    return actual_dcg / ideal_dcg


def run_multilingual_benchmark(dataset_path: Path, output_report_path: Path) -> Dict[str, Any]:
    dataset: List[Dict[str, Any]] = json.loads(dataset_path.read_text(encoding="utf-8"))
    session_id = "eval_multilingual_benchmark"
    user_id = "eval_user"
    org_id = "eval_org"

    print("=== [1/3] Indexing Multilingual Evaluation Corpus into Vector & Lexical Stores ===")
    # Clean up previous benchmark runs in this session
    vector_store.delete_session(session_id)
    lexical_index.delete_by_session(session_id)

    chunk_to_id: Dict[str, str] = {}
    for idx, item in enumerate(dataset):
        chunk_id = item["relevant_chunk_ids"][0]
        text = item["document_text"]
        filename = item["source_file"]
        page = item["page"]

        vec = embeddings.embed_text([text])[0].tolist()
        meta = {
            "file": filename,
            "session_id": session_id,
            "user_id": user_id,
            "org_id": org_id,
            "modality": "document",
            "page": page,
            "chunk_id": chunk_id,
            "lang": item["doc_lang"],
        }

        vector_store.add_text_chunks(
            ids=[chunk_id],
            embeddings=[vec],
            documents=[text],
            metadatas=[meta],
        )

    print(f"Indexed {len(dataset)} multilingual evaluation chunks.")

    # Warm up reranker and embedding models so initial load does not skew query latency
    try:
        search._get_reranker()
        embeddings.warmup()
    except Exception as exc:
        print(f"Warmup notice: {exc}")

    print("\n=== [2/3] Executing Queries and Measuring Retrieval & Generation Quality ===")
    results_by_scenario: Dict[str, List[Dict[str, Any]]] = {}
    query_eval_results: List[Dict[str, Any]] = []

    retrieval_latencies: List[float] = []

    for item in dataset:
        qid = item["id"]
        scenario = item["scenario"]
        query = item["query"]
        relevant_ids = set(item["relevant_chunk_ids"])

        t0 = time.perf_counter()
        hits = search.text_query(
            query=query,
            top_k=10,
            modality="document",
            session_id=session_id,
            user_id=user_id,
            org_id=org_id,
        )
        t_ret = (time.perf_counter() - t0) * 1000
        retrieval_latencies.append(t_ret)

        retrieved_ids = [h.get("id") or h.get("chunk_id") for h in hits]

        # Calculate Ranking Metrics
        hit_at_1 = 1 if any(h in relevant_ids for h in retrieved_ids[:1]) else 0
        hit_at_5 = 1 if any(h in relevant_ids for h in retrieved_ids[:5]) else 0
        hit_at_10 = 1 if any(h in relevant_ids for h in retrieved_ids[:10]) else 0

        # Precision@1, Precision@5
        p_at_1 = sum(1 for h in retrieved_ids[:1] if h in relevant_ids) / 1.0
        p_at_5 = sum(1 for h in retrieved_ids[:5] if h in relevant_ids) / 5.0

        # Recall@1, Recall@5, Recall@10
        total_rel = max(1, len(relevant_ids))
        r_at_1 = sum(1 for h in retrieved_ids[:1] if h in relevant_ids) / total_rel
        r_at_5 = sum(1 for h in retrieved_ids[:5] if h in relevant_ids) / total_rel
        r_at_10 = sum(1 for h in retrieved_ids[:10] if h in relevant_ids) / total_rel

        # MRR
        mrr = 0.0
        for rank, hid in enumerate(retrieved_ids, start=1):
            if hid in relevant_ids:
                mrr = 1.0 / rank
                break

        # NDCG@5, NDCG@10
        ndcg_5 = ndcg_at_k(retrieved_ids, relevant_ids, 5)
        ndcg_10 = ndcg_at_k(retrieved_ids, relevant_ids, 10)

        # Context relevance
        context_relevance = r_at_5

        # Answer generation check
        gen_result = answer_mod.answer_query(
            query=query,
            hits=hits,
            user_id=user_id,
            provider="ollama",
        )
        answer_text = gen_result.get("answer", "")
        citations = gen_result.get("citations", [])
        
        # Citation precision
        cited_correct = any(c.get("file") == item["source_file"] for c in citations)
        cit_precision = 1.0 if cited_correct else (0.0 if citations else 0.5)

        q_res = {
            "id": qid,
            "scenario": scenario,
            "query": query,
            "doc_lang": item["doc_lang"],
            "query_lang": item["query_lang"],
            "hit_at_1": hit_at_1,
            "hit_at_5": hit_at_5,
            "hit_at_10": hit_at_10,
            "p_at_1": p_at_1,
            "p_at_5": p_at_5,
            "r_at_1": r_at_1,
            "r_at_5": r_at_5,
            "r_at_10": r_at_10,
            "mrr": mrr,
            "ndcg_5": ndcg_5,
            "ndcg_10": ndcg_10,
            "context_relevance": context_relevance,
            "citation_precision": cit_precision,
            "retrieval_ms": round(t_ret, 2),
            "retrieved_files": [h.get("file") for h in hits[:3]],
            "expected_file": item["source_file"],
            "answer_preview": answer_text[:120],
        }

        query_eval_results.append(q_res)
        results_by_scenario.setdefault(scenario, []).append(q_res)
        print(f"[{scenario:<28}] Query: '{query[:40]}...' -> Hit@5: {hit_at_5}, MRR: {mrr:.2f}, Latency: {t_ret:.1f}ms")

    print("\n=== [3/3] Aggregating Scenario & Global Metrics ===")
    scenario_aggregates: Dict[str, Dict[str, float]] = {}
    for scn, items in results_by_scenario.items():
        n = len(items)
        scenario_aggregates[scn] = {
            "count": n,
            "hit_at_1": round(sum(i["hit_at_1"] for i in items) / n, 4),
            "hit_at_5": round(sum(i["hit_at_5"] for i in items) / n, 4),
            "hit_at_10": round(sum(i["hit_at_10"] for i in items) / n, 4),
            "r_at_1": round(sum(i["r_at_1"] for i in items) / n, 4),
            "r_at_5": round(sum(i["r_at_5"] for i in items) / n, 4),
            "r_at_10": round(sum(i["r_at_10"] for i in items) / n, 4),
            "p_at_1": round(sum(i["p_at_1"] for i in items) / n, 4),
            "p_at_5": round(sum(i["p_at_5"] for i in items) / n, 4),
            "mrr": round(sum(i["mrr"] for i in items) / n, 4),
            "ndcg_5": round(sum(i["ndcg_5"] for i in items) / n, 4),
            "ndcg_10": round(sum(i["ndcg_10"] for i in items) / n, 4),
            "context_relevance": round(sum(i["context_relevance"] for i in items) / n, 4),
            "citation_precision": round(sum(i["citation_precision"] for i in items) / n, 4),
            "avg_latency_ms": round(sum(i["retrieval_ms"] for i in items) / n, 2),
        }

    total_n = len(query_eval_results)
    overall = {
        "total_queries": total_n,
        "hit_at_1": round(sum(i["hit_at_1"] for i in query_eval_results) / total_n, 4),
        "hit_at_5": round(sum(i["hit_at_5"] for i in query_eval_results) / total_n, 4),
        "hit_at_10": round(sum(i["hit_at_10"] for i in query_eval_results) / total_n, 4),
        "r_at_1": round(sum(i["r_at_1"] for i in query_eval_results) / total_n, 4),
        "r_at_5": round(sum(i["r_at_5"] for i in query_eval_results) / total_n, 4),
        "r_at_10": round(sum(i["r_at_10"] for i in query_eval_results) / total_n, 4),
        "p_at_1": round(sum(i["p_at_1"] for i in query_eval_results) / total_n, 4),
        "p_at_5": round(sum(i["p_at_5"] for i in query_eval_results) / total_n, 4),
        "mrr": round(sum(i["mrr"] for i in query_eval_results) / total_n, 4),
        "ndcg_5": round(sum(i["ndcg_5"] for i in query_eval_results) / total_n, 4),
        "ndcg_10": round(sum(i["ndcg_10"] for i in query_eval_results) / total_n, 4),
        "context_relevance": round(sum(i["context_relevance"] for i in query_eval_results) / total_n, 4),
        "citation_precision": round(sum(i["citation_precision"] for i in query_eval_results) / total_n, 4),
        "avg_latency_ms": round(sum(retrieval_latencies) / total_n, 2),
    }

    full_report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "models": {
            "embedding": config.TEXT_EMBED_MODEL,
            "reranker": config.RERANK_MODEL,
            "rerank_enabled": config.RERANK_ENABLED,
            "generator": config.LLM_MODEL,
        },
        "overall": overall,
        "scenarios": scenario_aggregates,
        "queries": query_eval_results,
    }

    output_report_path.parent.mkdir(parents=True, exist_ok=True)
    output_report_path.write_text(json.dumps(full_report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nMultilingual benchmark report written to: {output_report_path}")
    return full_report


if __name__ == "__main__":
    dpath = ROOT / "evaluation" / "datasets" / "multilingual_rag_dataset.json"
    rep_name = sys.argv[1] if len(sys.argv) > 1 else "multilingual_improved_report.json"
    rpath = ROOT / "reports" / rep_name
    rep = run_multilingual_benchmark(dpath, rpath)
    print("\n--- OVERALL BENCHMARK SUMMARY ---")
    for k, v in rep["overall"].items():
        print(f"  {k:<20}: {v}")
