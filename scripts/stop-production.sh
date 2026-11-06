#!/usr/bin/env bash
# Enterprise Production Shutdown Script (Linux/macOS)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ROOT_DIR"

echo "Gracefully stopping Enterprise Multimodal Offline RAG..."

PID_FILE="storage/rag_server.pid"
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
        echo "Terminating PID: $PID..."
        kill -15 "$PID" 2>/dev/null || kill -9 "$PID" 2>/dev/null
    fi
    rm -f "$PID_FILE"
fi

# Fallback: check if anything remains bound to 8000
if command -v fuser >/dev/null 2>&1; then
    fuser -k 8000/tcp 2>/dev/null || true
fi

echo "✓ System stopped successfully."
