# Enterprise Production Startup Script (Windows PowerShell)
param (
    [switch]$Foreground = $false
)

$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
Set-Location $RootDir

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Starting Enterprise Multimodal Offline RAG Platform      " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 0. Ensure storage directory exists
$StorageDir = "$RootDir\storage"
if (-not (Test-Path $StorageDir)) {
    New-Item -ItemType Directory -Path $StorageDir -Force | Out-Null
}

# 1. Clean up any lingering process on port 8000 to prevent port conflict ([Errno 10048])
$existingConn = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
if ($existingConn) {
    Write-Host "[*] Freeing occupied port 8000 from previous session..." -ForegroundColor Yellow
    foreach ($c in $existingConn) {
        if ($c.OwningProcess -gt 0) {
            Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
        }
    }
    Start-Sleep -Seconds 1
}

# 2. Verify Ollama inference service is reachable
Write-Host "[1/4] Checking Ollama daemon connectivity on http://127.0.0.1:11434..." -ForegroundColor Yellow
try {
    $ollamaCheck = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -Method Get -TimeoutSec 3
    Write-Host "  -> Ollama is online. Models installed: $(($ollamaCheck.models | ForEach-Object { $_.name }) -join ', ')" -ForegroundColor Green
} catch {
    Write-Host "  -> Ollama is not responding on 127.0.0.1:11434. Starting Ollama daemon..." -ForegroundColor Yellow
    Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 3
}

# 3. Verify Frontend production distribution bundle
Write-Host "[2/4] Checking Frontend production distribution..." -ForegroundColor Yellow
if (-not (Test-Path "$RootDir\frontend\dist\index.html")) {
    Write-Host "  -> Compiling frontend production bundle (Vite)..." -ForegroundColor Yellow
    Set-Location "$RootDir\frontend"
    npm run build
    Set-Location $RootDir
}
Write-Host "  -> Frontend dist bundle verified." -ForegroundColor Green

# 4. Verify Python Virtual Environment
Write-Host "[3/4] Checking Python backend runtime..." -ForegroundColor Yellow
$PythonExe = "$RootDir\backend\venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    Write-Error "Python venv not found at $PythonExe. Please initialize backend environment."
    exit 1
}

# 5. Start production Uvicorn server
Write-Host "[4/4] Starting FastAPI production server on http://127.0.0.1:8000..." -ForegroundColor Yellow
$LogFile = "$StorageDir\rag_server.log"

if ($Foreground) {
    Write-Host "  -> Running in foreground mode (Press Ctrl+C to terminate)..." -ForegroundColor Cyan
    & $PythonExe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 1
} else {
    # Launch in a persistent console window that never closes automatically on exit or error
    $batPath = "$RootDir\scripts\run-server.bat"
    $proc = Start-Process -FilePath "cmd.exe" -ArgumentList "/k", "`"$batPath`"" -PassThru -WindowStyle Normal

    # Save PID
    $proc.Id | Out-File -FilePath "$StorageDir\rag_server.pid" -Encoding ascii

    # Health check verification loop (wait up to 15s for models to warm up)
    Write-Host "  -> Waiting for model warm-up and server readiness..." -ForegroundColor Yellow
    $ready = $false
    $healthInfo = $null
    for ($i = 0; $i -lt 15; $i++) {
        Start-Sleep -Seconds 1
        try {
            $h = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health" -Method Get -TimeoutSec 1 -ErrorAction SilentlyContinue
            if ($h.status -eq "ok") {
                $ready = $true
                $healthInfo = $h
                break
            }
        } catch {}

        if ($proc.HasExited) {
            break
        }
    }

    if ($ready) {
        Write-Host ""
        Write-Host "[OK] System successfully launched and verified healthy!" -ForegroundColor Green
        Write-Host "  Access URL:     http://localhost:8000" -ForegroundColor Cyan
        Write-Host "  Health Check:   http://localhost:8000/api/health" -ForegroundColor Cyan
        Write-Host "  Active Model:   $($healthInfo.llm_model)" -ForegroundColor Cyan
        Write-Host "  PID:            $($proc.Id) (Stored in storage\rag_server.pid)" -ForegroundColor Gray
        Write-Host "  Log File:       $LogFile" -ForegroundColor Gray
        Write-Host "  To stop:        powershell scripts\stop-production.ps1" -ForegroundColor Gray
        Write-Host ""
    } else {
        Write-Host ""
        Write-Host "[WARNING] Server took longer than expected to report ready." -ForegroundColor Yellow
        Write-Host "  Check the server window or inspect log: $LogFile" -ForegroundColor Yellow
        Write-Host ""
    }
}
