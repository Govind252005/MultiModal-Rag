"""
FastAPI application — HTTP surface of the multimodal RAG system.

Now MULTI-USER: everyone registers (email + password) and logs in to get a
token. Every request carries the token; all data (chats, files, vector chunks,
media) is scoped to the logged-in user, so nobody can see anyone else's data.

Run (from backend/):   uvicorn main:app --host 0.0.0.0 --port 8000
API docs:              http://localhost:8000/docs
"""

from __future__ import annotations

import hashlib
import json
import io
import shutil
import threading
import time
from pathlib import Path
from typing import List, Optional

from backend import cache as cache_store

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from PIL import Image
from pydantic import BaseModel

from backend import auth
from backend import config
from backend import keystore
from backend import sessions as session_store
from backend.generation import active_provider
from backend.generation import answer as answer_mod
from backend.generation import llm_client
from backend.generation import multihop as multihop_mod
from backend.generation import prompt_templates
from backend.generation import query_enhance
from backend.generation import query_eval
from backend.generation.providers import registry
from backend.generation.providers import circuit_breaker
from backend.generation.providers.router import router as provider_router
from backend.ingestion import ingest as ingest_mod
from backend.ingestion import jobs as ingest_jobs
from backend.ingestion import file_signature
from backend.ingestion.audio_pipeline import transcribe as transcribe_audio
from backend.observability import metrics as obs_metrics
from backend.observability import resources
from backend import logging_utils
from backend.retrieval import late_interaction, search, vector_store

app = FastAPI(title="Multimodal Offline RAG", version="3.0.0")


# ------------------------------------------------------------------ standardized error envelope (brief §53)
# Every error response becomes {"error": {"code", "message", "request_id"}}
# instead of FastAPI's raw {"detail": "..."} — with the same request_id
# the X-Request-ID header carries, so a person reporting "I got an error"
# can be matched to the exact structured log line (brief §54) without
# ever needing a stack trace exposed to them.
_STATUS_CODES = {
    400: "BAD_REQUEST", 401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND",
    409: "CONFLICT", 422: "VALIDATION_ERROR", 429: "RATE_LIMITED",
}


@app.exception_handler(StarletteHTTPException)
async def _http_exception_handler(request: Request, exc: StarletteHTTPException):
    request_id = getattr(request.state, "request_id", None)
    code = _STATUS_CODES.get(exc.status_code, "ERROR" if exc.status_code < 500 else "INTERNAL_ERROR")
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": code, "message": exc.detail, "request_id": request_id}},
        headers=getattr(exc, "headers", None) or {},
    )


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception):
    # brief §25: never expose internal stack traces / exception text to
    # the client. The real exception is still visible server-side via
    # the structured request log this middleware chain already writes.
    request_id = getattr(request.state, "request_id", None)
    logging_utils.log_request(
        request_id or "unknown", path=request.url.path, method=request.method,
        status=500, unhandled_exception=exc.__class__.__name__,
    )
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_ERROR",
                           "message": "An internal error occurred.",
                           "request_id": request_id}},
    )

# ------------------------------------------------------------------ CORS (AUDIT_REPORT.md P0-1)
# `allow_origins=["*"]` previously shipped unconditionally, including for
# production. Origins now come from config.ALLOWED_ORIGINS (env
# ALLOWED_ORIGINS, comma-separated) with an explicit, opt-in-only escape
# hatch (CORS_ALLOW_ALL=1) for local development against a Vite dev server
# on a random port.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if config.CORS_ALLOW_ALL else config.ALLOWED_ORIGINS,
    allow_credentials=not config.CORS_ALLOW_ALL,
    allow_methods=["*"], allow_headers=["*"],
)


# ------------------------------------------------------------------ API versioning (brief §94)
# Non-invasive approach: rather than rename every existing @app.get/@app.post
# route (high risk of a typo breaking something, for a repo already this
# large), requests to /api/v1/* are transparently rewritten to /api/* before
# routing. Every existing route becomes reachable at both paths -- old
# clients (and the existing frontend) keep working unchanged, and new
# clients get an explicit, stable version prefix to code against.
@app.middleware("http")
async def _api_versioning_middleware(request: Request, call_next):
    if request.url.path.startswith("/api/v1/"):
        request.scope["path"] = "/api/" + request.url.path[len("/api/v1/"):]
    return await call_next(request)


# ------------------------------------------------------------------ security headers (brief §124)
# CSP is deliberately permissive on connect-src/img-src rather than
# locked to 'self' only: this app is served from an arbitrary host:port
# the operator chooses (docker-compose/k8s both put the frontend behind
# whatever domain they configure), and the SPA legitimately needs to call
# its own API origin plus render user-uploaded images via /api/media/*.
# A stricter CSP is worth tightening once you know your real deployment
# origin(s) — see docs/security.md.
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data: blob:; "
        "connect-src 'self'; style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; frame-ancestors 'none'"
    ),
}


@app.middleware("http")
async def _security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    for header, value in _SECURITY_HEADERS.items():
        response.headers.setdefault(header, value)
    # HSTS only makes sense once you're actually serving over HTTPS (brief
    # §123) — setting it on a plain-HTTP local/dev server would tell
    # browsers to force HTTPS on a host that doesn't have it yet, locking
    # people out. Gate it on an explicit opt-in instead of guessing from
    # the request.
    if config.FORCE_HSTS:
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=63072000; includeSubDomains")
    return response


# ------------------------------------------------------------------ observability (brief §125-126)
@app.middleware("http")
async def _metrics_middleware(request: Request, call_next):
    """Records http_requests_total and http_request_duration_ms for every
    request, and gives every request a structured, greppable log line
    with a request_id (brief §54) that's also returned as an X-Request-ID
    response header so a client-reported issue can be traced back to the
    exact log line. Deliberately excludes /metrics itself from being
    counted (a metrics endpoint scraping itself into its own counters is
    noise, not signal)."""
    if request.url.path == "/metrics":
        return await call_next(request)
    request_id = logging_utils.new_request_id()
    request.state.request_id = request_id
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        obs_metrics.inc_counter(
            "http_requests_total",
            {"path": request.url.path, "method": request.method, "status": "500"},
        )
        logging_utils.log_request(
            request_id, path=request.url.path, method=request.method,
            status=500, duration_ms=round((time.perf_counter() - start) * 1000, 1),
        )
        raise
    elapsed_ms = (time.perf_counter() - start) * 1000
    obs_metrics.inc_counter(
        "http_requests_total",
        {"path": request.url.path, "method": request.method, "status": str(response.status_code)},
    )
    obs_metrics.observe_histogram(
        "http_request_duration_ms", elapsed_ms,
        {"path": request.url.path, "method": request.method},
    )
    logging_utils.log_request(
        request_id, path=request.url.path, method=request.method,
        status=response.status_code, duration_ms=round(elapsed_ms, 1),
    )
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/metrics")
def metrics():
    """Prometheus-scrapeable text exposition (brief §126). No auth
    required — same as every other Prometheus target; put this behind
    network-level access control (not exposed publicly) in production,
    the same way you would for any /metrics endpoint."""
    return Response(content=obs_metrics.render(), media_type="text/plain; version=0.0.4")


