# API Reference

Full interactive docs (brief §93, satisfied automatically by using
FastAPI): **`/docs`** (Swagger UI) and **`/openapi.json`** on your running
backend — every request/response schema, auth requirement, and Pydantic
validation rule is generated from the actual code, so it can't drift from
this document the way a hand-written reference can. What follows is a
map of what exists and the things the auto-generated docs don't say
explicitly (auth header format, rate limits, versioning).

## Auth
Bearer token in `Authorization: Bearer <token>`, obtained from
`POST /api/auth/login` or `/api/auth/register`. Tokens last
`TOKEN_TTL_HOURS` (default 168h/7 days) or until `POST /api/auth/logout`
revokes that specific token.

## Versioning
Every route is reachable at both `/api/...` and `/api/v1/...` (the
latter is transparently rewritten to the former by middleware in
`main.py`). Existing clients calling `/api/...` are unaffected; new
clients can use the explicit `/v1` prefix.

## Rate limits
| Endpoint(s) | Limit |
|---|---|
| `/api/auth/login` | `LOGIN_MAX_ATTEMPTS` per `LOGIN_WINDOW_SECONDS`, keyed by email+IP |
| `/api/auth/register` | `REGISTER_MAX_ATTEMPTS` per `REGISTER_WINDOW_SECONDS`, keyed by IP |
| `/api/query*`, `/api/extract`, `/api/summarize` | `CHAT_RATE_LIMIT_PER_MINUTE` per user |
| `/api/ingest*` | `INGEST_RATE_LIMIT_PER_HOUR` per user |

A rate-limited request gets `429` with the wait time in the error message.

## Route groups
- **Auth**: `/api/auth/register`, `/login`, `/logout`, `/me`
- **Admin** (role=admin only): `GET /api/admin/users`,
  `POST /api/admin/users/{email}/role`, `GET /api/admin/security-events`
- **Sessions**: `/api/sessions` (paginated: `?limit=&offset=`),
  `/api/sessions/{id}`, rename/delete
- **Ingestion**: `/api/ingest` (sync), `/api/ingest/async` +
  `/api/ingest/status/{job_id}`, both accept `mode=fast|balanced|max_quality`
- **Query**: `/api/query` (blocking, cached), `/api/query/stream` (SSE,
  not cached), `/api/query/image`, `/api/query/audio`, `/api/extract`,
  `/api/summarize`
- **Providers**: `GET /api/providers`, `POST /api/providers/validate`,
  `POST`/`DELETE /api/providers/key`, and the §51A active-provider
  endpoints: `GET /api/llm/active`, `POST /api/llm/providers/{name}/activate`
- **Health/observability**: `/api/health`, `/health/live`, `/health/ready`,
  `/health/dependencies`, `/metrics` (Prometheus text format)
- **Files/media**: `/api/files`, `/api/source/{doc_id}`, `/api/media/...`

## Error shape
```json
{"error": {"code": "HTTP_400", "message": "...", "request_id": "..."}}
```
`request_id` matches the `X-Request-ID` response header on the same
request, and the `[request]` structured log line — hand both to whoever's
debugging an issue.

## Streaming protocol (`/api/query/stream`)
Server-Sent Events. Three event types, in order:
```
event: citations
data: [{"index": 1, "file": "...", ...}, ...]

event: delta          (repeated, one per generated chunk)
data: {"text": "..."}

event: done
data: {"used_llm": true, "metrics": {"provider": "ollama", "ttft_ms": ..., ...}}
```
