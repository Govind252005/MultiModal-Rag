@echo off
REM ===================================================================
REM  Build Multimodal RAG Windows Installer (MultimodalRagSetup.exe)
REM  Orchestrates:
REM    1. Frontend build (npm run build)
REM    2. PyInstaller payload compilation (dist\MultimodalRag)
REM    3. Inno Setup packaging (release\MultimodalRagSetup.exe)
REM ===================================================================
setlocal enabledelayedexpansion

echo ============================================================
echo   Building Multimodal RAG Setup Installer (.exe)
echo ============================================================

REM --- 0. Verify working directory
if not exist "Installer\installer.iss" (
  echo [ERROR] Must run from project root (containing Installer\ and backend\).
  exit /b 1
)

REM --- 1. Find Inno Setup compiler (ISCC.exe)
set "ISCC_EXE="

where ISCC.exe >nul 2>&1
if !errorlevel! equ 0 (
  set "ISCC_EXE=ISCC.exe"
)

if not defined ISCC_EXE if exist "%LOCALAPPDATA%\Programs\Antigravity IDE\resources\app\node_modules\innosetup\bin\ISCC.exe" set "ISCC_EXE=%LOCALAPPDATA%\Programs\Antigravity IDE\resources\app\node_modules\innosetup\bin\ISCC.exe"
if not defined ISCC_EXE if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC_EXE=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC_EXE if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC_EXE=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC_EXE if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC_EXE=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"

if not defined ISCC_EXE (
  echo [ERROR] Inno Setup compiler (ISCC.exe) was not found.
  echo Please install Inno Setup 6 from https://jrsoftware.org/isinfo.php
  exit /b 1
)

echo [INFO] Using Inno Setup compiler: "!ISCC_EXE!"

REM --- 2. Check if PyInstaller payload already exists or needs rebuild
if not exist "dist\MultimodalRag\MultimodalRag.exe" (
  echo.
  echo [INFO] PyInstaller payload missing. Running build-exe-windows.bat...
  call build-exe-windows.bat
  if !errorlevel! neq 0 (
    echo [ERROR] Failed to compile PyInstaller payload.
    exit /b 1
  )
) else (
  echo [INFO] Found existing application payload at dist\MultimodalRag\
)

REM --- 3. Ensure release directory exists
if not exist "release" mkdir "release"

REM --- 4. Compile Inno Setup installer
echo.
echo [INFO] Compiling installer with Inno Setup (this may take several minutes)...
pushd Installer
"!ISCC_EXE!" installer.iss
set "BUILD_STATUS=!errorlevel!"
popd

if !BUILD_STATUS! neq 0 (
  echo [ERROR] Inno Setup compilation failed with code !BUILD_STATUS!.
  exit /b !BUILD_STATUS!
)

echo.
echo ============================================================
echo   INSTALLER CREATED SUCCESSFULLY!
echo ============================================================
echo   Output: release\MultimodalRagSetup_V2.exe
echo.
echo   You can now distribute MultimodalRagSetup.exe to anyone.
echo   When launched, it will:
echo     1. Check system hardware (RAM, GPU/CPU, disk)
echo     2. Install Multimodal RAG into Program Files
echo     3. Detect or install Ollama automatically
echo     4. Pull the default model (qwen2.5:7b-instruct)
echo     5. Create Desktop and Start Menu shortcuts
echo     6. Configure Windows Firewall
echo ============================================================
endlocal

