# Enterprise Production Shutdown Script (Windows PowerShell)
$ErrorActionPreference = "SilentlyContinue"

$RootDir = Split-Path -Parent $PSScriptRoot
Set-Location $RootDir

Write-Host "Gracefully stopping Enterprise Multimodal Offline RAG..." -ForegroundColor Yellow

$pidFile = "$RootDir\storage\rag_server.pid"
if (Test-Path $pidFile) {
    $procId = Get-Content $pidFile
    if ($procId) {
        Write-Host "Stopping process PID: $procId..." -ForegroundColor Yellow
        Stop-Process -Id $procId -Force
        Remove-Item $pidFile -Force
    }
}

# Also ensure any lingering uvicorn processes on port 8000 are cleaned
$conn = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
if ($conn) {
    foreach ($c in $conn) {
        if ($c.OwningProcess -gt 0) {
            Write-Host "Terminating lingering process on port 8000 (PID $($c.OwningProcess))..." -ForegroundColor Yellow
            Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
        }
    }
}

Write-Host "✓ System stopped successfully." -ForegroundColor Green
