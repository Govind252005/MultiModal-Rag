# Development

## Setup
```bash
cd backend && pip install -r requirements.txt
cd ../evaluation && pip install -r requirements.txt   # matplotlib, for eval graphs only
cd ../frontend && npm ci
ollama pull qwen3:4b
```

## Running
```bash
cd backend && uvicorn main:app --reload
cd frontend && npm run dev
```

## Testing
```bash
python backend/test_verify.py                          # fast smoke test, no live services needed
python tests/unit/test_provider_router.py               # 8 router/failover/circuit-breaker/backoff tests
python tests/security/test_prompt_injection.py          # 5 prompt-injection tests
python tests/security/test_path_traversal.py            # 5 path-traversal tests
python tests/security/test_idor.py                      # 5 IDOR/tenant-isolation tests
pytest tests/ evaluation/metrics/                       # all of the above, once pytest is installed
python -m evaluation.runner.run_eval --self-test         # eval framework self-test (synthetic data)
python -m security.audit                                # security scan (tools installed separately)
cd frontend && npx tsc --noEmit && npm run build          # frontend type-check + build
```

Every test file above also runs directly with `python <file>` (a tiny
manual runner at the bottom of each), so a missing `pytest` install
never blocks running them.

There is no CI running these automatically yet in this repository's own
history — `.github/workflows/ci.yml` exists and is valid, but has never
executed on a real runner (see `REMAINING_WORK.md`).

## Where things live
| Concern | Module |
|---|---|
| Retrieval fusion (dense+lexical+CLIP+RRF+rerank) | `backend/retrieval/search.py` |
| Persistent lexical index | `backend/retrieval/lexical_index.py` |
| Provider routing + failover + circuit breaker | `backend/generation/providers/` |
| Prompt construction + citations | `backend/generation/answer.py`, `prompt_templates.py` |
| Auth + RBAC | `backend/auth.py` |
| Structured/audit logging | `backend/logging_utils.py` |
| Metrics registry | `backend/observability/` |
| Ingestion (parse/OCR/caption/embed) | `backend/ingestion/` |
| RAG evaluation framework | `evaluation/` |
| Maintenance scripts (backup/cleanup/GPU diagnostic) | `scripts/maintenance/` |

## Conventions this codebase follows (see `CHANGES.md`/`AUDIT_REPORT.md` for the reasoning)
- Every module that does something non-obvious explains **why** in its
  docstring, with a brief §-reference where relevant, not just what.
- New singletons (model loaders) use double-checked locking — see
  `retrieval/embeddings.py` for the pattern.
- New mutable shared state (session files, rate limiters, the circuit
  breaker) is protected by an explicit lock, not assumed safe.
- Config constants are env-overridable via `config.py`, never hardcoded
  in the module that uses them.
- Every new pure-logic module (metrics math, error classification, the
  lexical index) has a corresponding test that was actually run, not
  just written — see the many "verified by actually running it" notes
  in `CHANGES.md`.

## Adding a new LLM provider
Implement `generation/providers/base.py::BaseProvider` (four methods:
`generate_answer`, `stream_answer` — inherit the default for a
non-streaming provider — `validate_api_key`, `is_available`), register it
in `generation/providers/registry.py`, add its model/config constants to
`config.py`, and add it to `_PROVIDER_META` in `main.py`. The router,
failover classification, circuit breaker, and cache-key logic all work
against the registry/base-class abstraction — none of them need to
change for a new provider.
