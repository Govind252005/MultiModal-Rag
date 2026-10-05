# CHANGES — This Transformation Pass

This summarizes what was actually done to `minor-main` in this pass. See
`AUDIT_REPORT.md` for the findings this addresses, and `docs/` for
architecture/security/threat-model detail.

## A. What changed (file by file)

| File | Change |
|---|---|
| `backend/retrieval/lexical_index.py` | **New.** Persistent SQLite FTS5 lexical index, replacing per-query `BM25Okapi` rebuild. |
| `backend/retrieval/vector_store.py` | Hooked lexical index sync into `add_text_chunks`/`delete_file`/`delete_session`/`reset`; added `has_images()`. |
| `backend/retrieval/search.py` | `_bm25_search` now reads the persistent index instead of rebuilding one; CLIP branch skipped when scope has no images. |
| `backend/config.py` | `qwen3:4b` default, env-configurable Ollama context/num_predict/think/timeout, CORS allowlist, auth/rate-limit/upload-limit constants. |
| `backend/generation/llm_client.py` | Rewritten: `think`/`num_predict` wired in, real streaming (`stream_chat`) with TTFT/tokens-per-sec from Ollama's own response fields. |
| `backend/generation/providers/base.py` | Normalized streaming protocol (`{"delta":...}` / `{"done":True,"metrics":...}`) as the default for every provider. |
| `backend/generation/providers/ollama_provider.py` | Uses the new streaming client. |
| `backend/generation/providers/cloud_providers.py` | Real `stream_answer()` added for OpenAI, Claude, and Groq. |
| `backend/generation/providers/errors.py` | **New.** Cloud-error classification (invalid key/request vs. rate-limit/network/5xx). |
| `backend/generation/providers/router.py` | Rewritten: classified failover/retry policy, structured observability logging, `stream_generate()`. |
| `backend/generation/active_provider.py` | **New.** Persisted per-user active-provider state (§51A). |
| `backend/generation/answer.py` | Extracted `prepare_answer_context()` so the blocking and streaming answer paths share one prompt/citation implementation. |
| `backend/auth.py` | Rewritten: per-token revocation (logout), login/register rate limiting with lockout, 8-char password minimum. |
| `backend/main.py` | CORS allowlist wired in; `/api/auth/logout`; `/api/llm/active` + `/api/llm/providers/{p}/activate`; `/api/query/stream` (SSE); cache key now uses `history_hash` + resolved model instead of `history_len`, across query/extract/summarize/image/audio; chat rate limiting on all 5 generation endpoints; ingest rate limiting + upload count/size limits; `/api/health` reports Ollama config. |
| `docker-compose.yml` | Ollama port no longer published to the host; `qwen3:4b` + Ollama env defaults; `ALLOWED_ORIGINS` wired in. |
| `.env.example` | All new config knobs documented with their defaults. |
| `backend/test_verify.py` | Updated stubs to match new config surface; still passes. |
| `backend/launcher.py` | Stale `qwen3:8b` fallback corrected. |
| `docs/architecture.md`, `docs/security.md`, `docs/security/threat-model.md`, `docs/release-checklist.md` | **New.** |
| `AUDIT_REPORT.md` | **New** (Phase 0 audit that preceded all of the above). |

### Round 2 additions (frontend, eval framework, CI/CD, observability, security tooling)

| File | Change |
|---|---|
| `frontend/src/types.ts` | Added `ActiveProviderResponse`, `StreamMetrics`. |
| `frontend/src/api.ts` | Added `logout()` (calls the new revocation endpoint), `getActiveProvider()`, `activateProvider()`, and `queryStream()` — a hand-rolled SSE client (fetch + ReadableStream) since `EventSource` can't send a POST body or Bearer header. |
| `frontend/src/App.tsx` | `handleTextQuery` now streams via `/api/query/stream` with automatic fallback to the blocking `/api/query` if streaming fails; provider selection now calls the backend's `activate` endpoint instead of only setting local state; active provider is fetched from the backend on login; `updateMessage` extended to accept a functional updater (needed for incremental delta appends); logout calls the new revocation endpoint. |
| `backend/generation/prompt_templates.py` | `SYSTEM_PROMPT` strengthened with explicit "retrieved content is untrusted data, never instructions" language (brief §15/§16) — this was missing before. |
| `evaluation/` | **New.** Full framework: `metrics/retrieval_metrics.py` + `citation_metrics.py` (Recall@K, Precision@K, Hit Rate@K, MRR, MAP, NDCG@K, F1, ROC/AUC, citation precision/recall/accuracy/completeness, faithfulness, hallucination rate, abstention accuracy), `visualization/plots.py` (matplotlib, saved PNGs), `reports/writer.py` (JSON/CSV/MD + terminal summary), `runner/run_eval.py` (calls the live `/api/query`, or `--self-test` against synthetic data), `datasets/schema.py` + `example_dataset.json`. |
| `backend/observability/metrics.py` | **New.** Dependency-free Prometheus-compatible counter/histogram registry. |
| `backend/main.py` | `/metrics` endpoint + HTTP-level middleware (`http_requests_total`, `http_request_duration_ms`). |
| `backend/generation/providers/router.py` | `_log_generation` now also pushes into the observability registry (`rag_generation_total`, `errors_total`, `llm_latency_ms`, `llm_ttft_ms`, `llm_tokens_per_second`), not just JSON print-logging. |
| `security/audit.py` | **New.** `python -m security.audit` — runs pip-audit/bandit/npm-audit if installed (SKIPPED if not), plus a small dependency-free heuristic secret scanner. |
| `tests/security/test_prompt_injection.py` | **New.** 5 adversarial-document tests against the real (strengthened) system prompt and context-building code. |
| `.github/workflows/ci.yml` | **New.** Lint/type-check/security-scan/test/build pipeline. |
| `deploy/k8s/rag-app.yaml` | **New.** Kubernetes manifests (Namespace/ConfigMap/PVCs/Deployments/Services/Ingress). |
| `docs/evaluation.md`, `docs/metrics.md` | **New.** |

