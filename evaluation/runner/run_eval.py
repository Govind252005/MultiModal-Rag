"""
Evaluation runner (brief §148): python -m evaluation.runner.run_eval

Loads a ground-truth dataset, calls the LIVE backend's /api/query for each
question, computes retrieval/citation/performance metrics from the real
responses, writes JSON/CSV/MD reports + graphs, and prints the brief's
§81 terminal summary.

THIS MODULE MAKES REAL HTTP CALLS TO YOUR RUNNING BACKEND. It does not
fabricate any number: if the backend is unreachable, or a question's
result can't be scored (e.g. no ground truth for that field), the
relevant metric is recorded as None ("NOT RUN") rather than guessed.

Usage:
    # 1. Have the backend running (uvicorn backend.main:app) with your
    #    documents already ingested into a session.
    # 2. Fill in evaluation/datasets/example_dataset.json (or copy it)
    #    with real questions and ground truth about YOUR documents.
    # 3. python -m evaluation.runner.run_eval \\
    #        --base-url http://localhost:8000 \\
    #        --token <your bearer token> \\
    #        --session-id <session to query> \\
    #        --dataset evaluation/datasets/example_dataset.json

Self-test mode (--self-test) runs the SAME metric/report/graph pipeline
against synthetic, clearly-labeled fake retrieval results instead of a
live backend, purely to prove the plumbing works. Its output is written
under reports/evaluation/selftest_<id>/ and is never presented as a real
evaluation of the app.
"""


from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from evaluation.datasets.schema import load_dataset
from evaluation.metrics import citation_metrics as cm
from evaluation.metrics import retrieval_metrics as rm
from evaluation.reports import writer
from evaluation.visualization import plots

try:
    from backend.observability import resources as resource_snapshot # backend module
except Exception:
    resource_snapshot = None  # psutil not installed — degrade honestly, see below

REPORTS_ROOT = Path(__file__).resolve().parents[2] / "reports" / "evaluation"


def _call_query(base_url: str, token: str, session_id: str, question: str,
                top_k: int = 5, timeout: int = 60) -> Dict[str, Any]:
    url = f"{base_url.rstrip('/')}/api/query"
    body = json.dumps({
        "session_id": session_id, "query": question, "top_k": top_k,
        "modality": "all", "files": None, "provider": None,
    }).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
    )
    start = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        elapsed_ms = (time.perf_counter() - start) * 1000
        data = json.loads(resp.read().decode("utf-8"))
        data["_latency_ms"] = elapsed_ms
        return data


def _percentiles(values: List[float]) -> Dict[str, float]:
    if not values:
        return {}
    values = sorted(values)
    def pct(p):
        idx = min(len(values) - 1, int(round(p / 100 * (len(values) - 1))))
        return values[idx]
    return {"P50": pct(50), "P75": pct(75), "P90": pct(90), "P95": pct(95), "P99": pct(99)}


