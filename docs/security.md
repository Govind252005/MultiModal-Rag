# Security

This document describes the security posture of this application **as
actually implemented and verified in this repository** — not an aspirational
target. See `docs/security/threat-model.md` for the threat model and
`AUDIT_REPORT.md` for the original findings this work addresses.

## Implemented and verified (unit-tested with fakes; not run against the
## live app end-to-end — see "Verification method" below)

- **Password storage**: PBKDF2-HMAC-SHA256, 200,000 iterations, per-user
  random salt. Minimum length 8 (`config.PASSWORD_MIN_LENGTH`).
- **Token auth**: HMAC-signed, expiring tokens with a random per-token id
  (`jti`). `POST /api/auth/logout` revokes the presented token immediately
  without affecting the user's other sessions/devices. Revoked ids are kept
  in `storage/revoked_tokens.json`, pruned of anything past its natural
  expiry.
- **Login/registration rate limiting**: sliding-window counter + lockout,
  in-process (single-backend-process deployments; back with Redis for a
  multi-process deployment). Config: `LOGIN_MAX_ATTEMPTS`,
  `LOGIN_WINDOW_SECONDS`, `LOGIN_LOCKOUT_SECONDS`,
  `REGISTER_MAX_ATTEMPTS`/`_WINDOW_SECONDS`/`_LOCKOUT_SECONDS`.
- **Chat/ingest rate limiting**: `CHAT_RATE_LIMIT_PER_MINUTE`,
  `INGEST_RATE_LIMIT_PER_HOUR`, same mechanism.
- **Upload limits**: `MAX_FILES_PER_REQUEST`, `MAX_UPLOAD_SIZE_MB` (checked
  against `UploadFile.size` where the ASGI server provides it).
- **CORS**: explicit allowlist (`config.ALLOWED_ORIGINS`); `["*"]` is no
  longer the unconditional default — `CORS_ALLOW_ALL=1` is a documented,
  opt-in-only local-dev escape hatch.
- **Provider API keys**: Fernet-encrypted at rest (`keystore.py`, unchanged
  from before this pass — it was already solid), never returned to the
  frontend, never logged. Verified by the repo's own `test_verify.py`.
- **Cloud provider error handling**: classified by `generation/providers/errors.py`
  so an invalid key or malformed request fails immediately and visibly,
  rather than silently generating a different provider's answer in its
  place. Unit-tested with 5 scenarios (see `AUDIT_REPORT.md` progress notes).
- **Provider activation**: a cloud provider can only be activated
  (`POST /api/llm/providers/{provider}/activate`) if a key is already
  stored for it — activation never happens implicitly.
- **Ollama network isolation**: `docker-compose.yml` no longer publishes
  Ollama's port to the host; the backend reaches it over the internal
  Docker network by service name.
- **Tenant isolation**: every retrieval/cache/session/lexical-index
  operation is scoped by `user_id` (and `session_id` where applicable).
  The new `lexical_index.py` module was specifically unit-tested for
  cross-user leakage (see test transcript in the implementation notes) —
  it does not leak.

## Verification method (read this before trusting anything above)

This development environment has **no network access and none of the
app's runtime dependencies installed** (no FastAPI, torch, chromadb,
redis-py, ollama-py). Every change above was verified by:
1. Careful reading of the surrounding code before and after the change.
2. Unit-testing the pure-logic modules (`auth.py`, `lexical_index.py`,
   `active_provider.py`, `router.py`/`errors.py`) in isolation, using fake
   `config` modules and fake provider/exception objects, with explicit
   assertions (not just "it ran without crashing").
3. Running this repo's own pre-existing `backend/test_verify.py` smoke
   test against the modified code — it passes.

None of this is a substitute for running the real FastAPI app against a
real Ollama instance, real cloud provider keys, and real concurrent users.
That has not happened. Treat every claim above as "implemented and
logically verified," not "load-tested in production."

## Explicitly NOT done

- No dependency vulnerability scan (`pip-audit`, `npm audit`) has been run —
  this sandbox has no network to reach PyPI/npm registries or a CVE
  database.
- No static analysis (`ruff`, `mypy`, `bandit`, `semgrep`, ESLint) has been
  run.
- No penetration testing, fuzzing, or OWASP Top 10 checklist walkthrough
  has been performed.
- No Docker image scan.
- Frontend XSS/sanitization audit (`dangerouslySetInnerHTML` usage, if any)
  has not been performed.
- File-signature/magic-byte validation on uploads is still TODO (filenames
  are sanitized to a basename, but content-type/signature is not checked
  against the extension).
- No CSRF protection has been added — acceptable as long as auth stays
  bearer-token-based (not cookies), but if cookie-based auth is ever added,
  this must be revisited.

## Final security statement (brief §152's own template, honestly filled in)

No known critical or high-severity vulnerability was identified in the code
paths touched by this pass, by the automated unit tests and manual review
performed above, as of this writing. This is **not** a claim of "zero
vulnerabilities" — no dependency scan, static analysis, or penetration test
has been run, and none of this was executed against the live, fully
assembled application. Ongoing patching, dependency scanning with real
network access, and a real security review before any production/public
deployment are still required.