## B. Security — vulnerabilities found and fixed

See `AUDIT_REPORT.md` for the full table with evidence (file/line). Summary:
CORS wildcard, Ollama publicly reachable, no login/register rate limiting,
no token revocation, unconditional cloud-failure failover to local (masking
an explicit provider choice and, worse, an invalid-key error, behind a
silently-generated Ollama answer), 6-char passwords, BM25 rebuilt from the
full corpus per query (a performance/DoS-adjacent issue at scale),
unnecessary CLIP invocation, and a system prompt that never explicitly told
the model retrieved content is untrusted (found while writing the
prompt-injection tests in round 2).

Every one of these has a corresponding fix in this pass, described above.

## C. Performance

**No before/after numbers are reported.** This development environment has
no GPU, no running Ollama instance, and no network access — any number
here would be invented, which both source documents explicitly forbid.
What can be said honestly:
- The lexical search path no longer does O(corpus size) work per query;
  it's now an indexed SQLite FTS5 lookup. The *shape* of the improvement is
  structural and will scale better as the corpus grows, but the concrete
  magnitude (ms saved) has not been measured.
- The streaming path means a user sees the first token as soon as Ollama
  produces it, instead of waiting for the entire answer — again, structural,
  not quantified.

**Action for you**: run `backend/test_verify.py` first (passes today), then
stand up the real app with Ollama + `qwen3:4b` pulled, and compare
`/api/query` latency before/after on your own hardware. That's the only way
to get numbers you can trust.

## D. Ollama

model=`qwen3:4b` (was `qwen3:8b`), context=4096 (was hardcoded 8192, now
`OLLAMA_NUM_CTX`), `num_predict`=512 (new, was unbounded), `think`=false
(new), streaming=on (new — was fully blocking). All env-overridable.

## E. RAG retrieval quality

Not measured (no eval framework exists yet — see below). The retrieval
*pipeline* itself (dense + lexical + CLIP + RRF + rerank) is structurally
unchanged except for the lexical channel's implementation and the CLIP
skip-when-empty optimization; neither should change retrieval quality
(recall/precision) since they don't change what's searched, only how/when.
This is a reasoned expectation, not a measured guarantee.

## F. Citations

Unchanged in this pass — citation building was refactored into
`prepare_answer_context()` for reuse between blocking and streaming, but
the citation logic itself (`_citation`, `_add_confidence`) was not modified.

## G. Testing

- New unit tests written and run (with fakes, in isolation) for:
  `lexical_index.py` (tenant isolation, filtering, deletion, injection-safe
  queries), `auth.py` (password policy, token issue/verify/revoke,
  rate-limit/lockout), `active_provider.py` (default/activate/isolation),
  `router.py`/`errors.py` (5 failover-classification scenarios,
  re-verified in round 2 to also confirm observability wiring). All pass.
- `evaluation/metrics/test_retrieval_metrics.py` — every formula checked
  against hand-computed values; run for real (not just written).
- `tests/security/test_prompt_injection.py` — 5 tests, run for real
  against the actual (strengthened) `prompt_templates.py`; all pass.
- `security/audit.py` — run for real; caught and fixed a genuine
  self-matching bug in its own heuristic secret scanner.
- `evaluation/runner/run_eval.py` — run end-to-end for real in both
  `--self-test` mode and against a deliberately unreachable backend
  (confirmed honest `NOT RUN` reporting rather than fabricated numbers).
- `backend/observability/metrics.py` — run for real with synthetic
  observations; Prometheus text-exposition output checked byte-for-byte
  against expected bucket/counter values.