def run_against_live_backend(base_url: str, token: str, session_id: str,
                             dataset_path: str, top_k: int = 5) -> Dict[str, Any]:
    dataset = load_dataset(dataset_path)
    run_id = writer.new_run_id()
    out_dir = REPORTS_ROOT / run_id
    fig_dir = out_dir / "figures"

    retrieved_lists: List[List[str]] = []
    relevant_sets: List[set] = []
    latencies: List[float] = []
    citation_precisions: List[float] = []
    citation_presence_flags: List[bool] = []
    citation_details: List[Dict[str, Any]] = []
    faithfulness_flags: List[bool] = []
    used_llm_flags: List[bool] = []
    failures: List[Dict[str, Any]] = []
    resource_samples: List[Dict[str, Any]] = []
    errors = 0

    total_items = len(dataset)

    print()
    print("=" * 70)
    print(f"Starting live evaluation: {total_items} questions")
    print(f"Session: {session_id}")
    print(f"Timeout per question: 60 seconds")
    print("=" * 70)
    print()

    for index, item in enumerate(dataset, 1):
        question_start = time.perf_counter()

        print(
            f"[{index}/{total_items}] "
            f"{item['question_id']} | "
            f"{item['question'][:90]}",
            flush=True
        )

        # One CPU/RAM/GPU sample per question.
        if resource_snapshot is not None:
            try:
                resource_samples.append(
                    resource_snapshot.snapshot()
                )
            except Exception:
                pass

        try:
            resp = _call_query(
                base_url,
                token,
                session_id,
                item["question"],
                top_k=top_k
            )

            elapsed = time.perf_counter() - question_start

            print(
                f"    OK | "
                f"API: {resp.get('_latency_ms', 0):.0f} ms | "
                f"Total: {elapsed:.1f}s",
                flush=True
            )

        except (urllib.error.URLError, TimeoutError, OSError) as exc:

            errors += 1

            elapsed = time.perf_counter() - question_start

            failure_type = "request_error"

            if isinstance(exc, TimeoutError):
                failure_type = "timeout"

            elif isinstance(exc, urllib.error.URLError):
                reason = getattr(exc, "reason", None)

                if isinstance(reason, TimeoutError):
                    failure_type = "timeout"

            failures.append({
                "question_id": item["question_id"],
                "failure_type": failure_type,
                "detail": str(exc)
            })

            print(
                f"    ERROR | "
                f"{failure_type} | "
                f"{elapsed:.1f}s | "
                f"{exc}",
                flush=True
            )

            continue

        latencies.append(
            resp.get("_latency_ms", 0.0)
        )

        used_llm_flags.append(
            bool(resp.get("used_llm"))
        )

        faithfulness_flags.append(
            bool(resp.get("faithfulness_warning"))
        )

        retrieved_ids = [
            h.get("id")
            for h in resp.get("retrieved", [])
        ]

        relevant_ids = set(
            item.get("relevant_chunk_ids") or []
        )

        if relevant_ids:
            retrieved_lists.append(
                retrieved_ids
            )
            relevant_sets.append(
                relevant_ids
            )

        required = set(
            item.get("required_citations") or []
        )

        cited_files = {
            c.get("file")
            for c in resp.get("citations", [])
            if c.get("file")
        }

        citation_present = bool(cited_files)

        citation_presence_flags.append(
            citation_present
        )

        if required:
            valid_flags = [
                f in required
                for f in cited_files
            ]

            precision = cm.citation_precision(
                list(cited_files),
                valid_flags
            )

            citation_precisions.append(
                precision
            )

            citation_details.append({
                "question_id": item["question_id"],
                "required_citations": sorted(required),
                "cited_files": sorted(cited_files),
                "citation_precision": precision,
                "citation_present": citation_present
            })
        else:
            citation_details.append({
                "question_id": item["question_id"],
                "required_citations": [],
                "cited_files": sorted(cited_files),
                "citation_precision": None,
                "citation_present": citation_present
            })


        if item["category"] == "unanswerable":

            answer_text = (
                resp.get("answer", "")
                .lower()
                .strip()
            )

            abstention_patterns = [
                "i could not find",
                "i couldn't find",
                "could not find",
                "couldn't find",
                "not found in the provided sources",
                "not present in the provided sources",
                "not available in the provided sources",
                "not mentioned in the provided sources",
                "not contained in the provided sources",
                "not enough information",
                "insufficient information",
                "cannot answer from the provided sources",
                "can't answer from the provided sources",
                "unable to answer from the provided sources"
            ]

            abstained = any(
                pattern in answer_text
                for pattern in abstention_patterns
            )

            if not abstained:

                failures.append({
                    "question_id": item["question_id"],
                    "failure_type": "possible_hallucination",
                    "detail": (
                        "Expected abstention on an "
                        "unanswerable question; answer "
                        "did not look like an abstention. "
                        "Manual review needed."
                    )
                })

    print()
    print("=" * 70)
    print(
        f"Evaluation requests completed: "
        f"{total_items - errors}/{total_items}"
    )
    print(f"Request errors/timeouts: {errors}")
    print("=" * 70)
    print()

    retrieval_metrics = {}

    if retrieved_lists:

        for k in (1, 3, 5, 10):

            retrieval_metrics[
                f"recall@{k}"
            ] = (
                sum(
                    rm.recall_at_k(
                        r,
                        s,
                        k
                    )
                    for r, s in zip(
                        retrieved_lists,
                        relevant_sets
                    )
                )
                / len(retrieved_lists)
            )

            retrieval_metrics[
                f"precision@{k}"
            ] = (
                sum(
                    rm.precision_at_k(
                        r,
                        s,
                        k
                    )
                    for r, s in zip(
                        retrieved_lists,
                        relevant_sets
                    )
                )
                / len(retrieved_lists)
            )

        retrieval_metrics["mrr"] = rm.mrr(
            retrieved_lists,
            relevant_sets
        )

        retrieval_metrics["map"] = (
            rm.mean_average_precision(
                retrieved_lists,
                relevant_sets
            )
        )

    else:

        retrieval_metrics = {
            k: None
            for k in [
                "recall@1",
                "recall@5",
                "precision@1",
                "precision@5",
                "mrr",
                "map"
            ]
        }

    generation_metrics = {
        "used_llm_rate": (
            sum(used_llm_flags)
            / len(used_llm_flags)
        )
        if used_llm_flags
        else None,

        "faithfulness_warning_rate": (
            sum(faithfulness_flags)
            / len(faithfulness_flags)
        )
        if faithfulness_flags
        else None,
    }

    citation_report = {
    "citation_precision": (
        sum(citation_precisions)
        / len(citation_precisions)
        if citation_precisions
        else None
    ),
    "citation_presence_rate": (
        sum(citation_presence_flags)
        / len(citation_presence_flags)
        if citation_presence_flags
        else None
    ),
}

    citation_report["per_question"] = citation_details
    perf = _percentiles(latencies)

    performance_metrics = (
        {
            f"query_latency_{k.lower()}_ms": v
            for k, v in perf.items()
        }
        if perf
        else {
            "query_latency_p50_ms": None,
            "query_latency_p95_ms": None,
        }
    )

    resource_summary: Dict[str, Any] = {}

    if resource_samples:

        for key in (
            "cpu_percent",
            "ram_percent"
        ):

            values = [
                s[key]
                for s in resource_samples
                if s.get(key) is not None
            ]

            if values:

                resource_summary[
                    f"{key}_min"
                ] = round(
                    min(values),
                    1
                )

                resource_summary[
                    f"{key}_mean"
                ] = round(
                    sum(values)
                    / len(values),
                    1
                )

                resource_summary[
                    f"{key}_max"
                ] = round(
                    max(values),
                    1
                )

        gpu_values = [
            s["gpu"]["gpu_utilization_percent"]
            for s in resource_samples
            if s.get("gpu")
        ]

        resource_summary[
            "gpu_utilization_percent_mean"
        ] = (
            round(
                sum(gpu_values)
                / len(gpu_values),
                1
            )
            if gpu_values
            else None
        )

    else:

        resource_summary = {
            "cpu_percent_mean": None,
            "ram_percent_mean": None,
            "gpu_utilization_percent_mean": None
        }

    report = {
        "run_id": run_id,
        "timestamp": run_id,
        "dataset_path": str(dataset_path),
        "num_questions": len(dataset),
        "num_errors": errors,

        "config": {
            "base_url": base_url,
            "session_id": session_id,
            "top_k": top_k,
            "request_timeout_seconds": 60
        },

        "retrieval": retrieval_metrics,
        "generation": generation_metrics,
        "citations": citation_report,
        "performance": performance_metrics,
        "resources": resource_summary,
        "failures": failures,
        "report_dir": str(out_dir),
    }

    _write_all(
        report,
        out_dir,
        fig_dir,
        retrieval_metrics,
        perf,
        resource_samples
    )

    return report

