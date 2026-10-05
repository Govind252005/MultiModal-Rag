<#
.SYNOPSIS
    Post-uninstall cleanup for Multimodal RAG. Stops any running app process
    and, only if -RemoveUserData was passed, deletes the app data directory.
    Ollama itself is NEVER removed by this script — it is a shared, separately
    managed dependency that the user installed system-wide.

.PARAMETER DataDir
    Root application data directory to optionally remove.

.PARAMETER RemoveUserData
    Pass "true" to delete DataDir (config, logs, cached data). Defaults to
    "false" so uninstalling never silently destroys user data/history.
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$DataDir,

    [string]$RemoveUserData = 'false'
)

$ErrorActionPreference = 'SilentlyContinue'

# Stop any lingering app process
Get-Process -Name 'MultimodalRag' -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Output "Stopping running process: $($_.Id)"
    Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
}

if ($RemoveUserData -eq 'true') {
    if (Test-Path $DataDir) {
        Write-Output "Removing application data directory: $DataDir"
        Remove-Item -Path $DataDir -Recurse -Force -ErrorAction SilentlyContinue
    }
} else {
    Write-Output "Preserving application data directory: $DataDir"
}

Write-Output "Cleanup complete."
exit 0