- Existing `backend/test_verify.py` still passes against all modified code
  (re-run after every round of backend changes).
- `pytest` itself was never run (not installed, no network) — every test
  file above was instead executed directly via a small inline runner
  (shown in the conversation) that calls each `test_*` function and
  reports pass/fail, which is functionally equivalent for files with no
  fixtures/parametrization, but is not the same as a `pytest` CI run.
  `evaluation/requirements.txt` and `.github/workflows/ci.yml` both assume
  a real `pytest` will run these in your environment.

## H. Security scanning

`security/audit.py` was written and run in this sandbox — every external
tool (pip-audit, bandit, npm audit) reported `SKIPPED` because none are
installed here (no network to install them), which is the honest, correct
result for this environment, not a bug. The dependency-free heuristic
secret scanner (also part of this script) did run for real and reported
`PASS`. Run `python -m security.audit` again after `pip install pip-audit
bandit` (and `npm ci` in `frontend/`) in your real environment to get an
actual scan result — see `docs/release-checklist.md`.

## I. Deployment

- **Local**: `ollama pull qwen3:4b`, then run the backend/frontend as
  before (`SETUP_GUIDE.md`/`RUN_AND_LOGIN.md` — not modified in this pass
  beyond the two stale-model-name fixes noted above).
- **Docker**: `docker compose up -d --build`, then
  `docker compose exec ollama ollama pull qwen3:4b`. Ollama is no longer
  reachable from outside the compose network by default.
- **Kubernetes**: `deploy/k8s/rag-app.yaml` — written carefully (11 valid
  YAML documents, cross-checked for internal consistency) but **never
  applied to a real cluster** in this sandbox (none available). Treat it
  as a reviewed starting point, not a verified deployment.
- **Production**: set `ALLOWED_ORIGINS` explicitly; review every new env
  var in `.env.example`; the k8s Ingress template includes the
  long-read-timeout/no-buffering annotations SSE streaming needs, but
  HTTPS/TLS secret provisioning is left to your cluster's usual process
  (not something this pass could set up or test).

## J. Known limitations / explicitly NOT done in this pass

Round 1 built the backend security/performance fixes. Round 2 built the
frontend wiring, the evaluation framework, CI/CD config, a dependency-free
Prometheus metrics endpoint, a security audit script, and prompt-injection
tests. Still not attempted, honestly:
- **Generation-quality judging**: `evaluation/`'s citation/faithfulness/
  hallucination metrics are implemented and unit-tested at the arithmetic
  level, but nothing in this pass builds the LLM-judge or human-review
  step that produces their inputs (`claims_supported_by_evidence`, etc.).
  See `docs/evaluation.md` for exactly what's missing.
- **A real, filled-in ground-truth dataset** — `example_dataset.json` is a
  template with `REPLACE ME` placeholders, not real evaluation data (this
  environment has no ingested documents of yours to write real questions
  against).
- Static analysis (ruff/mypy/bandit/semgrep/ESLint) has been configured in
  CI but never actually run — see section H.
- `tests/rag/`, `tests/performance/`, `tests/e2e/` directories don't exist
  yet — only `tests/security/test_prompt_injection.py` was built.
- File-signature/magic-byte upload validation — still not done.
- Docker image hardening (non-root user, pinned base images beyond what
  was already in the repo, resource limits) — not done.
- Backup/restore procedures, HTTPS/TLS provisioning, Grafana dashboards
  (the `/metrics` endpoint exists; nothing consumes it yet) — not done.
- Table-structure-preserving retrieval, chunking-size benchmarking,
  conflicting-source handling review — not done.
- No `npm install`/`npm run build`/`tsc` was run against the frontend
  changes — no network access to install `node_modules`. The new
  TypeScript was reviewed carefully against the existing file's patterns
  but not compiled.

## K. Final recommendation

