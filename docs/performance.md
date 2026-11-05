# Performance

No benchmark numbers in this document are fabricated. Where a real
number doesn't exist yet (this development environment has no GPU, no
live Ollama), that's stated plainly instead of guessed — see
`REMAINING_WORK.md` Bucket A for how to produce real ones on your
hardware.

## What changed, and why it should help (reasoned, not yet measured)

| Change | Why it should be faster/lighter | Measured? |
|---|---|---|
| Persistent SQLite FTS5 lexical index (was: rebuild BM25 from the whole corpus every query) | O(index lookup) instead of O(corpus size) per query | No — needs a real corpus at scale to show the difference |
| Adaptive CLIP skip for image-free sessions | Skips a CLIP embedding call + vector query entirely when there's nothing to search | No |
| `qwen3:4b` default (was `qwen3:8b`), `num_predict` cap, `think=false` | Smaller model + bounded output + no reasoning tokens = lower TTFT and higher tokens/sec, at some quality cost | No — run `python -m evaluation.benchmark_ollama` on your machine |
| Streaming (`/api/query/stream`) | User sees the first token as soon as it's generated instead of waiting for the whole answer | Structurally true (it's just not buffering); TTFT itself is measured (see below), "perceived latency improvement" is not separately quantified |
| Ingestion modes (`fast`/`balanced`/`max_quality`) | `fast` skips OCR fallback, table extraction, and embedded-image extraction/captioning entirely | No — depends heavily on your documents |
| Double-checked locking on model loaders | Avoids loading the same multi-hundred-MB model twice under concurrent first-requests | Yes, at the level of "the race is closed" (see `CHANGES.md`'s concurrency test) — not "here's how many seconds that saves you," which depends on your hardware |

## What IS measured, for real

- **TTFT and tokens/sec**: captured from Ollama's own streaming response
  (`generation/llm_client.py::stream_chat`), not estimated. Every
  generation logs these via `observability/metrics.py` — check `/metrics`
  or the structured `[llm_observability]` log lines on your running
  instance for real numbers from your hardware.
- **Query latency percentiles**: `evaluation/runner/run_eval.py` computes
  real P50/P75/P90/P95/P99 from actual `/api/query` calls, once you run
  it against your live backend (see `docs/evaluation.md`).
- **Session-write concurrency**: the lock+atomic-write fix in `sessions.py`
  was verified to prevent lost updates under 30 concurrent writers, with
  a side-by-side test proving the *old* code lost 28 of 30 — see
  `CHANGES.md` for the transcript. This is a correctness fix with a
  performance-adjacent framing (it also means no wasted retries from a
  corrupted read), not a "queries/sec" number.

## How to get real numbers on your machine

```bash
# GPU/Ollama diagnostic first
python scripts/maintenance/diagnose_gpu.py

# Sweep a few (context, output-length) configs against your Ollama:
python -m evaluation.benchmark_ollama --model qwen3:4b

# Full retrieval+generation+citation+latency evaluation against real
# documents and questions:
python -m evaluation.runner.run_eval --base-url http://localhost:8000 \
    --token <token> --session-id <id> --dataset your_dataset.json
```

Both write reports with graphs under `reports/`. See `docs/evaluation.md`
and `docs/metrics.md` for what each number in those reports means and
what it doesn't.

## Resource monitoring

`/health/dependencies` and `evaluation/runner/run_eval.py`'s reports both
include a live CPU/RAM snapshot (`backend/observability/resources.py`,
via `psutil` — a new dependency added this pass). GPU/VRAM are
best-effort via `nvidia-smi`: `None` if it's not on PATH (as it correctly
is in this sandbox, which has no GPU), real numbers on a machine that has
one.