# ------------------------------------------------------------------ startup warmup
@app.on_event("startup")
def _warmup():
    if not config.WARMUP_ON_STARTUP:
        return
    def _run():
        try:
            from backend.retrieval import embeddings            
            embeddings.warmup()
            print("[startup] embedding models warm.")
        except Exception as exc:
            print(f"[startup] warmup skipped: {exc}")
    threading.Thread(target=_run, daemon=True).start()


# ------------------------------------------------------------------ auth dependency
def get_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Not authenticated.")
    uid = auth.verify_token(authorization.split(" ", 1)[1])
    if not uid:
        raise HTTPException(401, "Invalid or expired session. Please log in again.")
    user = auth.get_user_by_id(uid)
    if not user:
        raise HTTPException(401, "Account not found.")
    return user


def require_admin(user: dict = Depends(get_user)) -> dict:
    """brief §24: authorization matrix — user management, system
    configuration, and security-log access are Admin-only. This
    dependency runs get_user() first (so an unauthenticated request
    still gets 401, not a misleading 403), then checks the role."""
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin access required.")
    return user


def _require_owner(session_id: str, user: dict):
    if not session_store.owns(session_id, user["id"]):
        raise HTTPException(404, "Session not found.")


# ------------------------------------------------------------------ request models
class RegisterRequest(BaseModel):
    email: str
    password: str


class QueryRequest(BaseModel):
    session_id: str
    query: str
    top_k: int = config.DEFAULT_TOP_K
    modality: str = "all"
    files: Optional[List[str]] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    # Phase 3 (all optional; None = fall back to server-side config flags).
    rewrite: Optional[bool] = None
    hyde: Optional[bool] = None
    colbert: Optional[bool] = None
    multihop: Optional[bool] = None
    # Evaluation and other batch callers can request a response without
    # adding the exchange to the user's interactive chat history.
    persist_messages: bool = True


class ProviderKeyRequest(BaseModel):
    provider: str
    api_key: str


class ProviderValidateRequest(BaseModel):
    provider: str
    api_key: str


class ActivateProviderRequest(BaseModel):
    model: Optional[str] = None



class CreateSessionRequest(BaseModel):
    title: str = "New chat"


class RenameRequest(BaseModel):
    title: str


# ------------------------------------------------------------------ helpers
def _safe_join(base: Path, *parts: str) -> Path:
    """brief §34: resolve the final path and verify it's still under
    `base` before returning it — defense-in-depth on top of the
    character-allowlist sanitization already applied to session_id
    (`_session_dir`) and the basename-only filenames (`_save_upload`).
    Neither of those should ever produce a path outside `base` as
    written, but this makes that property something the code CHECKS
    rather than something that's merely true by construction — so a
    future edit that loosens the sanitization trips this instead of
    silently reintroducing a traversal bug."""
    candidate = (base / Path(*parts)).resolve()
    base_resolved = base.resolve()
    try:
        candidate.relative_to(base_resolved)
    except ValueError:
        raise HTTPException(400, "Invalid path.")
    return candidate


def _session_dir(session_id: str) -> Path:
    safe = "".join(c for c in session_id if c.isalnum() or c in "-_")
    d = _safe_join(config.DATA_DIR, safe)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _save_upload(upload: UploadFile, session_id: str) -> Path:
    dest = _safe_join(_session_dir(session_id), Path(upload.filename).name)
    with dest.open("wb") as f:
        shutil.copyfileobj(upload.file, f)
    # brief §28: verify magic bytes match the extension for every upload,
    # regardless of which endpoint it came through — applied here, once,
    # rather than at each of the 4 call sites (ingest sync/async, audio
    # query, transcribe) so none of them can accidentally skip it.
    try:
        file_signature.verify_signature(str(dest), filename=upload.filename)
    except file_signature.SignatureMismatchError as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(400, str(exc))
    return dest


def _history_for(session_id: str) -> List[dict]:
    s = session_store.get_session(session_id)
    if not s:
        return []
    out = []
    for m in s.get("messages", []):
        if m.get("role") in ("user", "assistant") and m.get("text"):
            out.append({"role": m["role"], "content": m["text"]})
    return out

