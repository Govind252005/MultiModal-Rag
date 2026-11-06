#!/usr/bin/env bash
# Enterprise Production Startup Script (Linux/macOS)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ROOT_DIR"

echo "=========================================================="
echo "  Starting Enterprise Multimodal Offline RAG Platform      "
echo "=========================================================="

# 1. Check Ollama daemon
echo "[1/4] Checking Ollama daemon connectivity..."
if ! curl -s "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1; then
    echo "  -> Starting Ollama daemon in background..."
    ollama serve >/dev/null 2>&1 &
    sleep 3
fi
echo "  -> Ollama is online."

# 2. Check Frontend build
echo "[2/4] Checking frontend build..."
if [ ! -f "frontend/dist/index.html" ]; then
    echo "  -> Compiling frontend distribution bundle..."
    cd frontend && npm run build && cd ..
fi
echo "  -> Frontend dist bundle verified."

# 3. Check Python venv
echo "[3/4] Checking Python environment..."
PYTHON_BIN="backend/venv/bin/python"
if [ ! -f "$PYTHON_BIN" ]; then
    echo "Error: Python binary not found at $PYTHON_BIN. Please initialize venv."
    exit 1
fi

# 4. Start Uvicorn production server
echo "[4/4] Starting FastAPI backend on http://127.0.0.1:8000..."
nohup $PYTHON_BIN -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4 > storage/production.log 2>&1 &
echo $! > storage/rag_server.pid

echo ""
echo "✓ System successfully launched!"
echo "  Access URL:     http://localhost:8000"
echo "  Health Check:   http://localhost:8000/health/ready"
echo "  PID:            $(cat storage/rag_server.pid)"
echo "  To stop:        bash scripts/stop-production.sh"
echo ""
