@echo off
title Multimodal Offline RAG Server (Port 8000)
cd /d "%~dp0\.."
set PYTHONUNBUFFERED=1
set PYTHONIOENCODING=utf-8
echo ============================================================
echo   Enterprise Multimodal Offline RAG Production Server
echo   Port: 8000 -- Active Model: qwen2.5:7b-instruct (CUDA)
echo ============================================================
backend\venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 1
echo.
echo [SERVER TERMINATED] The FastAPI server process has stopped.
pause