def _write_all(report, out_dir: Path, fig_dir: Path, retrieval_metrics: dict,
               perf: dict, resource_samples: Optional[List[dict]] = None) -> None:
    writer.write_json(report, out_dir)
    writer.write_markdown_summary(report, out_dir)
    writer.write_csv([{"metric": k, "value": v} for k, v in retrieval_metrics.items()],
                     out_dir, "retrieval_metrics.csv")

    at_k = {int(k.split("@")[1]): v for k, v in retrieval_metrics.items()
           if k.startswith("recall@") and v is not None}
    if at_k:
        plots.plot_at_k_curve(at_k, "Recall@K", "Recall", fig_dir, "01_recall_at_k.png")
    if perf:
        plots.plot_latency_percentiles(perf, fig_dir, "02_latency.png", "Query Latency")
    if resource_samples:
        writer.write_csv(resource_samples, out_dir, "resource_metrics.csv")
        cpu = [s["cpu_percent"] for s in resource_samples if s.get("cpu_percent") is not None]
        ram = [s["ram_percent"] for s in resource_samples if s.get("ram_percent") is not None]
        if cpu or ram:
            plots.plot_resource_usage(
                {k: v for k, v in (("CPU %", cpu), ("RAM %", ram)) if v},
                fig_dir, "03_resource_usage.png", "CPU/RAM Usage During Run",
            )

    writer.print_terminal_summary(report)


