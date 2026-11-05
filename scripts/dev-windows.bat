@echo off
REM ============================================================
REM  Run in DEV mode (hot reload): backend + Vite in 2 windows.
REM  Frontend: http://localhost:5173   Backend: http://localhost:8000
REM ============================================================
cd /d "%~dp0\.."
start "RAG Backend"  cmd /k "cd backend && call venv\Scripts\activate.bat && uvicorn main:app --reload --host 0.0.0.0 --port 8000"
start "RAG Frontend" cmd /k "cd frontend && npm run dev -- --host"
echo Two windows launched. Close them to stop.
