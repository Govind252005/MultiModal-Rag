# Data Retention Policy

Configurable retention for what this app stores locally (see
`docs/architecture.md` for the storage layout). Defaults are conservative
(long retention, nothing deleted automatically) — this is a local/desktop
app where the person running it owns their own data; automatic deletion
defaults to off rather than silently discarding something they wanted.

## What's retained, and for how long (configurable)

| Data | Location | Default retention | Config |
|---|---|---|---|
| Chat sessions + messages | `storage/sessions/*.json` | Indefinite (no auto-delete) | `SESSION_RETENTION_DAYS` (0 = never auto-delete) |
| Uploaded files | `data/<session>/` | Tied to the session — deleted when its session is deleted, never independently | n/a |
| Vector/lexical index chunks | Chroma + `storage/lexical_index.sqlite3` | Tied to the session/file that produced them | n/a |
| Audit log | `storage/audit.log` | Rotates at 10MB (one backup kept: `audit.log.1`) — see `logging_utils.py` | `_MAX_AUDIT_LOG_BYTES` in `logging_utils.py` |
| Revoked-token list | `storage/revoked_tokens.json` | Pruned of anything past its natural token-expiry on every write | n/a (self-pruning) |
| Evaluation reports | `reports/evaluation/<run_id>/` | Indefinite (no auto-delete) | `EVAL_REPORT_RETENTION_DAYS` (0 = never auto-delete) |

## Cleanup job

`scripts/maintenance/cleanup.py` implements the policy above. It is
**never run automatically** — no cron job, no startup hook — because
automatically deleting a user's chat history is exactly the kind of
surprise this app should never spring on someone. Run it yourself,
on whatever schedule you want:

```bash
python scripts/maintenance/cleanup.py --dry-run   # see what WOULD be deleted
python scripts/maintenance/cleanup.py              # actually delete it
```

`--dry-run` always lists candidates without touching anything, so you can
verify the policy does what you expect before pointing it at real data.

## What this does NOT do

- Does not touch provider API keys, the signing secret, or `users.json` —
  account data is never in scope for a "retention" cleanup; that's a
  delete-my-account operation, a different and more consequential action
  this script deliberately doesn't perform.
- Does not touch anything outside `config.STORE_DIR`/`config.DATA_DIR`/
  the evaluation reports directory.
- Has not been run against a real, aged dataset in this development
  environment (no real usage history exists here to test retention
  against) — the date-math and dry-run/delete logic ARE unit-tested with
  synthetic timestamps (see the test transcript in `CHANGES.md`), but
  "tested with fake dates" and "verified against your actual multi-month
  usage history" are different claims.