**READY WITH CONDITIONS** for continued local/desktop use, now with
streaming, backend-authoritative provider switching, and Prometheus
metrics wired end-to-end (backend and frontend). **NOT READY** for a
public-internet production deployment: no dependency/security scan has
actually found anything (only confirmed the tools aren't installed here),
no live retrieval-quality numbers exist (the framework to produce them is
built and self-test-verified, but has not been run against a real corpus),
the frontend changes were never compiled, and the Kubernetes manifests
were never applied to a real cluster. The honest path forward: run
`npm ci && npm run build` and `python -m security.audit` (with tools
installed) in your real environment as the very next step, then fill in
`evaluation/datasets/example_dataset.json` with real questions and run a
real evaluation.

---

## Addendum — Follow-up rounds (closing out `REMAINING_WORK.md`)

`COMPLETION_MATRIX.md` and `REMAINING_WORK.md` are the authoritative,
current status documents; this addendum records what changed since the
sections above were written, and how each piece was verified.

**Real bugs found and fixed by actually running code (not by inspection):**
- `router.py` infinite loop: a circuit-breaker edit shifted indentation
  and stranded the failover logic after an unconditional `continue`.
  Permanent regression test: `tests/unit/test_provider_router.py`.
- Model-loader race (embedding/CLIP/reranker/Whisper/BLIP/PaddleOCR):
  unsafe check-then-load singletons → double-checked locking. Proven with
  a side-by-side test (unsafe: 20 loads under 20 threads; safe: exactly 1).
- Session-storage lost updates: 30 concurrent appends lost 28 with the old
  code, 0 with the per-session lock + atomic write.
- Eval framework CSV writer crashed on heterogeneous rows (found via
  `benchmark_ollama.py` with mocked data).
- `prompt_templates.py` gained a `config` import (token budget) that broke
  the prompt-injection tests' environment-independence; the test now stubs
  only the one config value it reads.
- One of my own IDOR test assertions was wrong on first run (checked a field
  `list_sessions` deliberately omits); corrected to assert on session
  identity instead.
- Two `str_replace` edits earlier accidentally deleted function `def` lines;
  caught and fixed, and an `ast`-based undefined-name check now runs after
  every edit.
- A claim in an earlier `REMAINING_WORK.md` ("one CREATE INDEX statement"
  for the lexical index) was wrong — SQLite forbids indexing virtual
  tables. Tested before implementing; corrected, not shipped.

**New capabilities, each tested:** file-signature validation; image/PDF/
audio resource limits; SHA-256 idempotent ingestion + pipeline/mode
versioning; ingestion modes (fast/balanced/max_quality); cache hit/miss
metrics; split health endpoints; circuit breaker; retry backoff+jitter;
`/api/v1` versioning; structured request-ID logging + rotating audit log;
minimal RBAC (first user = admin) + 3 admin endpoints; pagination
(sessions, session messages, audit events); path-traversal defense helper;
per-stage ingestion timing; resource monitoring (psutil, best-effort GPU);
`benchmark_ollama`; GPU/Ollama diagnostic; data-retention cleanup script;
backup/restore script (restore verified byte-for-byte); Docker hardening
(non-root, healthchecks — not build-verified); remaining docs; production
readiness report; §19 fake-confidence fix (backend + frontend).

**Test inventory (all run for real in this environment):**
`tests/unit/test_provider_router.py` (8), `tests/security/`
`test_prompt_injection.py` (5), `test_path_traversal.py` (5),
`test_idor.py` (5), `evaluation/metrics/` retrieval + citation metric
checks against hand-computed values, `backend/test_verify.py` smoke test.

**Still not verified (needs your environment):** the Docker/Kubernetes files were never
built/applied; `pip-audit`/`bandit`/`npm audit` never ran (reported SKIPPED);
no real custom evaluation dataset exists beyond the included benchmarks.

### Round 4 additions (Master Implementation Prompt: Groq/Ollama Runtime Switching, Terminal Scorecard, Frontend Verification)

| File | Change |
|---|---|
| `backend/generation/active_provider.py` | Added per-user active model support (`get_active_model()`, `get_active_full()`). |
| `backend/generation/providers/cloud_providers.py` | Added live Groq model discovery (`GroqProvider.get_model_list()`) with graceful fallback to default models. |
| `backend/generation/query_eval.py` | **New.** Computes real-time query metrics (retrieval ms, gen ms, TTFT, token counts, tokens/sec, semantic faithfulness via `FaithfulnessJudge`) and writes an ASCII-safe scorecard to stdout. |
| `backend/main.py` | Integrated `query_eval` into both `POST /api/query` and `POST /api/query/stream`; persists `metrics` inside session assistant messages; exposed `GET /api/providers/{provider}/models`. |
| `frontend/src/types.ts` | Added `ProviderModelsResponse`, `ProviderModel`, updated `ActiveProviderResponse`. |
| `frontend/src/api.ts` | Added `getProviderModels()`, updated `activateProvider()` to accept custom model. |
| `frontend/src/components/ProviderPanel.tsx` | Added dynamic model discovery dropdown for Groq, automatic model loading upon valid API key save. |
| `frontend/src/components/Header.tsx` | Added live active provider & model indicator badge with visual status dot. |
| `frontend/src/App.tsx` | Wired active provider/model synchronization between Header, ProviderPanel, and backend. |
| `frontend/dist/` | **Verified.** Built successfully via `npm run build` with 0 errors. |
| `evaluation/run_eval.py` | **Verified.** Ran `--self-test` successfully with 0 errors, validating all 12 pipeline stages. |
| `docs/LLM_PROVIDERS_AND_EVALUATION.md` | **New.** Comprehensive end-to-end architecture and usage guide. |