def _cache_key(route: str, user_id: str, payload: dict) -> str:
    # Bump this whenever retrieval/prompt/output semantics change; otherwise
    # Redis can return an older verbose answer for the same question.
    cache_payload = {
        "answer_pipeline_version": "2026-10-04-grounded-output-v5",
        "payload": payload,
    }
    blob = json.dumps(cache_payload, sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    return f"{route}:{user_id}:{digest}"


def _history_hash(history: List[dict]) -> str:
    """AUDIT_REPORT.md P1-4: the cache key previously used `len(history)`,
    so two different conversations of equal length collided onto the same
    cache entry. Hash the actual role+content sequence instead."""
    blob = json.dumps(history or [], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _resolve_provider(req_provider: Optional[str], user_id: str) -> str:
    """§51A.9: an explicit per-request provider always wins (unchanged
    behaviour); otherwise fall back to the user's persisted ACTIVE provider
    (new) instead of always defaulting straight to config.DEFAULT_PROVIDER,
    so switching providers via /api/llm/providers/{provider}/activate
    actually affects the next /api/query call."""
    return req_provider or active_provider.get_active(user_id)


def _resolve_model(req_model: Optional[str], provider: str, user_id: str) -> str:
    """Resolve the active model for this user and provider."""
    if req_model:
        return req_model.strip()
    if provider == "ollama":
        return config.LLM_MODEL
    custom = active_provider.get_active_model(user_id)
    if custom:
        return custom
    return _PROVIDER_META.get(provider, {}).get("model", "")


def _model_for_provider(provider: str) -> str:
    """Return the configured/default model for a provider."""
    return _PROVIDER_META.get(provider, {}).get("model", "")



def _check_chat_rate_limit(user_id: str) -> None:
    try:
        auth.check_custom_rate_limit(
            f"chat:{user_id}", config.CHAT_RATE_LIMIT_PER_MINUTE, 60,
        )
    except auth.RateLimitedError as exc:
        raise HTTPException(429, str(exc))


def _check_ingest_rate_limit(user_id: str) -> None:
    try:
        auth.check_custom_rate_limit(
            f"ingest:{user_id}", config.INGEST_RATE_LIMIT_PER_HOUR, 3600,
        )
    except auth.RateLimitedError as exc:
        raise HTTPException(429, str(exc))


def _flag(req_value: Optional[bool], config_value: bool) -> bool:
    """Resolve a per-request Phase 3 flag: explicit request value wins,
    otherwise fall back to the server-side config default."""
    return config_value if req_value is None else bool(req_value)


def _invalidate_user_cache(user_id: str) -> None:
    cache_store.delete_prefix(f"query:{user_id}:")
    cache_store.delete_prefix(f"extract:{user_id}:")
    cache_store.delete_prefix(f"summarize:{user_id}:")
    cache_store.delete_prefix(f"query_image:{user_id}:")
    cache_store.delete_prefix(f"query_audio:{user_id}:")
# ------------------------------------------------------------------ public routes
@app.get("/api/health")
def health():
    return {
        "status": "ok", "device": config.DEVICE, "llm_model": config.LLM_MODEL,
        "llm_available": llm_client.is_available(), "ocr_engine": config.OCR_ENGINE,
        "index": vector_store.stats(),
        "default_provider": config.DEFAULT_PROVIDER,
        "ollama": {
            "num_ctx": config.LLM_NUM_CTX,
            "num_predict": config.OLLAMA_NUM_PREDICT,
            "think": config.OLLAMA_THINK,
            "streaming": config.OLLAMA_STREAM,
            "keep_alive": config.OLLAMA_KEEP_ALIVE,
        },
    }


# brief §56/§57: liveness/readiness/dependencies, split apart on purpose.
# Liveness must stay cheap and near-unconditional (a load balancer kills
# and restarts a container that fails this — it should only fail if the
# process itself is broken, never because a downstream dependency is
# slow/down). Readiness answers "can this instance actually serve
# requests right now" — Ollama and storage are load-bearing, so their
# absence means NOT ready; Redis and cloud providers are not (the app
# already degrades gracefully without them — see cache.py/router.py), so
# their absence is reported but does not flip readiness to false.
@app.get("/health/live")
def health_live():
    return {"status": "alive"}


@app.get("/health/ready")
def health_ready():
    storage_ok = config.STORE_DIR.exists() and config.DATA_DIR.exists()
    ollama_ok = llm_client.is_available()
    ready = storage_ok and ollama_ok
    return {
        "status": "ready" if ready else "not_ready",
        "storage": "ok" if storage_ok else "unavailable",
        "ollama": "ok" if ollama_ok else "unavailable",
    }


@app.get("/health/dependencies")
def health_dependencies():
    """Full dependency breakdown — this is the one allowed to be slow/
    verbose; use /health/ready for load-balancer decisions, this one for
    a human or a dashboard checking what's actually up (brief §57's
    example: 'if a noncritical cloud provider is down, the service does
    not need to become unavailable' — reflected here as independent,
    non-fatal statuses rather than one boolean)."""
    return {
        "storage": "ok" if (config.STORE_DIR.exists() and config.DATA_DIR.exists()) else "unavailable",
        "vector_db": "ok" if vector_store.stats() is not None else "unavailable",
        "ollama": {
            "status": "ok" if llm_client.is_available() else "unavailable",
            "model": config.LLM_MODEL,
        },
        "redis_cache": "ok" if cache_store.is_available() else "unavailable (degrades to no-op, non-fatal)",
        "cloud_providers_configured": [
            name for name, meta in _PROVIDER_META.items() if not meta.get("local")
        ],
        "circuit_breakers": circuit_breaker.get_status(),
        "resources": resources.snapshot(),
    }


# ------------------------------------------------------------------ admin (brief §24/§127)
# Minimal RBAC: the first account created on a fresh install is admin
# (auth.py::create_user); every account after that is "user". These
# three endpoints cover the brief's authorization-matrix rows that this
# app didn't have any admin surface for at all before this pass — see
# COMPLETION_MATRIX.md for what's deliberately NOT built (a full admin
# dashboard UI, more granular permissions).
class SetRoleRequest(BaseModel):
    role: str


@app.get("/api/admin/users")
def admin_list_users(admin: dict = Depends(require_admin)):
    return {"users": auth.list_users()}


@app.post("/api/admin/users/{email}/role")
def admin_set_role(email: str, req: SetRoleRequest, admin: dict = Depends(require_admin)):
    try:
        result = auth.set_role(email, req.role)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    logging_utils.audit_log("admin_role_changed", user_id=admin["id"],
                            target_email=email, new_role=req.role)
    return result


@app.get("/api/admin/security-events")
def admin_security_events(limit: int = 100, offset: int = 0, admin: dict = Depends(require_admin)):
    """Paginated tail of the audit log (brief §24: 'Security logs: Admin
    only'; §132: paginated). `offset` counts back from the most recent
    entry (offset=0 = newest `limit` events, offset=limit = the `limit`
    events before those, etc.) — not a full query engine, this app's
    audit log is a flat JSONL file (logging_utils.py), which is the
    right amount of infrastructure for a local/desktop app's security log."""
    limit = max(1, min(limit, 1000))
    offset = max(0, offset)
    path = config.STORE_DIR / "audit.log"
    if not path.exists():
        return {"events": [], "total_lines_in_current_log": 0}
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    total = len(lines)
    # Newest-first pagination: reverse, slice, reverse back so page 0 is
    # the most recent `limit` events in their original (oldest-first) order.
    reversed_lines = list(reversed(lines))
    page = list(reversed(reversed_lines[offset:offset + limit]))
    events = []
    for line in page:
        try:
            events.append(json.loads(line))
        except Exception:
            continue
    return {"events": events, "total": total, "limit": limit, "offset": offset}


# ------------------------------------------------------------------ providers
_PROVIDER_META = {
    "ollama": {"label": "Local Qwen (Ollama)", "local": True, "model": config.LLM_MODEL},
    "gemini": {"label": "Google Gemini", "local": False, "model": config.GEMINI_MODEL},
    "openai": {"label": "OpenAI", "local": False, "model": config.OPENAI_MODEL},
    "claude": {"label": "Anthropic Claude", "local": False, "model": config.CLAUDE_MODEL},
    "groq": {"label": "Groq", "local": False, "model": config.GROQ_MODEL},
}


@app.get("/api/providers")
def list_providers(user: dict = Depends(get_user)):
    out = []
    for name in registry.names():
        meta = _PROVIDER_META.get(name, {"label": name, "local": False, "model": ""})
        prov = registry.get(name)
        out.append({
            "name": name,
            "label": meta["label"],
            "local": meta["local"],
            "model": meta["model"],
            "has_key": True if meta["local"] else keystore.has_key(user["id"], name),
            "available": prov.is_available() if meta["local"] else keystore.has_key(user["id"], name),
            "supports_images": prov.supports_images(),
            "supports_streaming": prov.supports_streaming(),
        })
    return {"providers": out, "default": config.DEFAULT_PROVIDER}


@app.post("/api/providers/key")
def set_provider_key(req: ProviderKeyRequest, user: dict = Depends(get_user)):
    if req.provider not in registry.names():
        raise HTTPException(400, f"Unknown provider: {req.provider}")
    if _PROVIDER_META.get(req.provider, {}).get("local"):
        raise HTTPException(400, "The local provider does not need an API key.")
    if not req.api_key.strip():
        raise HTTPException(400, "API key is empty.")
    keystore.set_key(user["id"], req.provider, req.api_key.strip())
    _invalidate_user_cache(user["id"])
    # brief §55: audit-log the ACTION, never the key itself.
    logging_utils.audit_log("provider_key_added", user_id=user["id"], provider=req.provider)
    return {"status": "ok", "provider": req.provider, "has_key": True}


@app.delete("/api/providers/key/{provider}")
def delete_provider_key(provider: str, user: dict = Depends(get_user)):
    if provider not in registry.names():
        raise HTTPException(400, f"Unknown provider: {provider}")
    keystore.delete_key(user["id"], provider)
    _invalidate_user_cache(user["id"])
    logging_utils.audit_log("provider_key_removed", user_id=user["id"], provider=provider)
    return {"status": "ok", "provider": provider, "has_key": False}


@app.post("/api/providers/validate")
def validate_provider_key(req: ProviderValidateRequest, user: dict = Depends(get_user)):
    if req.provider not in registry.names():
        raise HTTPException(400, f"Unknown provider: {req.provider}")
    valid = registry.get(req.provider).validate_api_key(req.api_key.strip())
    return {"provider": req.provider, "valid": valid}


@app.get("/api/providers/{provider}/models")
def list_provider_models(provider: str, user: dict = Depends(get_user)):
    """Fetch available models for a provider (e.g. Groq models via SDK if API key present, or fallback defaults)."""
    if provider not in registry.names():
        raise HTTPException(400, f"Unknown provider: {provider}")
    prov = registry.get(provider)
    if hasattr(prov, "get_model_list"):
        models = prov.get_model_list(user_id=user["id"])
    else:
        meta = _PROVIDER_META.get(provider, {})
        default_model = meta.get("model", "")
        models = [{"id": default_model, "name": default_model}] if default_model else []
    return {"provider": provider, "models": models}


# ------------------------------------------------------------------ active provider (brief §51A)
# Runtime local<->cloud switching. Validation (/api/providers/validate) and
# storing a key (/api/providers/key) are NOT the same thing as activation
# (§51A.13): entering/testing a key never changes which provider actually
# answers the next question. Only an explicit call to this endpoint does.
@app.get("/api/llm/active")
def get_active_provider(user: dict = Depends(get_user)):
    return active_provider.get_active_full(user["id"])


@app.post("/api/llm/providers/{provider}/activate")
def activate_provider(
    provider: str,
    req: Optional[ActivateProviderRequest] = None,
    user: dict = Depends(get_user),
):
    if provider not in registry.names():
        raise HTTPException(400, f"Unknown provider: {provider}")
    is_local = _PROVIDER_META.get(provider, {}).get("local", False)
    # §51A.6: a cloud provider can only be activated once a key is on file
    # for it — never activate purely because the frontend asked for it.
    if not is_local and not keystore.has_key(user["id"], provider):
        raise HTTPException(
            400,
            f"No API key is stored for {provider} yet. Add one with "
            f"POST /api/providers/key (optionally verified first via "
            f"POST /api/providers/validate) before activating this provider.",
        )
    chosen_model = req.model if req else None
    return active_provider.set_active(user["id"], provider, model=chosen_model)



@app.post("/api/auth/register")
def register(req: RegisterRequest, request: Request):
    # AUDIT_REPORT.md P0-3: brute-force / abuse protection on account
    # creation. Keyed by client IP; email is also checked implicitly since
    # create_user() rejects duplicates.
    client_ip = request.client.host if request.client else "unknown"
    try:
        auth.check_register_rate_limit(client_ip)
    except auth.RateLimitedError as exc:
        raise HTTPException(429, str(exc))
    try:
        user = auth.create_user(req.email, req.password)
    except ValueError as exc:
        logging_utils.audit_log("register_failed", ip=client_ip, email=req.email, reason=str(exc))
        raise HTTPException(400, str(exc))
    logging_utils.audit_log("register_success", user_id=user["id"], ip=client_ip)
    return {"token": auth.issue_token(user["id"]), "user": user}


@app.post("/api/auth/login")
def login(req: RegisterRequest, request: Request):
    # AUDIT_REPORT.md P0-3: login brute-force protection, keyed by
    # email+IP so one attacker can't lock out a legitimate user by
    # repeatedly failing their email from elsewhere, while still bounding
    # a single source's guessing rate.
    client_ip = request.client.host if request.client else "unknown"
    key = f"{(req.email or '').strip().lower()}:{client_ip}"
    try:
        auth.check_login_rate_limit(key)
    except auth.RateLimitedError as exc:
        logging_utils.audit_log("login_rate_limited", ip=client_ip, email=req.email)
        raise HTTPException(429, str(exc))
    user = auth.authenticate(req.email, req.password)
    if not user:
        # Never log the attempted password (brief §23/§54) — email + IP
        # is enough to spot a brute-force pattern without ever persisting
        # a credential.
        logging_utils.audit_log("login_failed", ip=client_ip, email=req.email)
        raise HTTPException(401, "Wrong email or password.")
    auth.clear_login_rate_limit(key)
    logging_utils.audit_log("login_success", user_id=user["id"], ip=client_ip)
    return {"token": auth.issue_token(user["id"]), "user": user}


@app.post("/api/auth/logout")
def logout(authorization: Optional[str] = Header(None), user: dict = Depends(get_user)):
    # AUDIT_REPORT.md P0-4: previously nothing could invalidate a token
    # before its natural TTL. This revokes only the presented token — other
    # active sessions/devices for the same user are untouched.
    token = authorization.split(" ", 1)[1]
    auth.revoke_token(token)
    logging_utils.audit_log("logout", user_id=user["id"])
    return {"status": "ok"}


@app.get("/api/auth/me")
def me(user: dict = Depends(get_user)):
    return {"user": user}


# ------------------------------------------------------------------ sessions
@app.post("/api/sessions")
def create_session(req: CreateSessionRequest, user: dict = Depends(get_user)):
    return session_store.create_session(user["id"], req.title)


@app.get("/api/sessions")
def list_sessions(user: dict = Depends(get_user),
                  limit: int = 50, offset: int = 0):
    """brief §132: never return an unbounded list. Paginates at the API
    layer — session_store.list_sessions() itself is left returning the
    full (already per-user-scoped) list, sliced here, since every caller
    of that function elsewhere in the codebase (e.g. the async-ingest
    refresh path) legitimately wants the whole thing."""
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    all_sessions = session_store.list_sessions(user["id"])
    page = all_sessions[offset:offset + limit]
    return {"sessions": page, "total": len(all_sessions), "limit": limit, "offset": offset}


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str, user: dict = Depends(get_user),
                message_limit: Optional[int] = None, message_offset: int = 0):
    """brief §132: message history is now paginate-able via
    `message_limit`/`message_offset`, without changing default behavior
    for existing callers — omitting both still returns every message,
    exactly as before this option existed."""
    _require_owner(session_id, user)
    s = session_store.get_session(session_id)
    s["files"] = vector_store.list_files(session_id=session_id, user_id=user["id"])
    total = len(s.get("messages", []))
    if message_limit is not None:
        limit = max(1, min(message_limit, 500))
        offset = max(0, message_offset)
        s["messages"] = s["messages"][offset:offset + limit]
        s["messages_total"] = total
        s["messages_limit"] = limit
        s["messages_offset"] = offset
    return s


@app.patch("/api/sessions/{session_id}")
def rename_session(session_id: str, req: RenameRequest, user: dict = Depends(get_user)):
    _require_owner(session_id, user)
    return session_store.rename_session(session_id, req.title)


@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str, user: dict = Depends(get_user)):
    _require_owner(session_id, user)
    removed = vector_store.delete_session(session_id)
    session_store.delete_session(session_id)
    safe = "".join(c for c in session_id if c.isalnum() or c in "-_")
    d = _safe_join(config.DATA_DIR, safe)
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
    _invalidate_user_cache(user["id"])
    logging_utils.audit_log("session_deleted", user_id=user["id"], session_id=session_id,
                            removed_chunks=removed)
    return {"status": "ok", "removed_chunks": removed}


