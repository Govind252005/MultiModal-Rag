"""
Central configuration for the Multimodal Offline RAG backend.

Tune this ONE file (or set the matching env vars). All models are open-source
and run fully OFFLINE after the first download.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import torch

# ------------------------------------------------------------------ Paths
BASE_DIR = Path(__file__).resolve().parent

# Where writable data lives. In normal (source) runs this stays inside the
# backend folder, so nothing changes for developers. When packaged as a
# PyInstaller exe (sys.frozen), the bundle is read-only, so we redirect writable
# data to a per-user folder. Either case can be overridden with RAG_DATA_HOME.
_FROZEN = getattr(sys, "frozen", False)
_data_home_env = os.getenv("RAG_DATA_HOME")
if _data_home_env:
    DATA_HOME = Path(_data_home_env).expanduser().resolve()
elif _FROZEN:
    _appdata = os.getenv("LOCALAPPDATA") or os.getenv("XDG_DATA_HOME") or str(Path.home())
    DATA_HOME = Path(_appdata) / "MultimodalRag"
else:
    DATA_HOME = BASE_DIR

DATA_DIR = DATA_HOME / "data"
STORE_DIR = DATA_HOME / "storage"
CHROMA_DIR = STORE_DIR / "chroma"
SESSIONS_DIR = STORE_DIR / "sessions"
USERS_FILE = STORE_DIR / "users.json"          # registered accounts
SECRET_FILE = STORE_DIR / "secret.key"         # HMAC signing key for tokens

# Bundled frontend. When frozen, PyInstaller unpacks data files under _MEIPASS;
# in source runs it's the sibling frontend/dist build.
if _FROZEN:
    _bundle_root = Path(getattr(sys, "_MEIPASS", BASE_DIR))
    STATIC_DIR = _bundle_root / "frontend_dist"
else:
    STATIC_DIR = BASE_DIR.parent / "frontend" / "dist"

for _p in (DATA_DIR, STORE_DIR, CHROMA_DIR, SESSIONS_DIR):
    _p.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------ Device
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# ------------------------------------------------------------------ Embeddings
TEXT_EMBED_MODEL = os.getenv(
    "TEXT_EMBED_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
TEXT_EMBED_DIM = 384
CLIP_MODEL = "clip-ViT-B-32"
CLIP_EMBED_DIM = 512
EMBED_BATCH_SIZE = int(os.getenv("EMBED_BATCH_SIZE", "64"))
WARMUP_ON_STARTUP = os.getenv("WARMUP_ON_STARTUP", "1") == "1"

# ------------------------------------------------------------------ Image / OCR
BLIP_CAPTION_MODEL = "Salesforce/blip-image-captioning-base"

# OCR Engine
OCR_ENGINE = os.getenv("OCR_ENGINE", "paddleocr")

# PaddleOCR Configuration
PADDLEOCR_LANG = os.getenv("PADDLEOCR_LANG", "en")  # en, ch, latin, etc.
PADDLEOCR_USE_GPU = DEVICE == "cuda"

# Optional future settings
PADDLEOCR_ENABLE_MKLDNN = DEVICE == "cpu"
PADDLEOCR_CPU_THREADS = int(os.getenv("PADDLEOCR_CPU_THREADS", "8"))

# Tesseract fallback (optional)
TESSERACT_CMD = os.getenv(
    "TESSERACT_CMD",
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.name == "nt"
    else "tesseract",
)

OCR_LANG = os.getenv("OCR_LANG", "eng")
OCR_CONFIG = os.getenv("OCR_CONFIG", "--oem 1 --psm 6")

# OCR preprocessing
OCR_MIN_WIDTH = 1400

# OCR chunking
OCR_CHUNK_WORDS = 120

# ------------------------------------------------------------------ Audio
# ------------------------------------------------------------------ Audio
# Use "medium.en" if you mostly speak English.
# Use "medium" if you want multilingual speech.
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "medium")
WHISPER_COMPUTE_TYPE = "float16" if DEVICE == "cuda" else "int8"
WHISPER_LANGUAGE = os.getenv("WHISPER_LANGUAGE", "en")  # change to hi, etc. if needed
WHISPER_TASK = os.getenv("WHISPER_TASK", "transcribe")
WHISPER_BEAM_SIZE = int(os.getenv("WHISPER_BEAM_SIZE", "8"))
WHISPER_VAD_FILTER = os.getenv("WHISPER_VAD_FILTER", "1") == "1"
WHISPER_CONDITION_ON_PREVIOUS_TEXT = os.getenv("WHISPER_CONDITION_ON_PREVIOUS_TEXT", "0") == "1"
WHISPER_INITIAL_PROMPT = os.getenv("WHISPER_INITIAL_PROMPT", "")
# Smaller windows = more precise "play from HH:MM:SS" timecodes.
AUDIO_CHUNK_SECONDS = int(os.getenv("AUDIO_CHUNK_SECONDS", "12"))

# ------------------------------------------------------------------ Chunking
CHUNK_SIZE_WORDS = 220
CHUNK_OVERLAP_WORDS = 40

# brief §45/§46: every chunk records what produced it, so (a) re-ingesting
# unchanged content can be skipped entirely (idempotent ingestion) and
# (b) if any of these ever change, old chunks are recognizably stale
# instead of silently mixed with new ones. Bump INGESTION_PIPELINE_VERSION
# whenever parsing/chunking logic changes materially enough that old
# chunks should be considered outdated even though the source file didn't.
INGESTION_PIPELINE_VERSION = os.getenv("INGESTION_PIPELINE_VERSION", "2")
# ------------------------------------------------------------------ Chunking strategy
CHUNKING_STRATEGY = os.getenv("CHUNKING_STRATEGY", "semantic")  # semantic | word
SEMANTIC_MIN_WORDS = int(os.getenv("SEMANTIC_MIN_WORDS", "80"))
SEMANTIC_SIM_THRESHOLD = float(os.getenv("SEMANTIC_SIM_THRESHOLD", "0.58"))
# ------------------------------------------------------------------ Retrieval
# ------------------------------------------------------------------ Retrieval fusion
DEFAULT_TOP_K = int(os.getenv("DEFAULT_TOP_K", "10"))
DENSE_CANDIDATES = int(os.getenv("DENSE_CANDIDATES", "40"))
BM25_CANDIDATES = int(os.getenv("BM25_CANDIDATES", "40"))
FUSION_RRF_K = int(os.getenv("FUSION_RRF_K", "60"))
TEXT_WEIGHT = 1.0
CLIP_WEIGHT = 1.0
# ------------------------------------------------------------------ Reranking
RERANK_ENABLED = os.getenv("RERANK_ENABLED", "1") == "1"
RERANK_MODEL = os.getenv("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L6-v2")
# Use BAAI/bge-reranker-large for higher quality, slower throughput:
# RERANK_MODEL = "BAAI/bge-reranker-large"
RERANK_BATCH_SIZE = int(os.getenv("RERANK_BATCH_SIZE", "16"))

# ------------------------------------------------------------------ LLM (Ollama)
# Local-inference target (AUDIT_REPORT.md / transformation brief §4-5):
# qwen3:4b, thinking disabled, bounded context + output, streaming enabled.
# Every one of these is now env-overridable — nothing here is hardcoded.
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen3:4b")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.0"))
# Keep the local prompt budget large enough for retrieved evidence while
# avoiding unnecessary prompt processing for short grounded answers.
LLM_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "3072"))
# Strict RAG answers should be short; callers can raise this for long answers.
OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "384"))
# Qwen3 supports an explicit "thinking" mode; keep it off by default for
# fast, low-latency RAG answers rather than relying on the model's default.
OLLAMA_THINK = os.getenv("OLLAMA_THINK", "0") == "1"
OLLAMA_STREAM = os.getenv("OLLAMA_STREAM", "1") == "1"
OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "30m")
# Per-request timeout for a local Ollama call (brief §96: every external
# operation must have a timeout).
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "120"))
HISTORY_TURNS = int(os.getenv("HISTORY_TURNS", "4"))
# brief §13: context builder token budget. Enforced in
# generation/prompt_templates.py::truncate_hits_to_budget — applied once,
# before both citations and the prompt are built, so what's cited always
# matches what the LLM actually saw.
MAX_CONTEXT_TOKENS = int(os.getenv("MAX_CONTEXT_TOKENS", "2500"))

# ------------------------------------------------------------------ Redis cache
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "600"))
CACHE_ENABLED = os.getenv("CACHE_ENABLED", "1") == "1"
# ------------------------------------------------------------------ CORS (AUDIT_REPORT.md P0-1)
# Comma-separated allowlist. Defaults to the app's own bundled-frontend
# origins for local/desktop use; production deployments MUST set this
# explicitly (brief §26 — never allow_origins=["*"] in production).
_default_origins = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080,http://127.0.0.1:8080"
ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv("ALLOWED_ORIGINS", _default_origins).split(",") if o.strip()
]
# Explicit opt-in escape hatch for local dev only — never set this in prod.
CORS_ALLOW_ALL = os.getenv("CORS_ALLOW_ALL", "0") == "1"
# Security headers (brief §124). HSTS is opt-in — see main.py's
# _security_headers_middleware for why it must never be sent by default
# on a plain-HTTP deployment.
FORCE_HSTS = os.getenv("FORCE_HSTS", "0") == "1"

# ------------------------------------------------------------------ Auth
TOKEN_TTL_HOURS = int(os.getenv("TOKEN_TTL_HOURS", str(24 * 7)))  # 1 week
PASSWORD_MIN_LENGTH = int(os.getenv("PASSWORD_MIN_LENGTH", "8"))
# Login/registration brute-force protection (AUDIT_REPORT.md P0-3).
LOGIN_MAX_ATTEMPTS = int(os.getenv("LOGIN_MAX_ATTEMPTS", "5"))
LOGIN_WINDOW_SECONDS = int(os.getenv("LOGIN_WINDOW_SECONDS", "60"))
LOGIN_LOCKOUT_SECONDS = int(os.getenv("LOGIN_LOCKOUT_SECONDS", "300"))
REGISTER_MAX_ATTEMPTS = int(os.getenv("REGISTER_MAX_ATTEMPTS", "10"))
REGISTER_WINDOW_SECONDS = int(os.getenv("REGISTER_WINDOW_SECONDS", "3600"))
REGISTER_LOCKOUT_SECONDS = int(os.getenv("REGISTER_LOCKOUT_SECONDS", "3600"))
# Chat/query rate limiting (brief §27). Simple in-process token-bucket-ish
# fixed window; swap for a Redis-backed limiter behind a load balancer with
# multiple backend processes.
CHAT_RATE_LIMIT_PER_MINUTE = int(os.getenv("CHAT_RATE_LIMIT_PER_MINUTE", "30"))
INGEST_RATE_LIMIT_PER_HOUR = int(os.getenv("INGEST_RATE_LIMIT_PER_HOUR", "60"))

# ------------------------------------------------------------------ Uploads (brief §28)
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "200"))
MAX_FILES_PER_REQUEST = int(os.getenv("MAX_FILES_PER_REQUEST", "20"))

# ------------------------------------------------------------------ Per-modality resource limits
# (transformation brief §28/§30/§31/§32 — AUDIT_REPORT.md follow-up: these
# were entirely absent before. Pillow's own default MAX_IMAGE_PIXELS
# already blocks the most extreme decompression bombs, but there was no
# app-level PDF page cap or audio duration cap at all — those are the real
# gaps this section closes.)
MAX_IMAGE_PIXELS = int(os.getenv("MAX_IMAGE_PIXELS", str(64_000_000)))  # ~64MP
MAX_IMAGE_WIDTH = int(os.getenv("MAX_IMAGE_WIDTH", "12000"))
MAX_IMAGE_HEIGHT = int(os.getenv("MAX_IMAGE_HEIGHT", "12000"))
MAX_PDF_PAGES = int(os.getenv("MAX_PDF_PAGES", "500"))
MAX_PDF_FILE_SIZE_MB = int(os.getenv("MAX_PDF_FILE_SIZE_MB", "200"))
MAX_AUDIO_DURATION_SECONDS = int(os.getenv("MAX_AUDIO_DURATION_SECONDS", str(4 * 3600)))  # 4h
MAX_EXTRACTED_IMAGES_PER_DOC = int(os.getenv("MAX_EXTRACTED_IMAGES_PER_DOC", "40"))

# ------------------------------------------------------------------ Data retention (brief §88)
# 0 = never auto-delete (the safe default for a local/desktop app — see
# docs/data-retention.md). Only scripts/maintenance/cleanup.py reads
# these; nothing in the running app deletes data on a timer.
SESSION_RETENTION_DAYS = int(os.getenv("SESSION_RETENTION_DAYS", "0"))
EVAL_REPORT_RETENTION_DAYS = int(os.getenv("EVAL_REPORT_RETENTION_DAYS", "0"))

# ------------------------------------------------------------------ Chroma
TEXT_COLLECTION = "rag_text"
IMAGE_COLLECTION = "rag_image"

# ------------------------------------------------------------------ LLM providers (hybrid local + cloud)
# The RETRIEVAL pipeline never changes with the provider — only the final
# answer-generation model does. "ollama" is the default, fully-offline local
# model (Qwen). Cloud providers require a per-user API key (encrypted at rest).
DEFAULT_PROVIDER = os.getenv("DEFAULT_PROVIDER", "ollama")

# Per-user encrypted API keys live here; the Fernet key that encrypts them
# lives in KEYS_SECRET_FILE. Both stay on the local machine.
PROVIDER_KEYS_FILE = STORE_DIR / "provider_keys.json"
KEYS_SECRET_FILE = STORE_DIR / "keys.secret"

# Default cloud model per provider (each is overridable per request/env).
# gemini-2.0-flash is current and broadly available; gemini-1.5-flash is
# retired for newer projects, so it is a poor default.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-latest")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

# Shared generation knobs for cloud providers (local Ollama keeps its own).
CLOUD_TEMPERATURE = float(os.getenv("CLOUD_TEMPERATURE", "0.1"))
CLOUD_MAX_TOKENS = int(os.getenv("CLOUD_MAX_TOKENS", "2048"))
# Network timeout (seconds) for a cloud generation / validation call.
CLOUD_TIMEOUT = int(os.getenv("CLOUD_TIMEOUT", "60"))
# On cloud failure, fall back to the local Ollama model — but ONLY for
# error classes where that's actually safe (rate limit, timeout, transient
# provider outage). Invalid API key / invalid request never fail over,
# regardless of this flag (AUDIT_REPORT.md P0-5; brief §52 / §51A.21: don't
# auto-fallback on every cloud failure, and don't hide an explicit user
# provider choice behind a silent local answer).
PROVIDER_FAILOVER_TO_LOCAL = os.getenv("PROVIDER_FAILOVER_TO_LOCAL", "1") == "1"
# Max attempts (including the first) for a "retryable" cloud error class
# (rate_limited / network_error / provider_unavailable) before giving up or
# failing over. Kept small and configurable — never an endless retry chain.
PROVIDER_RETRY_MAX_ATTEMPTS = int(os.getenv("PROVIDER_RETRY_MAX_ATTEMPTS", "2"))
# Exponential backoff + jitter between same-provider retries (brief §97).
PROVIDER_RETRY_BASE_DELAY_SECONDS = float(os.getenv("PROVIDER_RETRY_BASE_DELAY_SECONDS", "0.5"))
PROVIDER_RETRY_MAX_DELAY_SECONDS = float(os.getenv("PROVIDER_RETRY_MAX_DELAY_SECONDS", "8"))
# Circuit breaker (brief §98) — scoped ONLY to provider-health failures
# (5xx / network errors), never to one user's bad key or rate limit. See
# generation/providers/circuit_breaker.py's module docstring for why.
CIRCUIT_BREAKER_FAILURE_THRESHOLD = int(os.getenv("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "5"))
CIRCUIT_BREAKER_COOLDOWN_SECONDS = int(os.getenv("CIRCUIT_BREAKER_COOLDOWN_SECONDS", "60"))

# ------------------------------------------------------------------ Phase 3 (advanced retrieval / reasoning)
# Every flag below defaults OFF so the existing retrieval + answer path is
# unchanged. Turn them on per-request (API flags) or globally (env vars).
#
# Query rewriting: use the LLM to turn a context-dependent question
# ("and its price?") into a standalone search query before retrieval.
QUERY_REWRITE_ENABLED = os.getenv("QUERY_REWRITE_ENABLED", "0") == "1"
# HyDE: generate a short hypothetical answer and embed THAT for dense search.
HYDE_ENABLED = os.getenv("HYDE_ENABLED", "0") == "1"
# Multi-hop: decompose a complex question into sub-questions, retrieve per
# sub-question, then synthesize one cited answer.
MULTIHOP_ENABLED = os.getenv("MULTIHOP_ENABLED", "0") == "1"
MULTIHOP_MAX_SUBQUESTIONS = int(os.getenv("MULTIHOP_MAX_SUBQUESTIONS", "4"))
# ColBERT / late-interaction rerank: optional post-retrieval reranker applied
# AFTER the existing cross-encoder. Requires an extra model download; if the
# model or deps are unavailable it no-ops (returns hits unchanged).
COLBERT_ENABLED = os.getenv("COLBERT_ENABLED", "0") == "1"
COLBERT_MODEL = os.getenv("COLBERT_MODEL", "colbert-ir/colbertv2.0")
COLBERT_TOP_N = int(os.getenv("COLBERT_TOP_N", "5"))

# ------------------------------------------------------------------ Async ingestion
# When enabled the /api/ingest/async endpoint accepts files and processes them
# on a background worker pool; poll /api/ingest/status/{job_id} for progress.
# The original synchronous /api/ingest is unaffected.
INGEST_ASYNC_WORKERS = int(os.getenv("INGEST_ASYNC_WORKERS", "2"))
