# Operations

Day-to-day running of this app once it's deployed. See
`docs/deployment.md` for getting it running in the first place, and
`docs/troubleshooting.md` for when something's wrong.

## Health checks
- `/health/live` — is the process alive at all (load-balancer liveness probe)
- `/health/ready` — can it actually serve requests (Ollama + storage reachable)
- `/health/dependencies` — full breakdown: storage, vector DB, Ollama,
  Redis, configured cloud providers, circuit-breaker states, live
  CPU/RAM/GPU snapshot

## Metrics
`/metrics` — Prometheus text format. Point a Prometheus scrape config at
it; there's no bundled Grafana dashboard yet (see `REMAINING_WORK.md`).
Key series: `http_requests_total`, `http_request_duration_ms`,
`rag_generation_total`, `llm_latency_ms`, `llm_ttft_ms`,
`llm_tokens_per_second`, `errors_total`, `cache_hits_total`/`cache_misses_total`.

## Logs
Two structured JSONL streams, both on stdout:
- `[request] {...}` — one line per HTTP request (`request_id`, path,
  method, status, duration_ms)
- `[audit] {...}` — security-sensitive events (login/logout/failed
  login/register/provider-key-add-remove/file-upload-delete/session-
  delete/account-reset/admin-role-change), also durably written to
  `storage/audit.log` (rotates at 10MB, one backup kept)

Neither stream ever contains a password, API key, or token — see
`logging_utils.py`'s docstring for the discipline this relies on.

## Admin operations
The first account created is admin automatically (see `docs/api.md`'s
Admin section). As admin:
- `GET /api/admin/users` — list every account (no password hashes)
- `POST /api/admin/users/{email}/role` — promote/demote (`{"role": "admin"|"user"}`)
- `GET /api/admin/security-events?limit=N` — tail the audit log

## Data retention & cleanup
Nothing is deleted automatically. See `docs/data-retention.md` and:
```bash
python scripts/maintenance/cleanup.py --dry-run   # see what's eligible
python scripts/maintenance/cleanup.py              # actually delete it
```

## Backups
```bash
python scripts/maintenance/backup.py                    # secrets excluded by default
python scripts/maintenance/backup.py --include-secrets  # only if you know where this file is going
python scripts/maintenance/backup.py --restore backups/backup-<ts>.tar.gz
```
Restores into `storage_restored/`/`data_restored/` next to your real
directories — never overwrites live data automatically. Move the
restored files into place yourself after reviewing them.

## Diagnostics
```bash
python scripts/maintenance/diagnose_gpu.py   # GPU + Ollama reachability/model-pulled check
python -m security.audit                     # dependency/secret scan (installs tools separately)
python backend/test_verify.py                # fast smoke test of core modules
```

## Rotating the token-signing secret
`storage/secret.key` signs every session token. Deleting/rotating it
invalidates every currently-issued token (everyone has to log in again)
— there's no separate rotation command; stop the backend, replace or
delete the file (a new one is generated on next start), restart.
