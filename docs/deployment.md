# Deployment

This app already has `SETUP_GUIDE.md` and `DEPLOYMENT.md` at the repo
root with real, detailed instructions for local and Docker deployment —
this page doesn't duplicate them (brief §121 itself says "remove
redundant/duplicate documentation"). It covers what changed across this
transformation and links out for the rest.

## Local (unchanged process, new model)
Follow `SETUP_GUIDE.md`, with one difference: pull `qwen3:4b` instead of
whatever model an older version of this guide named:
```bash
ollama pull qwen3:4b
```

## Docker Compose
```bash
docker compose up -d --build
docker compose exec ollama ollama pull qwen3:4b
```
What's different from before this pass (see `AUDIT_REPORT.md`/`CHANGES.md`):
- Ollama's port is no longer published to the host — only the backend
  can reach it, over the internal compose network.
- The backend container now runs as a non-root user (`appuser`); the
  HuggingFace model cache moved from `/root/.cache/huggingface` to
  `/app/hf_cache` to match (the compose volume mount was updated too —
  if you have an old `hf_cache` volume from before this change, models
  will just re-download once into the new path).
- Both containers have a `HEALTHCHECK` now (`/health/live` for the
  backend, a root-path probe for the frontend).
- Set `ALLOWED_ORIGINS` in `docker-compose.yml`'s backend environment to
  your real origin before exposing this beyond localhost/LAN.

## Kubernetes
`deploy/k8s/rag-app.yaml` — written this pass, **never applied to a real
cluster** (this development environment has none). Read the honesty note
at the top of that file before using it. Start with:
```bash
kubectl apply --dry-run=client -f deploy/k8s/rag-app.yaml
```
There's also a pre-existing `k8s/multimodal-rag.yaml` in this repo, for
an all-in-one single-image deployment — that's a different deployment
shape (one image, not separate ollama/backend/frontend services) and
predates this pass. Pick whichever matches how you've built your images.

## Production checklist
See `docs/release-checklist.md` for the full list. The two items you
cannot skip:
1. `ALLOWED_ORIGINS` set to your real origin(s) — never `CORS_ALLOW_ALL=1`
   outside local dev.
2. HTTPS in front of this (a reverse proxy, or your cluster's ingress
   controller) — this app has no built-in TLS termination. The k8s
   Ingress template has the annotations SSE streaming needs
   (`proxy-read-timeout`, `proxy-buffering: off`) already filled in;
   fill in the TLS secret reference yourself.

## Ingestion mode
New in this pass (brief §44) — `/api/ingest` and `/api/ingest/async` both
accept a `mode` form field: `fast` | `balanced` | `max_quality` (default:
`max_quality`, i.e. unchanged from before this option existed). See
`docs/performance.md` for what each tier actually skips.
