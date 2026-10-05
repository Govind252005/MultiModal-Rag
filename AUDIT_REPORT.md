# AUDIT REPORT — Multimodal Offline RAG (minor-main)
Generated from an actual read of the uploaded repository. No metric below is invented —
where something wasn't measured, it's marked `NOT MEASURED` rather than guessed.

## 0. Scope note
This repo is a real, working single-service FastAPI + React app (~3,900 lines of backend
Python, 35 backend modules, one React frontend). It is **not** currently a multi-node,
Postgres/Redis-cluster, Kubernetes-grade platform — it's a well-built local/offline RAG app
with Chroma, Redis-optional caching, and JSON-file auth/session storage.

The transformation brief calls for ~155 sections of production hardening (threat models,
full eval framework, CI/CD, k8s, Prometheus, etc.). That is genuinely a multi-week, multi-person
effort. Below is the honest Phase-0 audit the brief itself requires before any code changes,
with concrete, verified findings — prioritized so we can work through it in real phases instead
of a single unverifiable "big bang" rewrite.

## 1. Architecture as it actually exists today
```
React (Vite/TS) ── HTTPS/HTTP ── FastAPI (main.py)
                                    ├── auth.py       (PBKDF2 + HMAC token, JSON user store)
                                    ├── keystore.py    (Fernet-encrypted per-user provider keys)
                                    ├── sessions.py    (one JSON file per chat session)
                                    ├── cache.py       (Redis, optional, keyed per user+route)
                                    ├── retrieval/
                                    │     ├── embeddings.py   (SBERT text + CLIP)
                                    │     ├── vector_store.py (Chroma, 2 collections: text/image)
                                    │     └── search.py       (dense + BM25 + CLIP → RRF → cross-encoder rerank)
                                    ├── ingestion/     (PDF/DOCX parse, OCR, BLIP caption, Whisper audio, chunker, async jobs)
                                    └── generation/
                                          ├── providers/ (ollama, gemini, cloud_providers: openai/claude/groq via a router+registry)
                                          └── answer.py, multihop.py, query_enhance.py
```
Provider abstraction, RRF fusion, cross-encoder reranking, per-user/session/file scoping,
async ingestion jobs, and encrypted-at-rest API keys **already exist and are reasonably built**.
This is a solid foundation — the plan should extend it, not replace it (consistent with the
brief's own "do not rewrite unnecessarily" instruction).

## 2. Verified findings (read directly from source, not assumed)

### P0 — Critical
| # | Finding | Evidence |
|---|---|---|
| P0-1 | **CORS wildcard in production**: `allow_origins=["*"]` | `backend/main.py:47-50` |
| P0-2 | **Ollama port published to the host** (`11434:11434`), reachable outside the backend | `docker-compose.yml` |
| P0-3 | **No login/register rate limiting or brute-force backoff** — `authenticate()` has no attempt counter | `backend/auth.py` |
| P0-4 | **No token revocation/logout invalidation** — tokens are pure HMAC+expiry; nothing server-side can invalidate one before its 7-day TTL | `backend/auth.py:107-129` |
| P0-5 | **Automatic cloud→local failover is unconditional**, not error-classified — `PROVIDER_FAILOVER_TO_LOCAL=1` by default, contradicting the brief's own §52/§51A.21 requirement to classify errors before failing over | `backend/config.py:175` |

### P1 — High
| # | Finding | Evidence |
|---|---|---|
| P1-1 | **BM25 index is rebuilt from scratch on every single query** — loads the entire scoped text corpus and reconstructs `BM25Okapi` per request. This is exactly the anti-pattern the brief calls out (§9) and is the biggest latency/scale risk as corpora grow | `backend/retrieval/search.py:118-133` |
| P1-2 | **Ollama path has no `think=false`, no `num_predict` cap, no streaming** — `llm_client.chat()` is a single blocking non-streaming call; `OllamaProvider.supports_streaming()` returns `False` | `backend/generation/llm_client.py`, `backend/generation/providers/ollama_provider.py:34-35` |
| P1-3 | **Default local model is `qwen3:8b`, context hardcoded to 8192** — not `qwen3:4b`/4096 as the brief's target, and not configurable via env (`LLM_NUM_CTX` is a literal, not `os.getenv`) | `backend/config.py:133-135` |
| P1-4 | **Cache key uses `history_len` instead of a history hash** — two different conversations of equal length collide onto the same cache entry (brief §20 calls this out by name) | `backend/main.py:395` |
| P1-5 | **Password minimum is 6 characters, PBKDF2 not Argon2id** (200k iterations — acceptable but not the brief's target) | `backend/auth.py:27,75-76` |
| P1-6 | **CLIP branch always runs when modality is "all"/"image"**, even for sessions with zero images — wastes a CLIP-text embedding call every query | `backend/retrieval/search.py:216-230` |

### P2 — Medium
| # | Finding | Evidence |
|---|---|---|
| P2-1 | No explicit backend "active provider" state (§51A.9) — provider is chosen per-request via `req.provider`; there's no persisted default the frontend can read back other than `config.DEFAULT_PROVIDER` | `backend/main.py` (query/extract/summarize routes) |
| P2-2 | Sessions are one JSON file per session with no visible file locking/atomic-write/corruption-recovery | `backend/sessions.py` |
| P2-3 | No file-signature/magic-byte validation on uploads — filename is sanitized (`Path(...).name`) but content-type/signature isn't checked | `backend/main.py:132-136` |
| P2-4 | `.env.example` at repo root defaults `LLM_MODEL=qwen3:8b`, inconsistent with backend default and the brief's target | `.env.example` |
| P2-5 | No visible request-size limits, per-endpoint rate limits, or structured request-ID logging | `backend/main.py` (global) |

### P3 — Low / not yet assessed (would need dedicated passes)
- Dependency scan (`pip-audit`, `npm audit`) — not run yet, no network egress in this sandbox to do it live.
- Frontend XSS/sanitization audit of `AnswerText.tsx`, `dangerouslySetInnerHTML` usage — not yet read.
- No RAG evaluation framework, ground-truth dataset, or metrics harness exists yet (brief §63-121) — this is a from-scratch build, not a fix.
- No CI pipeline, static analysis (ruff/mypy/bandit), or Docker hardening (non-root user, pinned base images) verified yet.

### What's already good (don't re-do this)
- Per-user/session/file scoping is enforced server-side on every route (`_require_owner`, `vector_store` `where` filters) — no obvious IDOR found in the routes read so far.
- Provider API keys: Fernet-encrypted at rest, never returned to the frontend, deletion supported (`keystore.py`).
- RRF fusion + cross-encoder reranking + citation de-duplication logic is already implemented and reasonably designed (`search.py`).
- Cache is already scoped by `route:user_id:hash(payload)` — tenant isolation is correct, just the hash's inputs need fixing (P1-4).

## 3. Recommended phase order (adapted from the brief's §146, scoped to what's real here)
1. **Security P0 fixes** — CORS allowlist, Ollama internal-only network, login rate limiting, token revocation list, error-classified failover.
2. **Ollama/local-inference target** — `qwen3:4b` default, `think=false`, `num_predict`, configurable context, streaming (SSE) end to end.
3. **RAG latency fix** — persistent BM25 via SQLite FTS5 (build on ingest, not on query), adaptive CLIP skip when a session has no images.
4. **Cache correctness** — `history_hash` instead of `history_len`, include resolved model name.
5. **Provider-switching state** — explicit `/api/llm/active` backend state per §51A, rather than pure per-request `provider` param.
6. Everything else in the original brief (full eval framework, CI/CD, k8s, threat model doc, etc.) — real, valuable, but each is its own multi-turn effort; best tackled after 1-5 land and can be verified against a baseline.

## 4. Honesty note (per the brief's own §113/§152)
No performance numbers (TTFT, tokens/sec, Recall@K, etc.) are reported here because none have
been measured yet — this sandbox has no GPU/Ollama runtime attached to this conversation, so
any number would be fabricated. Once phase 2 lands, benchmarking needs to run against your
actual hardware (Ollama + GPU), not this audit environment.
