# Architecture

## Current (as of this transformation pass)

```
React (Vite/TS) ── HTTPS/HTTP ── FastAPI (main.py)
                                    │
                    ┌───────────────┼──────────────────────────────┐
                    │               │                              │
                    ▼               ▼                              ▼
                 auth.py        cache.py (Redis, optional)   keystore.py
            (PBKDF2, per-token   scoped: route:user_id:hash   (Fernet-encrypted
             revocation, login   (payload incl. history_hash,  per-user provider
             rate limiting)      resolved model)               API keys)
                    │
                    ▼
             generation/active_provider.py   <- persisted per-user active
                                                  provider (§51A), NOT the
                                                  same thing as "has a key
                                                  on file" or "key validated"
                    │
                    ▼
          generation/providers/router.py
                    │  classified failover (errors.py): invalid key/request
                    │  fail immediately; only rate-limit/network/5xx retry
                    │  or fail over to Ollama, and only if enabled.
        ┌───────────┼────────────────────────────────┐
        ▼           ▼            ▼           ▼        ▼
    ollama_      gemini_      cloud_providers.py (openai/claude/groq)
    provider     provider     — all normalized to the same streaming
    (Qwen3 4B,     protocol: {"delta":...}* then {"done":True,"metrics":...}
     think=false,
     num_ctx/num_predict
     from config,
     real streaming)

Retrieval (unchanged in shape, changed in implementation):
  retrieval/search.py
    ├── dense text search      -> vector_store.query_text (Chroma)
    ├── lexical search         -> retrieval/lexical_index.py  (NEW: SQLite
    │                              FTS5, built at ingest time, not rebuilt
    │                              per query — was rank_bm25.BM25Okapi
    │                              rebuilt from the whole corpus every call)
    ├── CLIP image search      -> vector_store.query_images, now SKIPPED
    │                              entirely when vector_store.has_images()
    │                              is False for the current scope
    ├── RRF fusion              (unchanged)
    └── cross-encoder rerank    (unchanged)

Ingestion (unchanged): ingestion/ingest.py -> parse/OCR/caption/transcribe
  -> chunk -> embed -> vector_store.add_text_chunks() / add_image()
  add_text_chunks() now ALSO writes into lexical_index.py in the same call,
  so the dense and lexical indexes can never drift apart.
```

## What changed and why (see AUDIT_REPORT.md for the evidence trail)

| Area | Before | After |
|---|---|---|
| Lexical search | `BM25Okapi` rebuilt from the whole scoped corpus on every `/api/query` call | Persistent SQLite FTS5 index, updated incrementally at ingest/delete time |
| CLIP retrieval | Always ran for `modality in {all, image}` | Skipped when the scope has zero images (`vector_store.has_images()`) |
| Local LLM | `qwen3:8b`, hardcoded 8192 context, no `think`/`num_predict`, blocking-only | `qwen3:4b` default, env-configurable context/`num_predict`/`think`, real streaming with TTFT/tokens-per-sec |
| Cloud failover | Any exception → unconditional fallback to Ollama if `PROVIDER_FAILOVER_TO_LOCAL` | Errors classified (invalid key/request vs. rate-limit/network/5xx); only the latter ever retry or fail over |
| Provider selection | Per-request only; no persisted state | `generation/active_provider.py` — explicit backend-authoritative state per §51A, `/api/llm/active` + `/api/llm/providers/{p}/activate` |
| Cache key | `history_len` (collides across different histories of equal length) | `history_hash` (hash of the actual role+content sequence) + resolved model name |
| CORS | `allow_origins=["*"]` unconditionally | `config.ALLOWED_ORIGINS` allowlist; `CORS_ALLOW_ALL=1` is an explicit, documented dev-only opt-in |
| Auth | No login rate limit, no token revocation, 6-char passwords | Login/register rate limiting with lockout, per-token revocation (logout), 8-char minimum |
| Ollama network exposure | `11434:11434` published to the host in `docker-compose.yml` | Not published; backend reaches it over the internal Docker network only |
| Streaming | None — every provider blocked until the full answer was ready | `/api/query/stream` (SSE), normalized across all 5 providers |

## What is explicitly NOT done in this pass

This codebase's transformation brief (see the two uploaded documents) describes
a full production platform: a from-scratch RAG evaluation/benchmarking
framework with 20+ metrics and auto-generated graphs, a formal threat model
with a full attack-surface inventory, CI/CD, Kubernetes manifests,
Prometheus/Grafana, automated dependency/security scanning, and a
multi-day concurrency/stress-test suite. None of that exists yet. Building
it honestly (i.e., with real measured numbers, not invented ones) requires
running this app against a live Ollama instance and a real document/eval
corpus — something this development environment cannot do (no network, no
GPU, no Ollama runtime attached). See `docs/release-checklist.md` for what
would need to happen before any of those sections could be honestly marked
complete.
