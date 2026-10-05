# Release Checklist

Copied structure from the transformation brief (§144), filled in honestly
for the state of this repository as of this pass. **Nothing below is marked
done unless it was actually performed and can be pointed to.**

- [x] Unit tests for new pure-logic modules pass (`lexical_index.py`,
      `auth.py`, `active_provider.py`, `router.py`/`errors.py`) — run with
      fakes in an isolated interpreter, see implementation notes.
- [x] Repo's own pre-existing smoke test (`backend/test_verify.py`) passes
      against the modified code.
- [ ] Full test suite (`pytest`) run — **not done**: FastAPI/torch/chromadb
      etc. are not installed in this development environment (no network
      access to install them). Run `pytest` yourself after `pip install -r
      backend/requirements.txt` in your real environment.
- [ ] Lint (`ruff`/ESLint) — not run.
- [ ] Type checking (`mypy`) — not run.
- [ ] Dependency scan (`pip-audit`, `npm audit`) — not run (no network).
- [ ] Secret scan — not run.
- [ ] Security tests (`tests/security/`) — this directory does not exist
      yet; none of the brief's adversarial/prompt-injection/IDOR tests have
      been written.
- [ ] Docker build — not run (no Docker daemon / not verified in this
      environment). Review `docker-compose.yml` and `backend/Dockerfile`
      before relying on this.
- [ ] Health checks — `/api/health` was extended with Ollama config
      visibility but has not been exercised against a running server.
- [ ] Database migration tested — n/a, this app uses JSON files + Chroma +
      SQLite, no migration framework.
- [ ] Backup tested — not addressed in this pass.
- [ ] Restore tested — not addressed in this pass.
- [ ] RAG evaluation passes — **no evaluation framework exists yet** (brief
      §63+). Building one honestly requires a real document/question
      ground-truth set and a live model to run against; that has not
      happened here.
- [ ] Citation evaluation passes — same as above.
- [ ] Performance benchmark passes — **no benchmark has been run.** Every
      number in this repository's docs about tokens/sec, TTFT, latency,
      etc. that predates this pass should be treated as unverified against
      the current code; nothing new was fabricated to fill the gap.
- [ ] No known critical/high vulnerability — no scan has been run to make
      this claim either way; see `docs/security.md`'s honest statement.
- [ ] Production configuration reviewed — `ALLOWED_ORIGINS`,
      `CORS_ALLOW_ALL`, `PROVIDER_FAILOVER_TO_LOCAL`, and all the new
      rate-limit/upload-limit env vars in `.env.example` should be reviewed
      and set explicitly for your deployment before going live; none of
      the defaults are safe to assume for a public-internet deployment
      beyond "better than the previous unconditional `allow_origins=['*']`
      and unauthenticated-fallback behaviour."

## Before you run this for real

1. `pip install -r backend/requirements.txt` (this pass didn't touch that
   file; verify `rank_bm25` can be removed since `lexical_index.py`
   replaces its only use — see "Cleanup" below).
2. `ollama pull qwen3:4b` (the new default local model).
3. Set `ALLOWED_ORIGINS` to your actual frontend origin(s) if deploying
   beyond `localhost`.
4. Run `python backend/test_verify.py` — should print "All checks passed."
5. Run your existing test suite / manual smoke test of `/api/query` and the
   new `/api/query/stream` endpoint against a real Ollama instance, and
   confirm the SSE stream renders correctly in whatever frontend client you
   build against it (this pass did not touch the React frontend).

## Cleanup opportunity (not done — flagging it)
`rank_bm25` is no longer imported by `retrieval/search.py` (replaced by
`retrieval/lexical_index.py`'s SQLite FTS5 implementation). If nothing else
in the codebase imports it, it can be removed from
`backend/requirements.txt`. Not removed in this pass because dependency
files were out of scope for a no-network verification environment and
removing a currently-listed dependency without being able to actually
`pip install` and test the result felt riskier than leaving one unused
line in a requirements file.
