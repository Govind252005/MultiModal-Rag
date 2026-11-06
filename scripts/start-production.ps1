# Enterprise Production Startup Script (Windows PowerShell)
$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
Set-Location $RootDir

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Starting Enterprise Multimodal Offline RAG Platform      " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Verify Ollama inference service is reachable
Write-Host "[1/4] Checking Ollama daemon connectivity on http://127.0.0.1:11434..." -ForegroundColor Yellow
try {
    $ollamaCheck = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -Method Get -TimeoutSec 3
    Write-Host "  -> Ollama is online. Models installed: $(($ollamaCheck.models | ForEach-Object { $_.name }) -join ', ')" -ForegroundColor Green
} catch {
    Write-Host "  -> Ollama is not responding on 127.0.0.1:11434. Starting Ollama daemon..." -ForegroundColor Yellow
    Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 3
}

# 2. Verify Frontend production distribution bundle
Write-Host "[2/4] Checking Frontend production distribution..." -ForegroundColor Yellow
if (-not (Test-Path "$RootDir\frontend\dist\index.html")) {
    Write-Host "  -> Compiling frontend production bundle (Vite)..." -ForegroundColor Yellow
    Set-Location "$RootDir\frontend"
    npm run build
    Set-Location $RootDir
}
Write-Host "  -> Frontend dist bundle verified." -ForegroundColor Green

# 3. Verify Python Virtual Environment
Write-Host "[3/4] Checking Python backend runtime..." -ForegroundColor Yellow
$PythonExe = "$RootDir\backend\venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    Write-Error "Python venv not found at $PythonExe. Please initialize backend environment."
    exit 1
}

# 4. Start production Uvicorn server serving backend API and built SPA frontend
Write-Host "[4/4] Starting FastAPI production server on http://127.0.0.1:8000..." -ForegroundColor Yellow
$proc = Start-Process -FilePath $PythonExe -ArgumentList "-m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4" -PassThru -WindowStyle Normal

# Save PID for graceful shutdown
if (-not (Test-Path "$RootDir\storage")) {
    New-Item -ItemType Directory -Path "$RootDir\storage" -Force | Out-Null
}
$proc.Id | Out-File -FilePath "$RootDir\storage\rag_server.pid" -Encoding ascii

Write-Host "`n✓ System successfully launched!" -ForegroundColor Green
Write-Host "  Access URL:     http://localhost:8000" -ForegroundColor Cyan
Write-Host "  Health Check:   http://localhost:8000/health/ready" -ForegroundColor Cyan
Write-Host "  PID:            $($proc.Id) (Stored in storage\rag_server.pid)" -ForegroundColor Gray
Write-Host "  To stop:        powershell scripts\stop-production.ps1`n" -ForegroundColor Gray