# ------------------------------------------------------------------ self-test
def run_self_test() -> Dict[str, Any]:
    """Exercises the exact same metric/report/graph code paths with
    synthetic data, to prove the framework itself works without needing a
    live backend. NEVER presented as a real evaluation — see the loud
    labeling in the report and the separate reports/evaluation/selftest_*
    directory."""
    run_id = "selftest_" + writer.new_run_id()
    out_dir = REPORTS_ROOT / run_id
    fig_dir = out_dir / "figures"

    synthetic_retrieved = [["a", "b", "c", "d", "e"], ["x", "y", "z"], ["p", "q", "r", "s"]]
    synthetic_relevant = [{"b", "d"}, {"z"}, {"q", "t"}]

    retrieval_metrics = {}
    for k in (1, 3, 5):
        retrieval_metrics[f"recall@{k}"] = sum(
            rm.recall_at_k(r, s, k) for r, s in zip(synthetic_retrieved, synthetic_relevant)
        ) / len(synthetic_retrieved)
    retrieval_metrics["mrr"] = rm.mrr(synthetic_retrieved, synthetic_relevant)
    retrieval_metrics["map"] = rm.mean_average_precision(synthetic_retrieved, synthetic_relevant)

    perf = {"P50": 310.0, "P90": 640.0, "P95": 820.0, "P99": 1500.0}  # SYNTHETIC

    # Resource samples here are NOT synthetic — psutil gives a real reading
    # of whatever machine runs --self-test. Included to prove the resource
    # capture + plotting path works end to end, same spirit as the rest of
    # self-test: real code, exercised for real, just not against a real RAG
    # workload.
    resource_samples = []
    if resource_snapshot is not None:
        try:
            resource_samples = [resource_snapshot.snapshot() for _ in range(3)]
        except Exception:
            resource_samples = []


    report = {
        "run_id": run_id, "timestamp": run_id,
        "dataset_path": "SYNTHETIC (self-test — not a real dataset)",
        "num_questions": len(synthetic_retrieved), "num_errors": 0,
        "config": {"mode": "self-test", "note": "synthetic retrieval/latency data; "
                                                 "resource samples below are real"},
        "retrieval": retrieval_metrics,
        "generation": {"used_llm_rate": 1.0, "faithfulness_warning_rate": 0.0},
        "citations": {"citation_precision": 0.9},
        "performance": {f"query_latency_{k.lower()}_ms": v for k, v in perf.items()},
        "resources": {"note": "real psutil reading of the machine running --self-test"}
                     if resource_samples else {"note": "psutil not available"},
        "failures": [], "report_dir": str(out_dir),
        "SELF_TEST_DISCLAIMER": (
            "This report was generated from synthetic, hand-written data to "
            "verify the evaluation framework's own plumbing (metrics -> "
            "reports -> graphs). It is NOT a real evaluation of the RAG "
            "application. Run without --self-test against a live backend "
            "and a real dataset for an actual evaluation."
        ),
    }
    _write_all(report, out_dir, fig_dir, retrieval_metrics, perf, resource_samples)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--token", default=None, help="Bearer token for an already-logged-in user")
    parser.add_argument("--session-id", default="real-eval-v1", help="Session whose documents to query against")
    parser.add_argument("--dataset", default=str(
        Path(__file__).resolve().parents[1] / "datasets" / "rag_test_dataset.json"))
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--self-test", action="store_true",
                        help="Run the framework against synthetic data instead of a live backend.")
    parser.add_argument("--provider", choices=["ollama", "groq", "both"], default="ollama")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    # Delegate seamlessly to MasterEvaluationRunner
    from evaluation.runners.run_all import MasterEvaluationRunner
    runner = MasterEvaluationRunner(
        provider_name=args.provider,
        dataset_path=args.dataset,
        session_id=args.session_id or "real-eval-v1",
        base_url=args.base_url,
        token=args.token,
        top_k=args.top_k,
        self_test=args.self_test,
    )
    runner.run()


if __name__ == "__main__":
    main()
