# Remaining Work — Step-by-Step Plan

Organized by **what each item needs to be completed honestly**, not by
brief section number — that's the more useful grouping, since most of
what's left falls into just a few buckets. Cross-references to
`COMPLETION_MATRIX.md` are in brackets.

## Bucket A — Needs a live backend + live Ollama (you have this; I don't)

These are all things I could not do in this sandbox (no GPU, no running
Ollama, no network) but that need no new design — the code to run them
already exists. This is the highest-value bucket to run first, because
it validates everything else.

1. **Install and boot the real stack.**
   ```bash
   cd backend && pip install -r requirements.txt
   ollama pull qwen3:4b
   uvicorn main:app --reload   # or however you normally run it
   ```
2. **Run the repo's own smoke test against the live modules** (already
   passes against stubs; confirm it still passes with real imports):
   `python backend/test_verify.py`
3. **Run `python -m security.audit`** with `pip install pip-audit bandit`
   done first, and `npm ci` in `frontend/` done first, then re-run —
   this alone will surface real PASS/FAIL results instead of SKIPPED.
   [§60, §61, §150]
4. **Fill in a real evaluation dataset.** Ingest a handful of real
   documents into a session, ask real questions, copy the resulting
   `retrieved[].id` values into `evaluation/datasets/your_dataset.json`
   (see `docs/evaluation.md` step-by-step). Then:
   ```bash
   python -m evaluation.runner.run_eval --base-url http://localhost:8000 \
       --token <token> --session-id <id> --dataset your_dataset.json
   ```
   This gives you real Recall@K/MRR/NDCG/citation-precision numbers for
   the first time. [§65, §68, §79-83, §148]