def _transcribe_or_400(path: Path):
    """Wraps transcribe_audio() so a MAX_AUDIO_DURATION_SECONDS rejection
    (or any other audio-parsing ValueError) becomes a clean 400 instead of
    an unhandled 500 (brief §25: never expose internal exceptions)."""
    try:
        return transcribe_audio(str(path))
    except ValueError as exc:
        raise HTTPException(400, str(exc))


def _validate_uploads(files: List[UploadFile]) -> None:
    """AUDIT_REPORT.md P2-5 / brief §28: basic upload limits. Filename is
    already sanitized to just its basename in _save_upload(); this adds
    count/size bounds so a single request can't queue unbounded work."""
    if len(files) > config.MAX_FILES_PER_REQUEST:
        raise HTTPException(
            400, f"Too many files in one request (max {config.MAX_FILES_PER_REQUEST}).",
        )
    max_bytes = config.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    for up in files:
        size = getattr(up, "size", None)
        if size is not None and size > max_bytes:
            raise HTTPException(
                400, f"'{up.filename}' exceeds the {config.MAX_UPLOAD_SIZE_MB}MB upload limit.",
            )


# ------------------------------------------------------------------ ingestion
@app.post("/api/ingest")
async def ingest(session_id: str = Form(...), files: List[UploadFile] = File(...),
                 mode: str = Form("max_quality"), user: dict = Depends(get_user)):
    session_store.ensure_exists(session_id, user["id"])
    _require_owner(session_id, user)
    _check_ingest_rate_limit(user["id"])
    _validate_uploads(files)
    if mode not in ingest_mod.VALID_MODES:
        raise HTTPException(400, f"Unknown ingestion mode '{mode}'. Valid: {ingest_mod.VALID_MODES}")
    results = []
    for up in files:
        try:
            path = _save_upload(up, session_id)
            result = ingest_mod.ingest_file(str(path), session_id=session_id, user_id=user["id"], mode=mode)
            results.append(result)
            logging_utils.audit_log("file_uploaded", user_id=user["id"], session_id=session_id,
                                    filename=up.filename, chunks=result.get("chunks"),
                                    skipped_duplicate=result.get("skipped_duplicate"), mode=mode)
        except Exception as exc:
            results.append({"file": up.filename, "error": str(exc)})
            logging_utils.audit_log("file_upload_failed", user_id=user["id"], session_id=session_id,
                                    filename=up.filename, reason=str(exc))
        file_list = vector_store.list_files(session_id=session_id, user_id=user["id"])
    session_store.set_files(session_id, file_list)
    _invalidate_user_cache(user["id"])
    return {"status": "ok", "ingested": results, "files": file_list}


