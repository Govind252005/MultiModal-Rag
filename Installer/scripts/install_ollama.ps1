<#
.SYNOPSIS
    Verifies an Ollama installation and ensures the Ollama server is running,
    waiting up to -TimeoutSec seconds for the local API to respond.

.PARAMETER OllamaPath
    Full path to ollama.exe. If omitted, resolved via PATH.

.PARAMETER TimeoutSec
    How long to wait for the Ollama HTTP API to become available.
#>

param(
    [string]$OllamaPath = '',
    [int]$TimeoutSec = 60
)

$ErrorActionPreference = 'SilentlyContinue'
$ProgressPreference = 'SilentlyContinue'

function Resolve-OllamaPath {
    param([string]$Hint)

    if ($Hint -and (Test-Path $Hint)) { return $Hint }

    $candidates = @(
        "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe",
        "$env:ProgramFiles\Ollama\ollama.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { return $c }
    }

    $cmd = Get-Command 'ollama.exe' -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }

    return $null
}

$resolved = Resolve-OllamaPath -Hint $OllamaPath
if (-not $resolved) {
    Write-Error "ollama.exe could not be located on this system."
    exit 1
}

Write-Output "Using Ollama at: $resolved"

# Is the API already up?
function Test-OllamaApi {
    try {
        $r = Invoke-WebRequest -Uri 'http://127.0.0.1:11434/api/version' -UseBasicParsing -TimeoutSec 3
        return ($r.StatusCode -eq 200)
    } catch {
        return $false
    }
}

if (-not (Test-OllamaApi)) {
    Write-Output "Starting Ollama server..."
    Start-Process -FilePath $resolved -ArgumentList 'serve' -WindowStyle Hidden
}

$elapsed = 0
$interval = 2
while (-not (Test-OllamaApi) -and $elapsed -lt $TimeoutSec) {
    Start-Sleep -Seconds $interval
    $elapsed += $interval
}

if (Test-OllamaApi) {
    Write-Output "Ollama server is running and responding."
    exit 0
} else {
    Write-Error "Ollama server did not respond within $TimeoutSec seconds."
    exit 1
}