5. **Benchmark Ollama for real** — TTFT/tokens-per-sec/VRAM at the
   context/output configurations in the brief's experiment matrix (§76,
   §77). The plumbing to capture TTFT/tokens-per-sec already exists
   (`generation/llm_client.py::stream_chat`); what's missing is a
   dedicated `evaluation/runner/benchmark_ollama.py` that sweeps
   `OLLAMA_NUM_CTX`/`OLLAMA_NUM_PREDICT` combinations and records GPU/VRAM
   (needs `pynvml` or shelling out to `nvidia-smi`, which needs a GPU
   this sandbox doesn't have to even write against confidently). **Step
   to build it**: copy `evaluation/runner/run_eval.py`'s HTTP-calling
   pattern, loop over a list of `(model, num_ctx, num_predict)` tuples,
   set them via env before each Ollama restart (or add a per-request
   options override if you don't want to restart Ollama each time), and
   feed the results through `evaluation/reports/writer.py` +
   `evaluation/visualization/plots.py` (both are backend-agnostic and
   will work unchanged). [§76, §77, §149]
6. **Concurrency/load testing** (§75) and **memory leak testing over
   100-1000 queries** (§134) and **ingestion stress testing with
   1/10/100/500-page PDFs** (§135) — all need the live server running
   under sustained load. A simple approach: `hey` or `locust` against
   `/api/query` for concurrency, and a bash loop calling `/api/ingest`
   with progressively larger PDFs for the ingestion stress test, watching
   `/health/dependencies` and `/metrics` (both already expose what you'd
   want to watch) between runs.
7. **End-to-end provider-switching test** [§51A.26] — the only piece of
   §51A that's untested. With a real Ollama instance and one real cloud
   API key (Groq is cheapest to test with), walk the exact 17-step
   sequence in the brief: ask a question on Ollama, switch to the cloud
   provider, ask again, switch back, ask again, confirming citations and
   session history survive each switch. Everything needed for this to
   work is already built (`active_provider.py`, `/api/llm/*` endpoints,
   `router.py`'s classified failover) — this step is pure verification,
   not new code.
8. **Frontend build.** `cd frontend && npm ci && npm run build` — this
   is the single most important unverified piece from this whole
   engagement, since the SSE streaming client, provider-activation
   wiring, and the `relative_relevance` rename all went in without ever
   being compiled. If `npm run build` fails, the error will point exactly
   at the problem; I'd expect it to succeed given how closely the new
   code followed existing patterns, but "I expect it to succeed" is not
   the same claim as "it succeeded."

## Bucket B — Needs a Kubernetes cluster / Docker daemon (you have this; I don't)

1. `docker compose build && docker compose up` — confirm the backend
   image actually builds with the new `logging_utils.py`/`observability/`
   modules included (nothing about them should need a Dockerfile change,
   but this has never been built).
2. `kubectl apply --dry-run=client -f deploy/k8s/rag-app.yaml` first,
   then a real apply against a test cluster. [§122]
3. **Docker hardening** [§38]: add to `backend/Dockerfile` and
   `frontend/Dockerfile`:
   - `USER appuser` (non-root) after creating the user and chowning
     `/app`
   - pin the base image tag to a digest, not just `python:3.11-slim`
   - add a `HEALTHCHECK` directive pointing at `/health/live`
   - consider `--read-only` + an explicit writable volume for
     `storage/`/`data/` at the compose/k8s level
   This is genuinely quick (an hour of Dockerfile editing) but needs a
   Docker daemon to verify the build still works after each change —
   I don't have one here.
4. **HTTPS/TLS** [§123]: for Docker Compose, put Caddy or nginx in front
   with a Let's Encrypt config (or a self-signed cert for LAN use); for
   k8s, fill in the `rag-tls` secret referenced in
   `deploy/k8s/rag-app.yaml`'s Ingress. Needs a real domain or at least a
   real cluster DNS setup to test against.

## Bucket C — Design decisions I shouldn't make unilaterally

1. ~~**RBAC / admin role**~~ [§24, §127] — **DONE.** Implemented with the
   simplest defensible bootstrap: the first account ever created becomes
   admin automatically, everyone after that is "user". `auth.py::set_role`/
   `list_users`, `main.py::require_admin`, and three endpoints
   (`GET /api/admin/users`, `POST /api/admin/users/{email}/role`,
   `GET /api/admin/security-events`) — all unit-tested, including the
   "fails safe" property for pre-existing accounts with no role field.
   What's still a genuine open design question: a full admin dashboard UI
   (no frontend time left in this pass) and any more granular permission
   model than a flat admin/user split.
2. **PostgreSQL migration** [§40]. Still not done, and still the right
   call not to force: a real, multi-week piece of work on its own
   (schema design, migration scripts, connection pooling, rewriting
   `sessions.py`/`auth.py`'s JSON-file logic against SQLAlchemy or
   similar) — and arguably the wrong move for what this app's
   `docs/architecture.md` documents as an intentionally single-user
   local/desktop target. Worth doing only if you're actually taking this
   multi-tenant/multi-process.
3. ~~**Ingestion modes (FAST/BALANCED/MAX_QUALITY)**~~ [§44] — **DONE.**
   Implemented the brief's own tier definitions directly: FAST = text +
   embedding only; BALANCED = + selective OCR + CLIP; MAX_QUALITY
   (default, i.e. unchanged prior behavior) = + tables + embedded images
   + BLIP captions. Threaded through `/api/ingest`, `/api/ingest/async`,
   and folded into the idempotency fingerprint (changing mode correctly
   forces reprocessing) — all unit-tested.

## Bucket D — Straightforward, no live infra needed

Everything originally listed here is now done. Kept for the record of
what was closed and how:

1. ~~Security headers middleware~~ [§124] — turned out to already be
   implemented earlier in this engagement (found on re-audit, not redone).
2. ~~`MAX_CONTEXT_TOKENS` enforcement~~ [§13] — same: already implemented,
   verified rather than redone.
3. ~~Standardized JSON error envelope~~ [§53] — same: already implemented
   (`main.py`'s `_http_exception_handler`/`_unhandled_exception_handler`),
   verified rather than redone.
4. ~~DB index on `lexical_index`'s `(user_id, session_id)`~~ [§131] —
   **correction, not done as originally described**: I'd claimed this was
   "one CREATE INDEX statement." I tested that claim before implementing
   it and it's wrong — SQLite explicitly forbids indexing virtual tables
   (`sqlite3.OperationalError: virtual tables may not be indexed`). A real
   fix needs a companion regular table with its own indexed columns,
   joined to the FTS5 table by rowid — a legitimate but more involved
   schema change, and genuinely a Bucket-C-style judgment call (worth it
   only at a scale this single-user-local app doesn't target today) rather
   than the quick win originally described. Left undone on purpose rather
   than force a bad fix.
5. ~~Pagination for messages/audit logs~~ [§132] — **DONE.**
   `/api/sessions/{id}` now accepts `message_limit`/`message_offset`
   (opt-in — omitting both preserves exact prior behavior), and
   `/api/admin/security-events` accepts `limit`/`offset` (newest-first).
   Both tested.
6. ~~Retry backoff+jitter~~ [§97] — **DONE.** Exponential backoff+jitter
   between same-provider retries, verified with real timing assertions
   (a 3-attempt sequence took the expected ~0.15s+, a non-retryable error
   took 0.000s — no sleep at all).
7. ~~Move router regression tests into `tests/`~~ [§143] — **DONE.**
   `tests/unit/test_provider_router.py` — 8 tests including a dedicated
   `test_no_infinite_loop_on_exhausted_retries` regression test with a
   hard time budget, run for real.
8. ~~Path-security shared helper~~ [§34] — **DONE.** `main.py::_safe_join`
   (resolve + prefix-check), applied to session-directory creation,
   uploads, session deletion, and account reset. Tested against a `../`
   traversal attempt and an absolute-path injection.
9. ~~Remaining docs~~ [§121] — **DONE.** `docs/deployment.md`,
   `performance.md`, `api.md`, `troubleshooting.md`, `operations.md`,
   `development.md`, plus `docs/data-retention.md` (brief §88).
10. ~~`reports/final/production_readiness_report.md/.json`~~ [§151] —
    **DONE**, filled in honestly from this engagement's actual verified
    results (not fabricated placeholders) — see the file itself for what
    PASS/PARTIAL/NOT_RUN each mean here.
11. ~~OWASP-style path-traversal/IDOR tests~~ [§59] — **DONE.**
    `tests/security/test_path_traversal.py` (5 tests — extracts and runs
    against `main.py`'s live `_safe_join` source, so it can't silently go
    stale) and `tests/security/test_idor.py` (5 tests against `sessions.py`'s
    real ownership logic — one test's assertion was itself wrong on first
    run, caught and fixed by actually executing it, not by inspection).
12. ~~Per-stage ingestion timing~~ [§70] — **DONE.** `parse` and
    `embed_and_index` stage durations pushed to the Prometheus registry
    and returned in `ingest_file`'s result, verified with a mocked-timing
    test.
13. ~~Model memory management / ML init validation / embedding batching~~
    [§101/§102/§103] — **turned out to already be done**, correctly, in
    the pre-existing codebase (lazy singleton loading, an `@app.on_event
    ("startup")` warmup hook, and batched `embed_text()` calls). Verified
    by reading rather than re-implemented.

### Also found and fixed this round (not originally in any bucket — found by testing)
- **Thread-safety race in every ML model loader** [§100] — embedding,
  CLIP, reranker, Whisper, BLIP, and PaddleOCR singletons all used an
  unsafe check-then-load pattern. Fixed with double-checked locking
  everywhere, proven with a side-by-side unsafe-vs-safe concurrency test.
- **Lost-update bug in session storage** [§42] — no locking, no atomic
  writes; concurrent message appends could silently drop updates. Fixed
  with a per-session lock + atomic write-then-rename. Proven two ways: 30
  concurrent writers lost nothing with the fix; the same 30 lost 28 of 30
  with the old code.
- **A real bug in the eval framework's own CSV writer** — `write_csv`
  crashed on any report with heterogeneous rows (e.g. some questions
  succeed, some fail with an extra `error` field) — found by actually
  running `benchmark_ollama.py` against mocked data, not by inspection.
  Fixed to use the union of all rows' keys.
- **GPU/Ollama diagnostic script** [§39] — `scripts/maintenance/diagnose_gpu.py`,
  run for real in this no-GPU sandbox, confirmed it degrades honestly.
- **Resource utilization module** [§74] — `backend/observability/resources.py`
  (psutil-based CPU/RAM, best-effort GPU via `nvidia-smi`), wired into
  `/health/dependencies` and the eval framework's reports/graphs, verified
  with real readings from this machine.
- **`benchmark_ollama` command** [§149] — `evaluation/benchmark_ollama.py`,
  sweep logic and report-writing verified with a mocked Ollama call (the
  real call needs `torch`, genuinely not installed here — that's a correct
  hard failure, not something to mask).
- **Data retention cleanup script** [§88] — `scripts/maintenance/cleanup.py`
  + `docs/data-retention.md`, tested against synthetic aged/recent files
  including the dry-run-touches-nothing and retention=0-disables-everything
  safety properties.
- **Backup/restore script** [§89] — `scripts/maintenance/backup.py`,
  tested end-to-end including an actual restore with byte-for-byte content
  verification, and confirmed secrets are excluded by default.
- **Docker hardening** [§38] — non-root user, HF cache path fix (and the
  matching `docker-compose.yml` volume-mount update), `HEALTHCHECK` in
  both Dockerfiles. Written carefully, cross-checked for internal
  consistency, but **not build-verified** — no Docker daemon in this
  sandbox.

## Bucket E — Real work, but only worth doing after Bucket A tells you it matters

1. **Per-stage ingestion timing / GPU-VRAM capture** [§70, §72, §74] —
   building `psutil`/`pynvml` instrumentation is wasted effort until you
   know (from Bucket A's real benchmark) whether ingestion or generation
   is actually your bottleneck.
2. **Chunk-size A/B benchmark** [§47, §78] — needs the eval framework
   (done) run against a real dataset (Bucket A) at multiple chunk sizes;
   the chunking code itself doesn't need to change, just re-run ingestion
   with different `config.CHUNK_SIZE_WORDS` values and compare Recall@K.
3. **Hallucination/conflicting-source adversarial datasets** [§85, §86]
   — writing good adversarial questions is easier once you've seen how
   the model actually fails on your real corpus (from Bucket A), rather
   than guessing blind.

## Suggested order

1. Bucket A, items 1-3 (boot it, smoke-test it, scan it) — this either
   confirms everything above works or tells you exactly what doesn't,
   cheaply.
2. Bucket A, item 8 (frontend build) — same reasoning, and it's the
   riskiest unverified piece: the SSE streaming client, provider-
   activation wiring, and the `relative_relevance` rename were all
   written but never compiled.
3. Bucket A, item 6 (Docker build) — the non-root-user/HF-cache-path
   changes to `backend/Dockerfile` are the other piece written but never
   build-verified.
4. Bucket A, items 4/7 (real eval dataset, provider-switching E2E) — now
   that the app is confirmed running.
5. Bucket C — decide on PostgreSQL only if you're actually taking this
   multi-tenant/multi-process (RBAC and ingestion modes are already done).
6. Buckets B and E, once A-4/5 give you a stable, measured baseline to
   containerize/harden/optimize further.

Every Bucket D item is now closed — nothing left in this list is blocked
only on effort; everything remaining needs your hardware, a cluster, or a
product decision (see Buckets A, B, C, E above).
