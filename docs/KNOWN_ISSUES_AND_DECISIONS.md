# Known Issues and Decisions

## Confirmed and repaired

### Evaluation test contract mismatch

- Root cause: `router.py` passes `model=` to cloud providers, but the test fake did not accept it. The resulting `TypeError` prevented retry, failover, and circuit-breaker behavior from being tested.
- Fix: updated the fake provider signatures in `tests/unit/test_provider_router.py`.
- Evidence: focused provider suite passes 8/8.

### Metric API drift

- Root cause: existing tests and likely callers expected answer/classification helpers from `retrieval_metrics.py`, while implementations had moved to `generation_metrics.py` and `compute_roc_pr_auc`.
- Fix: added thin compatibility wrappers and imported missing `Any`; imported missing `Optional` in `retrieval_evaluator.py`.
- Evidence: retrieval metric suite passes 12/12; combined focused run passes 20/20.

## Repaired documentation inconsistency

- The README quick-start model was corrected from `qwen3:8b` to the backend's current default `qwen3:4b`.

## Unverified or blocked

- Live Ollama availability, exact installed model, latency, token throughput, and real answer quality require the user's running service and corpus.
- Groq model discovery and generation require network access and a user-supplied credential. Model-list availability must not be treated as generation authorization.
- Frontend production build and deterministic browser E2E are verified; live upload/provider-switch E2E remains service-gated.
- `backend/verify_backend.py` must be invoked as `python -m backend.verify_backend` from the repository root; direct script execution does not resolve the package import. The module invocation still requires the installed backend dependencies, including `cryptography`.
- Existing JSON/Chroma storage is appropriate for the documented local single-process target, but not a substitute for a transactional multi-process database.
- `npm install` reported 2 moderate and 4 high advisories in the frontend dependency tree. No blanket `npm audit fix` was applied; dependency upgrades require a separate compatibility review.
- Live Groq generation and provider comparison remain blocked until a user-owned encrypted Groq key and an accessible model are configured.

## Decisions

- Preserve the existing shared retrieval path and provider router; provider comparison must reuse the same dataset and retrieval configuration.
- Preserve raw per-question failures and represent unavailable metrics as `NOT RUN`/null, never as zero or a fabricated score.
- Do not reset vector stores, delete historical reports, expose secrets, or change provider fallback semantics without a regression test and evidence.