# Metric Definitions

Every metric below is implemented in `evaluation/metrics/` and unit-tested
against hand-computed values (see `docs/evaluation.md` for what "tested"
means precisely). This document is the plain-language reference; the code
is the source of truth for the exact formula.

## Retrieval metrics

| Metric | Formula | Purpose | Limitation |
|---|---|---|---|
| **Recall@K** | relevant items in top K / total relevant items | Did we find everything relevant, within a budget of K results? | Undefined-by-convention as 1.0 when there's nothing relevant to find — check your ground truth isn't accidentally empty. |
| **Precision@K** | relevant items in top K / K | Of what we returned, how much was actually useful? | Penalizes returning fewer than K items as if the missing slots were wrong — fine for a fixed-K RAG context window, less fine if K is just a "return up to" cap. |
| **Hit Rate@K** | 1 if ≥1 relevant item in top K, else 0 | Coarse "did we get at least something right" signal | Says nothing about ranking quality within the top K. |
| **MRR** | mean(1 / rank of first relevant result) | How high up the FIRST relevant result appears, on average | Ignores everything after the first hit — two systems that both rank the right answer #1 tie, even if one buries every other relevant item. |
| **MAP** | mean(Average Precision) across queries | Rewards ranking ALL relevant items highly, not just the first one | More sensitive to your ground truth being complete (missing a relevant chunk id in your dataset silently changes the score). |
| **NDCG@K** | DCG@K / ideal DCG@K | Ranking quality with graded relevance (some sources more relevant than others) | Needs graded relevance judgments to be more informative than binary Recall/Precision — with binary labels it's a smoother version of the same signal. |

## Generation metrics

| Metric | Formula | Purpose | Limitation |
|---|---|---|---|
| **Exact Match** | 1 if normalized strings equal, else 0 | Strict correctness for short factual answers | Useless for anything with valid paraphrase — don't use it for open-ended answers. |
| **Token F1** | harmonic mean of token-overlap precision/recall | Rough overlap between generated and reference answer | Purely lexical — "The revenue was $5M" vs "Revenue: five million dollars" scores low despite being the same answer. Not a substitute for semantic similarity or human judgment. |
| **Answer Correctness / Completeness / Faithfulness** | Not a formula — needs a human or LLM-judge label per answer (see `evaluation/metrics/citation_metrics.py::faithfulness_score`, which computes the ratio once you have the judgment) | Whether the answer is actually right, whether it covers what was asked, whether it's grounded in evidence | This pass built the aggregation math, not the judge. Producing `claims_total`/`claims_supported` inputs needs either human review or a separate LLM-judge call this pass didn't build. |

## Citation metrics (brief §68)

| Metric | Formula | Purpose |
|---|---|---|
| **Citation Precision** | valid citations used / total citations used | Of the citations the answer gave, how many actually check out? |
| **Citation Recall** | claims with a valid citation / claims requiring one | Of the claims that needed backing, how many got it? |
| **Citation Accuracy** | citations checked that support their claim / citations checked | Narrower than precision — the per-citation correctness rate. |
| **Citation Completeness** | claims that got any citation / claims requiring one | Did we even try to cite what needed it (separate from whether the citation was right)? |
| **Faithfulness** | claims supported by evidence / total claims | Did the answer stay grounded in what was retrieved? |
| **Hallucination Rate** | unsupported claims / total claims | The complement of faithfulness, tracked separately because it's the number people actually want to see minimized. |
| **Abstention Accuracy** | correctly-declined unanswerable questions / total unanswerable questions | On questions with no real answer in the corpus, did the system correctly say so instead of inventing one? |

All five of the citation-quality metrics above need a "does this citation
actually support this claim" judgment as an input — same caveat as
generation metrics: the arithmetic is built and tested, the judge that
produces the input isn't.

## Classification metrics (ROC/AUC)

Brief §69/§117: ROC/AUC is **only** computed for an explicitly defined
binary classification task (a score + a 0/1 label), never as a generic
RAG-quality number. `evaluation/metrics/retrieval_metrics.py::roc_curve()`
returns `{"applicable": False, ...}` rather than a fabricated AUC when only
one class is present in the labels — this was verified by test (see
`test_roc_auc_undefined_when_one_class` in the test file).

## Performance metrics

| Metric | Meaning |
|---|---|
| **TTFT** | Time to first generated token — captured for real from Ollama's/each cloud provider's own streaming response (see `generation/llm_client.py::stream_chat`), never estimated. |
| **Tokens/sec** | completion_tokens / generation_time — same source, real numbers when streaming is used, `None`/`NOT RUN` when it can't be computed (e.g. a provider didn't report token counts). |
| **P50/P90/P95/P99** | Latency percentiles across a batch of requests — computed by `evaluation/runner/run_eval.py::_percentiles()`, a plain nearest-rank percentile over whatever latencies were actually measured. |
| **Cache Hit Rate** | Not yet instrumented — `cache.py` doesn't currently expose hit/miss counters to `observability/metrics.py`. Listed here as a known gap, not implemented as a guess. |

## Honesty statement

Every formula in this document has a corresponding implementation in
`evaluation/metrics/` that was checked against hand-computed values before
being trusted (see `docs/evaluation.md`). Where a metric needs an input
this pass doesn't produce (a human/LLM-judge label), that's stated plainly
above rather than papered over with a stub that always returns 1.0 or a
plausible-looking fake number.
