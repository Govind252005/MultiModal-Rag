"""
Ollama performance benchmark (transformation brief §149):
    python -m evaluation.benchmark_ollama

Sweeps a small set of (num_ctx, num_predict) configurations against a
LIVE Ollama instance, using the exact same streaming client the app
itself uses (backend/generation/llm_client.py), so TTFT/tokens-per-sec
numbers here are the same real numbers the app would report, not a
separate simulated measurement path.

This sandbox has no Ollama instance to benchmark against, so running
this here will honestly print "Ollama not reachable" for every
configuration rather than fabricated numbers. Run it on your machine
with `ollama serve` running and `qwen3:4b` (or whatever model you want
to sweep) pulled.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

_BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(_BACKEND))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluation.reports import writer

try:
    from observability import resources as resource_snapshot
except Exception:
    resource_snapshot = None

REPORTS_DIR = Path(__file__).resolve().parents[1] / "reports" / "ollama"

# brief §77's experiment matrix, adapted to what's actually configurable
# in this app's config.py (LLM_MODEL/LLM_NUM_CTX/OLLAMA_NUM_PREDICT).
DEFAULT_SWEEP: List[Dict[str, Any]] = [
    {"label": "A: 4096ctx/512out", "num_ctx": 4096, "num_predict": 512},
    {"label": "B: 2048ctx/512out", "num_ctx": 2048, "num_predict": 512},
    {"label": "C: 4096ctx/256out", "num_ctx": 4096, "num_predict": 256},
]

BENCHMARK_PROMPT = (
    "Summarize, in two sentences, the main advantages of local (on-device) "
    "language model inference compared to a cloud API."
)


def _run_one(model: str, num_ctx: int, num_predict: int, think: bool) -> Dict[str, Any]:
    """Runs one generation through the app's real streaming client and
    returns its real metrics dict — never estimates a number llm_client
    didn't actually report."""
    import config
    import generation.llm_client as llm_client

    # Temporarily point the shared client at this sweep point's config.
    # Restored in the `finally` below so this function has no lasting
    # side effect on the module it borrows.
    original = (config.LLM_MODEL, config.LLM_NUM_CTX, config.OLLAMA_NUM_PREDICT, config.OLLAMA_THINK)
    config.LLM_MODEL, config.LLM_NUM_CTX, config.OLLAMA_NUM_PREDICT, config.OLLAMA_THINK = (
        model, num_ctx, num_predict, think)
    try:
        metrics = None
        for chunk in llm_client.stream_chat("You are a helpful assistant.", BENCHMARK_PROMPT):
            if chunk.get("done"):
                metrics = chunk["metrics"]
        return metrics or {}
    except llm_client.LLMError as exc:
        return {"error": str(exc)}
    finally:
        config.LLM_MODEL, config.LLM_NUM_CTX, config.OLLAMA_NUM_PREDICT, config.OLLAMA_THINK = original


def run_sweep(model: str = "qwen3:4b", sweep: List[Dict[str, Any]] = None,
             think: bool = False) -> Dict[str, Any]:
    sweep = sweep or DEFAULT_SWEEP
    run_id = writer.new_run_id()
    results = []
    for point in sweep:
        before = resource_snapshot.snapshot() if resource_snapshot else None
        metrics = _run_one(model, point["num_ctx"], point["num_predict"], think)
        after = resource_snapshot.snapshot() if resource_snapshot else None
        results.append({
            "label": point["label"], "model": model,
            "num_ctx": point["num_ctx"], "num_predict": point["num_predict"],
            "think": think, **metrics,
            "ram_before_gb": before["ram_used_gb"] if before else None,
            "ram_after_gb": after["ram_used_gb"] if after else None,
            "vram_used_mb": (after.get("gpu") or {}).get("vram_used_mb") if after and after.get("gpu") else None,
        })

    out_dir = REPORTS_DIR / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    writer.write_json({"run_id": run_id, "model": model, "results": results}, out_dir)
    writer.write_csv(results, out_dir, "ollama_benchmark.csv")

    print("=" * 60)
    print("OLLAMA BENCHMARK".center(60))
    print("=" * 60)
    for r in results:
        if r.get("error"):
            print(f"{r['label']:<24} FAILED: {r['error']}")
        else:
            ttft = r.get("ttft_ms")
            tps = r.get("tokens_per_second")
            print(f"{r['label']:<24} TTFT={ttft if ttft is not None else 'N/A':<8} "
                 f"tok/s={tps if tps is not None else 'N/A'}")
    print(f"\nReport: {out_dir}")
    print("=" * 60)
    return {"run_id": run_id, "results": results, "report_dir": str(out_dir)}


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="qwen3:4b")
    parser.add_argument("--think", action="store_true")
    args = parser.parse_args()
    run_sweep(model=args.model, think=args.think)


if __name__ == "__main__":
    main()
