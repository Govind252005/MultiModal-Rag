# RAG Evaluation Framework

Location: `evaluation/`. This is real, runnable code — verified in this
pass by actually running it (see the honesty notes below for exactly what
"verified" means here). It is not, itself, a report of your app's RAG
quality — it's the tool you run to produce one.

## What's here

```
evaluation/
  datasets/    schema.py (validator) + example_dataset.json (template)
  metrics/     retrieval_metrics.py, citation_metrics.py — pure functions,
               no dependency on the app; unit-tested against hand-computed
               values in test_retrieval_metrics.py
  visualization/plots.py — matplotlib graph generation, saved as PNGs
  reports/     writer.py — JSON/CSV/MD report writer + terminal printer
  runner/      run_eval.py — ties it together; the thing you actually run
```

## Running it

### 1. Self-test (no live backend needed)
Proves the framework's own plumbing works — metrics → reports → graphs —
using synthetic, hand-written numbers. **This is not an evaluation of your
app.** Every output file it produces says so explicitly.

```bash
python -m evaluation.runner.run_eval --self-test
```

### 2. Real evaluation (needs a running backend + real ground truth)
1. Start the backend and ingest some real documents into a session.
2. Log in and get a bearer token (`POST /api/auth/login`).
3. Copy `evaluation/datasets/example_dataset.json` and replace every
   `REPLACE ME` with real questions about your actual documents, and real
   `relevant_chunk_ids`/`required_citations` (the chunk ids come from
   `/api/query`'s `retrieved[].id` field — run a query once and look).
4. Run:
   ```bash
   python -m evaluation.runner.run_eval \
       --base-url http://localhost:8000 \
       --token <your token> \
       --session-id <the session you ingested into> \
       --dataset path/to/your_dataset.json
   ```
5. Look at `reports/evaluation/<timestamp>/summary.md` and `figures/`.

## What this pass actually verified vs. what it didn't

**Verified by actually running it:**
- Every metric formula, against hand-computed expected values (see
  `evaluation/metrics/test_retrieval_metrics.py` and the equivalent inline
  checks for citation metrics).
- The graph generator produces real, correctly-rendered PNGs.
- The full runner pipeline end-to-end, in both self-test mode and against
  a deliberately unreachable backend (confirmed it reports `NOT RUN`
  everywhere instead of a fabricated number — see `docs/release-checklist.md`).

**NOT verified (because it requires things this environment doesn't have):**
- That the metrics, when run against YOUR real documents and a live Ollama
  instance, produce good or bad numbers. That's the actual evaluation —
  it can only happen in your environment, with your data.
- Generation-quality metrics (answer correctness, faithfulness beyond the
  app's own heuristic `faithfulness_warning` flag, hallucination detection)
  need either a labeled reference answer set or an LLM-judge call, neither
  of which this pass built. `evaluation/metrics/citation_metrics.py`'s
  `faithfulness_score()`/`hallucination_rate()` functions exist and are
  tested at the arithmetic level, but the runner doesn't yet call an LLM
  judge to produce the `claims_total`/`claims_supported_by_evidence`
  inputs they need — that's the next piece to build, not something faked
  here.
- ROC/AUC: the function exists and is tested, but the runner doesn't yet
  wire up a labeled binary classification task (e.g. "was this retrieved
  chunk actually relevant?") to feed it — see `evaluation/metrics/retrieval_metrics.py`'s
  `roc_curve()` docstring for what inputs it needs.

## Extending it
- Add more metrics to `evaluation/metrics/` following the existing
  pattern (pure function, no app dependency, a hand-computed test).
- Add more plot types to `evaluation/visualization/plots.py`.
- The runner currently only exercises `/api/query`; extending it to also
  hit `/api/query/image`, `/api/query/audio`, and multi-hop mode is
  straightforward — copy `_call_query()`'s pattern.
