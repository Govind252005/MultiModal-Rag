@echo off
REM ===================================================================
REM  Build MultimodalRag.exe  (Windows)
REM  Run this from the PROJECT ROOT in a terminal where your backend
REM  venv Python is available. See BUILD_EXE_GUIDE.md for full details.
REM ===================================================================
setlocal enabledelayedexpansion

echo ============================================================
echo   Building MultimodalRag.exe
echo ============================================================

REM --- 0. Sanity: must run from project root (has backend\ + frontend\)
if not exist "backend\launcher.py" (
  echo [error] Run this from the project root ^(the folder with backend\ and frontend\^).
  exit /b 1
)

REM --- 1. Build the frontend so it can be bundled into the exe
echo.
echo [1/4] Building frontend (npm run build)...
pushd frontend
if not exist "node_modules" (
  call npm install || (echo [error] npm install failed & popd & exit /b 1)
)
call npm run build || (echo [error] npm run build failed & popd & exit /b 1)
popd
if not exist "frontend\dist\index.html" (
  echo [error] frontend\dist was not produced. Aborting.
  exit /b 1
)

REM --- 2. Make sure PyInstaller is installed in this Python env
echo.
echo [2/4] Ensuring PyInstaller is installed...
python -m pip show pyinstaller >nul 2>&1 || python -m pip install pyinstaller

REM --- 3. Clean previous build artifacts
echo.
echo [3/4] Cleaning previous build/dist...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

REM --- 4. Run PyInstaller against the spec
echo.
echo [4/4] Running PyInstaller (this takes several minutes)...
pyinstaller MultimodalRag.spec --noconfirm --clean || (echo [error] PyInstaller build failed & exit /b 1)

echo.
echo ============================================================
echo   DONE.
echo   Your app is at:  dist\MultimodalRag\MultimodalRag.exe
echo   Double-click it (or run from a terminal to see logs).
echo   NOTE: Ollama must be installed + the model pulled:
echo         ollama pull qwen3:8b
echo ============================================================
endlocal
