<#
.SYNOPSIS
    Performs first-run initialization for Multimodal RAG: creates app data
    folders and an initial SQLite database file if one does not exist yet.
    Config/INI creation itself is handled by first_run.iss via WriteIni so the
    values stay consistent with Pascal-Script-computed settings (GPU/CPU mode
    etc.); this script only prepares the filesystem layout.

.PARAMETER DataDir
    Root application data directory (…\AppData\Local\MultimodalRag).
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$DataDir
)

$ErrorActionPreference = 'Stop'

$dirs = @(
    $DataDir,
    (Join-Path $DataDir 'Config'),
    (Join-Path $DataDir 'Data'),
    (Join-Path $DataDir 'Models'),
    (Join-Path $DataDir 'Logs'),
    (Join-Path $DataDir 'Uploads'),
    (Join-Path $DataDir 'Cache')
)

foreach ($d in $dirs) {
    if (-not (Test-Path $d)) {
        New-Item -Path $d -ItemType Directory -Force | Out-Null
        Write-Output "Created: $d"
    }
}

$dbPath = Join-Path (Join-Path $DataDir 'Data') 'multimodal_rag.db'
if (-not (Test-Path $dbPath)) {
    New-Item -Path $dbPath -ItemType File -Force | Out-Null
    Write-Output "Initialized database file: $dbPath"
}

Write-Output "First-run filesystem initialization complete."
exit 0
