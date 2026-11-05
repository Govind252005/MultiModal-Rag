@echo off
REM ============================================================
REM  Run the whole app in PRODUCTION mode on Windows.
REM  Builds the frontend once, then the backend serves it.
REM  Open http://localhost:8000  (LAN: http://<your-ip>:8000)
REM ============================================================
cd /d "%~dp0\.."

echo [1/3] Building frontend (first run only)...
if not exist "frontend\dist" (
  pushd frontend
  call npm install || goto :err
  call npm run build || goto :err
  popd
)

echo [2/3] Preparing backend...
pushd backend
if not exist "venv" python -m venv venv
call venv\Scripts\activate.bat
echo   (make sure you've run SETUP once: torch + requirements + ollama pull)

echo [3/3] Starting server on http://localhost:8000 ...
uvicorn main:app --host 0.0.0.0 --port 8000
popd
goto :eof

:err
echo Build failed. See messages above.
pause