# --- Phase 3D: async ingestion (opt-in; the sync /api/ingest above is unchanged)
def _refresh_after_ingest(session_id: str, user_id: str) -> None:
    """Runs on the worker thread when an async job finishes: refresh the
    session's file list and drop stale query caches — same side effects the
    synchronous endpoint performs inline."""
    file_list = vector_store.list_files(session_id=session_id, user_id=user_id)
    session_store.set_files(session_id, file_list)
    _invalidate_user_cache(user_id)


@app.post("/api/ingest/async")
async def ingest_async(session_id: str = Form(...),
                       files: List[UploadFile] = File(...),
                       mode: str = Form("max_quality"),
                       user: dict = Depends(get_user)):
    session_store.ensure_exists(session_id, user["id"])
    _require_owner(session_id, user)
    _check_ingest_rate_limit(user["id"])
    _validate_uploads(files)
    if mode not in ingest_mod.VALID_MODES:
        raise HTTPException(400, f"Unknown ingestion mode '{mode}'. Valid: {ingest_mod.VALID_MODES}")
    # Save uploads synchronously (fast), then hand parsing+embedding to workers.
    paths: List[str] = []
    for up in files:
        path = _save_upload(up, session_id)
        paths.append(str(path))
    job_id = ingest_jobs.submit(
        paths, session_id=session_id, user_id=user["id"],
        on_complete=_refresh_after_ingest, mode=mode,
    )
    return {"status": "accepted", "job_id": job_id,
            "queued": [Path(p).name for p in paths]}


@app.get("/api/ingest/status/{job_id}")
def ingest_status(job_id: str, user: dict = Depends(get_user)):
    job = ingest_jobs.status(job_id)
    if job is None:
        raise HTTPException(404, "Job not found.")
    if job.get("user_id") != user["id"]:
        raise HTTPException(404, "Job not found.")
    return job


@app.get("/api/files")
def files(session_id: str, user: dict = Depends(get_user)):
    _require_owner(session_id, user)
    return {"files": vector_store.list_files(session_id=session_id, user_id=user["id"])}


@app.delete("/api/files/{filename}")
def delete_file(filename: str, session_id: str, user: dict = Depends(get_user)):
    _require_owner(session_id, user)
    removed = vector_store.delete_file(filename, session_id=session_id)
    p = _session_dir(session_id) / Path(filename).name
    if p.exists():
        p.unlink()
    file_list = vector_store.list_files(session_id=session_id, user_id=user["id"])
    session_store.set_files(session_id, file_list)
    _invalidate_user_cache(user["id"])
    logging_utils.audit_log("file_deleted", user_id=user["id"], session_id=session_id,
                            filename=filename, removed_chunks=removed)
    return {"status": "ok", "removed_chunks": removed, "files": file_list}


