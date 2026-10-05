# Troubleshooting

## "Cannot reach the local LLM" / Ollama errors
1. `python scripts/maintenance/diagnose_gpu.py` — confirms whether Ollama
   is reachable at all and whether `qwen3:4b` is actually pulled.
2. `curl http://localhost:11434/api/tags` — same check, by hand.
3. `ollama pull qwen3:4b` if it's not listed.
4. Check `/health/dependencies` on the backend — it reports Ollama's
   status independently of the rest of the app.

## 401 on every request after it used to work
Your token expired (`TOKEN_TTL_HOURS`, default 7 days) or was revoked
(you called `/api/auth/logout` from this or another session). Log in
again.

## A cloud provider "isn't working" after I added a key
Storing a key (`POST /api/providers/key`) never activates it by itself
(this is intentional — §51A.13). Check:
1. `POST /api/providers/validate` — is the key actually valid?
2. `GET /api/llm/active` — is this provider actually the active one?
3. `POST /api/llm/providers/{name}/activate` — did you call this?
If a cloud call fails with an authentication error, the app will **not**
silently fall back to Ollama (brief §52/§51A.21) — you'll get the real
error. Check `docs/security/threat-model.md`'s "classified failover"
note if you're expecting automatic fallback and not seeing it: that's
correct behavior for an invalid-key error, not a bug.

## `python -m security.audit` says everything is SKIPPED
That means `pip-audit`/`bandit`/`npm audit` aren't installed, not that
they ran clean. `pip install pip-audit bandit` and `npm ci` in
`frontend/`, then re-run.

## Evaluation run shows `NOT RUN` for every metric
The backend wasn't reachable at the `--base-url`/`--token`/`--session-id`
you gave `evaluation.runner.run_eval`. This is intentional (brief §113:
never fabricate a metric) — fix the connection details and re-run rather
than trusting a stale report.

## A file won't upload — "File content does not match its extension"
The magic-byte check (`ingestion/file_signature.py`) rejected it — the
file's actual content doesn't match what its extension claims (a renamed
file, a corrupted download, or genuinely something else masquerading as
that type). Re-download/re-export the file and try again. If you're
certain the file is legitimate and this is a false positive, check
`ingestion/file_signature.py`'s docstring — MP3/AAC signature checks are
intentionally permissive; PDF/DOCX/image/WAV/FLAC/OGG are strict.

## An upload silently didn't change anything
Check the response's `skipped_duplicate` field — if the exact same file
content was already ingested with the same pipeline version and
ingestion mode, re-ingesting it is a deliberate no-op (brief §45). Change
the file's content, or pass a different `mode`, to force reprocessing.

## Circuit breaker seems "stuck" on a cloud provider
`GET /health/dependencies` shows `circuit_breakers` state per provider.
It self-heals after `CIRCUIT_BREAKER_COOLDOWN_SECONDS` (default 60s) by
allowing one trial request through — it never needs a manual reset. If
it keeps re-opening, the provider is actually down/misconfigured, not
the breaker misbehaving.

## Docker: HuggingFace models re-downloading every restart
If you're upgrading from before this pass, your old `hf_cache` Docker
volume was mounted at `/root/.cache/huggingface`; the backend now runs
as a non-root user and expects `/app/hf_cache` (see `docs/deployment.md`).
Models will re-download once into the new path — expected, one-time cost.
