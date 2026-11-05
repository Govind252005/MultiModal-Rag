<#
.SYNOPSIS
    Pulls an Ollama model, streaming progress to stdout, then verifies it is
    listed by `ollama list` afterward.

.PARAMETER OllamaPath
    Full path to ollama.exe.

.PARAMETER ModelName
    Model tag to pull, e.g. "qwen2.5:7b".

.PARAMETER MaxRetries
    How many times to retry a failed pull.
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$OllamaPath,

    [Parameter(Mandatory = $true)]
    [string]$ModelName,

    [int]$MaxRetries = 3
)

$ErrorActionPreference = 'Stop'

function Test-ModelInstalled {
    param([string]$Ollama, [string]$Model)
    try {
        $list = & $Ollama list 2>$null
        return ($list -match [regex]::Escape($Model))
    } catch {
        return $false
    }
}

if (Test-ModelInstalled -Ollama $OllamaPath -Model $ModelName) {
    Write-Output "Model '$ModelName' is already installed."
    exit 0
}

$attempt = 0
$success = $false

while ($attempt -lt $MaxRetries -and -not $success) {
    $attempt++
    Write-Output "Pulling model '$ModelName' (attempt $attempt of $MaxRetries)..."
    try {
        & $OllamaPath pull $ModelName 2>&1 | ForEach-Object { Write-Output $_ }
        if ($LASTEXITCODE -eq 0) {
            $success = $true
        } else {
            Write-Output "ollama pull exited with code $LASTEXITCODE"
        }
    } catch {
        Write-Output "Pull attempt $attempt failed: $($_.Exception.Message)"
    }

    if (-not $success -and $attempt -lt $MaxRetries) {
        Start-Sleep -Seconds (5 * $attempt)
    }
}

if (-not $success) {
    Write-Error "Failed to pull model '$ModelName' after $MaxRetries attempts."
    exit 1
}

if (Test-ModelInstalled -Ollama $OllamaPath -Model $ModelName) {
    Write-Output "Model '$ModelName' verified as installed."
    exit 0
} else {
    Write-Error "Model '$ModelName' pull reported success but was not found in 'ollama list'."
    exit 1
}