# ------------------------------------------------------------------ querying
@app.post("/api/query")
def query(req: QueryRequest, user: dict = Depends(get_user)):
    if not req.query.strip():
        raise HTTPException(400, "Query is empty.")
    session_store.ensure_exists(req.session_id, user["id"])
    _require_owner(req.session_id, user)
    _check_chat_rate_limit(user["id"])

    # Resolve Phase 3 feature flags (request overrides server config default).
    use_rewrite = _flag(req.rewrite, config.QUERY_REWRITE_ENABLED)
    use_hyde = _flag(req.hyde, config.HYDE_ENABLED)
    use_colbert = _flag(req.colbert, config.COLBERT_ENABLED)
    use_multihop = _flag(req.multihop, config.MULTIHOP_ENABLED)

    resolved_provider = _resolve_provider(req.provider, user["id"])
    resolved_model = _resolve_model(req.model, resolved_provider, user["id"])
    history = _history_for(req.session_id)

    payload = {
        "session_id": req.session_id,
        "query": req.query,
        "top_k": req.top_k,
        "modality": req.modality,
        "files": req.files or [],
        "route": "query",
        "provider": resolved_provider,
        "model": resolved_model,
        "history_hash": _history_hash(history),
        "phase3": [use_rewrite, use_hyde, use_colbert, use_multihop],
        "persist_messages": req.persist_messages,
    }
    key = _cache_key("query", user["id"], payload)
    cached = cache_store.get_json(key)
    if cached is not None:
        return cached

    # --- Multi-hop path: fully self-contained (its own retrieval + synthesis).
    start_total = time.perf_counter()
    if use_multihop:
        result = multihop_mod.multihop_answer(
            req.query, top_k=req.top_k, modality=req.modality,
            session_id=req.session_id, files=req.files, user_id=user["id"],
            history=history, provider=resolved_provider,
            session_dir=_session_dir(req.session_id),
        )
        retrieval_ms = (time.perf_counter() - start_total) * 1000 * 0.5
        gen_ms = (time.perf_counter() - start_total) * 1000 * 0.5
        hits = result.get("retrieved", [])
    else:
        # Optional query enhancement — only changes the SEARCH string; the
        # retrieval pipeline itself is unchanged and the ANSWER still uses the
        # user's original query.
        search_text = req.query
        if use_rewrite and config.QUERY_REWRITE_ENABLED:
            search_text = query_enhance.query_rewrite(
                search_text, history=history, provider=resolved_provider,
                user_id=user["id"])
        if use_hyde and config.HYDE_ENABLED:
            search_text = query_enhance.hyde_passage(
                search_text, provider=resolved_provider, user_id=user["id"])

        t_ret_start = time.perf_counter()
        hits = search.text_query(
            search_text,
            top_k=req.top_k,
            modality=req.modality,
            session_id=req.session_id,
            files=req.files,
            user_id=user["id"],
        )

        # Optional late-interaction rerank AFTER the existing pipeline.
        if use_colbert:
            hits = late_interaction.rerank(req.query, hits)
        retrieval_ms = (time.perf_counter() - t_ret_start) * 1000

        t_gen_start = time.perf_counter()
        result = answer_mod.answer_query(
            req.query, hits, history=history,
            provider=resolved_provider, user_id=user["id"],
            model=resolved_model,
            session_dir=_session_dir(req.session_id),
        )
        gen_ms = (time.perf_counter() - t_gen_start) * 1000
        result["retrieved"] = hits

    # Compute per-query evaluation and output terminal scorecard
    eval_metrics = query_eval.evaluate_query_and_log(
        query=req.query,
        answer=result.get("answer", ""),
        retrieved_hits=hits,
        provider=resolved_provider,
        model=resolved_model,
        retrieval_ms=retrieval_ms,
        generation_ms=gen_ms,
        used_llm=result.get("used_llm", False),
        session_id=req.session_id,
    )
    result["metrics"] = eval_metrics

    cache_store.set_json(key, result)

    if req.persist_messages:
        session_store.append_message(req.session_id, {"role": "user", "text": req.query})
        session_store.append_message(req.session_id, {
            "role": "assistant",
            "text": result["answer"],
            "citations": result["citations"],
            "usedLlm": result["used_llm"],
            "provider": resolved_provider,
            "model": resolved_model,
            "metrics": eval_metrics,
        })
    return result



