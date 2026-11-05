#!/usr/bin/env bash
# Production run on macOS/Linux: build frontend, backend serves it.
set -e
cd "$(dirname "$0")/.."
if [ ! -d frontend/dist ]; then
  (cd frontend && npm install && npm run build)
fi
cd backend
[ -d venv ] || python3 -m venv venv
source venv/bin/activate
echo "Starting on http://localhost:8000  (LAN: http://$(hostname -I 2>/dev/null | awk '{print $1}'):8000)"
uvicorn main:app --host 0.0.0.0 --port 8000
