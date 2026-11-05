#!/usr/bin/env bash
# ===================================================================
#  All-in-one container entrypoint.
#
#  Starts the local Ollama LLM server in the background, waits until
#  it answers, makes sure the Qwen model is present (it is baked into
#  the image at build time, but we re-pull if a mounted volume hid it),
#  then launches the FastAPI backend, which also serves the compiled
#  React UI on the same port.
#
#  This is ADDITIVE glue for containerized "as-a-service" deployment.
#  It does not modify the app, its config defaults, or the retrieval
#  pipeline. Everything runs on ONE port ($RAG_PORT, default 8000).
# ===================================================================
set -euo pipefail

RAG_HOST="${RAG_HOST:-0.0.0.0}"
RAG_PORT="${RAG_PORT:-8000}"
OLLAMA_HOST="${OLLAMA_HOST:-http://127.0.0.1:11434}"
LLM_MODEL="${LLM_MODEL:-qwen3:8b}"
# Where Ollama serves/listens inside the container.
export OLLAMA_HOST_BIND="${OLLAMA_HOST_BIND:-127.0.0.1:11434}"

log() { echo "[entrypoint] $*"; }

# --------------------------------------------------------------- Ollama
log "starting Ollama server (OLLAMA_HOST=$OLLAMA_HOST_BIND) ..."
OLLAMA_HOST="$OLLAMA_HOST_BIND" ollama serve &
OLLAMA_PID=$!

# Wait for the Ollama API to answer /api/tags.
log "waiting for Ollama to become ready ..."
for i in $(seq 1 60); do
  if curl -sf "http://${OLLAMA_HOST_BIND}/api/tags" >/dev/null 2>&1; then
    log "Ollama is ready."
    break
  fi
  if ! kill -0 "$OLLAMA_PID" 2>/dev/null; then
    log "ERROR: Ollama process exited during startup."
    exit 1
  fi
  sleep 1
  if [ "$i" -eq 60 ]; then
    log "ERROR: Ollama did not become ready within 60s."
    exit 1
  fi
done

# Ensure the model exists. It is baked at build time, but a volume mounted
# over /root/.ollama (or a --pull skip) can hide it; re-pull if missing.
if ! OLLAMA_HOST="$OLLAMA_HOST_BIND" ollama list 2>/dev/null | grep -q "${LLM_MODEL%%:*}"; then
  log "model '$LLM_MODEL' not found in this container — pulling (needs network) ..."
  OLLAMA_HOST="$OLLAMA_HOST_BIND" ollama pull "$LLM_MODEL" || \
    log "WARN: pull failed. Local answers won't work until '$LLM_MODEL' is available."
else
  log "model '$LLM_MODEL' present."
fi

# Point the backend at the in-container Ollama.
export OLLAMA_HOST="http://${OLLAMA_HOST_BIND}"
export LLM_MODEL

# Graceful shutdown: stop Ollama when the backend exits.
cleanup() {
  log "shutting down ..."
  kill "$OLLAMA_PID" 2>/dev/null || true
  wait "$OLLAMA_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# --------------------------------------------------------------- Backend
# The backend serves the API and, when config.STATIC_DIR exists, the UI too.
# Run from /app so `import config` / `import main` resolve like a normal run.
log "starting backend on ${RAG_HOST}:${RAG_PORT} (serves API + UI) ..."
cd /app
exec uvicorn main:app --host "$RAG_HOST" --port "$RAG_PORT" --log-level info