@app.post("/api/query/stream")
def query_stream(req: QueryRequest, user: dict = Depends(get_user)):
    """Server-Sent Events variant of /api/query (brief §5/§51A.17): tokens
    are pushed to the client as they're generated instead of the caller
    waiting for the whole answer. Retrieval and citation-building reuse the
    exact same code path as the blocking endpoint
    (answer_mod.prepare_answer_context) — only the final generation call
    differs (streamed vs. blocking).

    Not cached: a partial cached JSON blob doesn't map cleanly onto a token
    stream, so /api/query remains the cached path and this one always
    generates fresh. Provider/history/citation semantics are otherwise
    identical to /api/query.
    """
    if not req.query.strip():
        raise HTTPException(400, "Query is empty.")
    session_store.ensure_exists(req.session_id, user["id"])
    _require_owner(req.session_id, user)
    _check_chat_rate_limit(user["id"])

    resolved_provider = _resolve_provider(req.provider, user["id"])
    resolved_model = _resolve_model(req.model, resolved_provider, user["id"])
    history = _history_for(req.session_id)

    search_text = req.query
    if _flag(req.rewrite, config.QUERY_REWRITE_ENABLED) and config.QUERY_REWRITE_ENABLED:
        search_text = query_enhance.query_rewrite(
            search_text, history=history, provider=resolved_provider, user_id=user["id"])
    if _flag(req.hyde, config.HYDE_ENABLED) and config.HYDE_ENABLED:
        search_text = query_enhance.hyde_passage(
            search_text, provider=resolved_provider, user_id=user["id"])

    t_ret_start = time.perf_counter()
    hits = search.text_query(
        search_text, top_k=req.top_k, modality=req.modality,
        session_id=req.session_id, files=req.files, user_id=user["id"],
    )
    if _flag(req.colbert, config.COLBERT_ENABLED):
        hits = late_interaction.rerank(req.query, hits)
    retrieval_ms = (time.perf_counter() - t_ret_start) * 1000

    ctx = answer_mod.prepare_answer_context(
        req.query, hits, history=history, session_dir=_session_dir(req.session_id),
    )

    def event_stream():
        if not hits:
            msg = prompt_templates.MISSING_CONTEXT_MESSAGE
            yield f"event: citations\ndata: {json.dumps([])}\n\n"
            yield f"event: delta\ndata: {json.dumps({'text': msg})}\n\n"
            yield f"event: done\ndata: {json.dumps({'used_llm': False, 'metrics': {}})}\n\n"
            return

        # Keep streaming behavior consistent with the blocking endpoint:
        # exact field questions must be answered from retrieved text without
        # invoking the LLM or exposing generated commentary.
        direct = answer_mod._direct_field_answer(
            req.query, hits, ctx["citations"]
        )
        if direct is not None:
            direct, direct_citations = answer_mod._restrict_citations_to_answer(
                direct, ctx["citations"]
            )
            # Send the exact extracted answer and only the source(s) it cites.
            # Uncited image chunks must not be rendered beside the answer.
            yield f"event: citations\ndata: {json.dumps(direct_citations)}\n\n"
            yield f"event: delta\ndata: {json.dumps({'text': direct})}\n\n"
            eval_metrics = query_eval.evaluate_query_and_log(
                query=req.query,
                answer=direct,
                retrieved_hits=hits,
                provider=resolved_provider,
                model=resolved_model,
                retrieval_ms=retrieval_ms,
                generation_ms=0.0,
                metrics={"streaming_enabled": False, "direct_extraction": True},
                used_llm=False,
                session_id=req.session_id,
            )
            session_store.append_message(req.session_id, {"role": "user", "text": req.query})
            session_store.append_message(req.session_id, {
                "role": "assistant",
                "text": direct,
                "citations": direct_citations,
                "usedLlm": False,
                "provider": resolved_provider,
                "model": resolved_model,
                "metrics": eval_metrics,
            })
            yield f"event: done\ndata: {json.dumps({'used_llm': False, 'metrics': eval_metrics})}\n\n"
            return

        full_text_parts: List[str] = []
        used_llm = True
        metrics: dict = {}
        t_gen_start = time.perf_counter()
        try:
            for chunk in provider_router.stream_generate(
                ctx["system"], ctx["user"], history=ctx["history"],
                provider=resolved_provider, user_id=user["id"],
                image_paths=ctx["image_paths"],
                model=resolved_model,
            ):
                if chunk.get("done"):
                    metrics = chunk.get("metrics", {}) or {}
                    break
                delta = chunk.get("delta", "")
                if delta:
                    full_text_parts.append(delta)
        except llm_client.LLMError as exc:
            used_llm = False
            top = hits[0]
            fallback = ("[LLM unavailable — showing top retrieved source]\n\n"
                        f"{top.get('snippet', '')} [1]")
            full_text_parts = [fallback]
            yield f"event: delta\ndata: {json.dumps({'text': fallback})}\n\n"

        gen_ms = (time.perf_counter() - t_gen_start) * 1000
        full_text = llm_client.clean_answer("".join(full_text_parts))
        full_text = answer_mod._enforce_clean_answer(
            answer_mod._finalize_answer(
                full_text, ctx["user"], resolved_provider, user["id"], resolved_model
            )
        )
        full_text, answer_citations = answer_mod._restrict_citations_to_answer(
            full_text, ctx["citations"]
        )
        yield f"event: citations\ndata: {json.dumps(answer_citations)}\n\n"
        if full_text:
            yield f"event: delta\ndata: {json.dumps({'text': full_text})}\n\n"

        # Compute per-query evaluation and print terminal scorecard
        eval_metrics = query_eval.evaluate_query_and_log(
            query=req.query,
            answer=full_text,
            retrieved_hits=hits,
            provider=resolved_provider,
            model=resolved_model,
            retrieval_ms=retrieval_ms,
            generation_ms=gen_ms,
            metrics=metrics,
            used_llm=used_llm,
            session_id=req.session_id,
        )

        session_store.append_message(req.session_id, {"role": "user", "text": req.query})
        session_store.append_message(req.session_id, {
            "role": "assistant",
            "text": full_text,
            "citations": answer_citations if used_llm else ctx["citations"],
            "usedLlm": used_llm,
            "provider": resolved_provider,
            "model": resolved_model,
            "metrics": eval_metrics,
        })
        yield f"event: done\ndata: {json.dumps({'used_llm': used_llm, 'metrics': metrics})}\n\n"

    return StreamingResponse(
        event_stream(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )



@app.post("/api/extract")
def extract(req: QueryRequest, user: dict = Depends(get_user)):
    if not req.query.strip():
        raise HTTPException(400, "Query is empty.")
    session_store.ensure_exists(req.session_id, user["id"])
    _require_owner(req.session_id, user)
    _check_chat_rate_limit(user["id"])

    resolved_provider = _resolve_provider(req.provider, user["id"])
    history = _history_for(req.session_id)
    payload = {
        "session_id": req.session_id,
        "query": req.query,
        "top_k": req.top_k,
        "modality": req.modality,
        "files": req.files or [],
        "route": "extract",
        "provider": resolved_provider,
        "model": _model_for_provider(resolved_provider),
        "history_hash": _history_hash(history),
    }
    key = _cache_key("extract", user["id"], payload)
    cached = cache_store.get_json(key)
    if cached is not None:
        return cached

    hits = search.text_query(
        req.query,
        top_k=req.top_k,
        modality=req.modality,
        session_id=req.session_id,
        files=req.files,
        user_id=user["id"],
    )
    result = answer_mod.extract_entities(
        req.query, hits, history=history,
        provider=resolved_provider, user_id=user["id"],
    )
    result["retrieved"] = hits

    cache_store.set_json(key, result)
    return result


@app.post("/api/summarize")
def summarize(req: QueryRequest, user: dict = Depends(get_user)):
    if not req.query.strip():
        raise HTTPException(400, "Query is empty.")
    session_store.ensure_exists(req.session_id, user["id"])
    _require_owner(req.session_id, user)
    _check_chat_rate_limit(user["id"])

    resolved_provider = _resolve_provider(req.provider, user["id"])
    history = _history_for(req.session_id)
    payload = {
        "session_id": req.session_id,
        "query": req.query,
        "top_k": req.top_k,
        "modality": req.modality,
        "files": req.files or [],
        "route": "summarize",
        "provider": resolved_provider,
        "model": _model_for_provider(resolved_provider),
        "history_hash": _history_hash(history),
    }
    key = _cache_key("summarize", user["id"], payload)
    cached = cache_store.get_json(key)
    if cached is not None:
        return cached

    hits = search.text_query(
        req.query,
        top_k=req.top_k,
        modality=req.modality,
        session_id=req.session_id,
        files=req.files,
        user_id=user["id"],
    )
    result = answer_mod.summarize_document(
        req.query, hits, history=history,
        provider=resolved_provider, user_id=user["id"],
    )
    result["retrieved"] = hits

    cache_store.set_json(key, result)
    return result

@app.post("/api/query/image")
async def query_image(session_id: str = Form(...), file: UploadFile = File(...),
                      top_k: int = Form(config.DEFAULT_TOP_K), files: Optional[str] = Form(None),
                      provider: Optional[str] = Form(None),
                      user: dict = Depends(get_user)):
    session_store.ensure_exists(session_id, user["id"])
    _require_owner(session_id, user)
    _check_chat_rate_limit(user["id"])

    resolved_provider = _resolve_provider(provider, user["id"])
    payload = {
        "session_id": session_id,
        "top_k": top_k,
        "files": (files or "").split(",") if files else [],
        "route": "query_image",
        "filename": file.filename,
        "provider": resolved_provider,
        "model": _model_for_provider(resolved_provider),
    }
    key = _cache_key("query_image", user["id"], payload)
    cached = cache_store.get_json(key)
    if cached is not None:
        return cached

    raw = await file.read()
    try:
        image = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception:
        raise HTTPException(400, "Could not read the uploaded image.")

    file_filter = [f for f in (files or "").split(",") if f] or None
    res = search.image_query(image, top_k=top_k, session_id=session_id,
                             files=file_filter, user_id=user["id"])
    hits = res["hits"]
    pseudo_q = (f"Describe and summarize the content related to this image "
                f"(caption: '{res['query_caption']}').")
    generated = answer_mod.answer_query(pseudo_q, hits, history=_history_for(session_id),
                                        provider=resolved_provider, user_id=user["id"],
                                        session_dir=_session_dir(session_id))

    session_store.append_message(session_id, {"role": "user", "text": f"[Image query: {file.filename}]"})
    session_store.append_message(session_id, {
        "role": "assistant", "text": generated["answer"], "citations": generated["citations"],
        "usedLlm": generated["used_llm"], "contextLabel": "Detected in image",
        "contextValue": res["query_caption"] or res["query_ocr"]})

    response = {
        "query_caption": res["query_caption"],
        "query_ocr": res["query_ocr"],
        "answer": generated["answer"],
        "citations": generated["citations"],
        "retrieved": hits,
        "used_llm": generated["used_llm"],
    }
    cache_store.set_json(key, response)
    return response


@app.post("/api/query/audio")
async def query_audio(session_id: str = Form(...), file: UploadFile = File(...),
                      top_k: int = Form(config.DEFAULT_TOP_K), files: Optional[str] = Form(None),
                      provider: Optional[str] = Form(None),
                      user: dict = Depends(get_user)):
    session_store.ensure_exists(session_id, user["id"])
    _require_owner(session_id, user)
    _check_chat_rate_limit(user["id"])

    resolved_provider = _resolve_provider(provider, user["id"])
    payload = {
        "session_id": session_id,
        "top_k": top_k,
        "files": (files or "").split(",") if files else [],
        "route": "query_audio",
        "filename": file.filename,
        "provider": resolved_provider,
        "model": _model_for_provider(resolved_provider),
    }
    key = _cache_key("query_audio", user["id"], payload)
    cached = cache_store.get_json(key)
    if cached is not None:
        return cached

    path = _save_upload(file, session_id)
    segments, lang = _transcribe_or_400(path)
    transcript = " ".join(s["text"] for s in segments).strip()
    if not transcript:
        raise HTTPException(400, "Could not transcribe any speech from the audio.")

    file_filter = [f for f in (files or "").split(",") if f] or None
    hits = search.text_query(transcript, top_k=top_k, modality="all",
                             session_id=session_id, files=file_filter, user_id=user["id"])
    generated = answer_mod.answer_query(transcript, hits, history=_history_for(session_id),
                                        provider=resolved_provider, user_id=user["id"],
                                        session_dir=_session_dir(session_id))

    session_store.append_message(session_id, {"role": "user", "text": f"[Audio query: {file.filename}]"})
    session_store.append_message(session_id, {
        "role": "assistant", "text": generated["answer"], "citations": generated["citations"],
        "usedLlm": generated["used_llm"], "contextLabel": "Transcript", "contextValue": transcript})

    response = {
        "transcript": transcript,
        "language": lang,
        "answer": generated["answer"],
        "citations": generated["citations"],
        "retrieved": hits,
        "used_llm": generated["used_llm"],
    }
    cache_store.set_json(key, response)
    return response


@app.post("/api/transcribe")
async def transcribe(session_id: str = Form(...), file: UploadFile = File(...),
                     user: dict = Depends(get_user)):
    session_store.ensure_exists(session_id, user["id"])
    _require_owner(session_id, user)
    path = _save_upload(file, session_id)
    segments, lang = _transcribe_or_400(path)
    return {"text": " ".join(s["text"] for s in segments).strip(), "language": lang}


# ------------------------------------------------------------------ source / media
@app.get("/api/source/{doc_id}")
def source(doc_id: str, user: dict = Depends(get_user)):
    item = vector_store.get_by_id(doc_id)
    if not item or item.get("metadata", {}).get("user_id") != user["id"]:
        raise HTTPException(404, "Source not found.")
    m = item["metadata"]
    sid, fname = m.get("session_id"), m.get("file")
    # Embedded images are saved under media_file; serving the parent PDF/DOCX
    # here makes the browser try to render a document as an image.
    serve_name = m.get("media_file") or fname
    media_url = f"/api/media/{sid}/{serve_name}" if sid else f"/api/media/{serve_name}"
    return {
        "id": item["id"], "file": fname, "modality": m.get("modality"),
        "source_type": m.get("source_type"), "page": m.get("page"),
        "chunk": m.get("chunk"), "chunk_total": m.get("chunk_total"),
        "start": m.get("start"), "end": m.get("end"), "timestamp": m.get("timestamp"),
        "full_text": item.get("document", ""), "media_url": media_url, "metadata": m,
    }


@app.get("/api/media/{session_id}/{filename}")
def media_scoped(session_id: str, filename: str, user: dict = Depends(get_user)):
    # Enforce authentication and ownership of the session.
    _require_owner(session_id, user)

    path = _session_dir(session_id) / Path(filename).name
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found.")

    return FileResponse(str(path))


# ------------------------------------------------------------------ danger zone
@app.post("/api/reset")
def reset(user: dict = Depends(get_user)):
    """Delete ALL of the current user's data (sessions + files + chunks)."""
    removed = 0
    for s in session_store.list_sessions(user["id"]):
        removed += vector_store.delete_session(s["id"])
        session_store.delete_session(s["id"])
        safe = "".join(c for c in s["id"] if c.isalnum() or c in "-_")
        d = _safe_join(config.DATA_DIR, safe)
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
    logging_utils.audit_log("account_data_reset", user_id=user["id"], removed_chunks=removed)

    _invalidate_user_cache(user["id"])
    return {"status": "ok", "removed_chunks": removed}


# ------------------------------------------------------------------ serve frontend
if config.STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(config.STATIC_DIR), html=True), name="static")
else:
    @app.get("/")
    def root():
        return {"service": "Multimodal Offline RAG", "docs": "/docs"}
