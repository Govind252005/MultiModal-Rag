<#
.SYNOPSIS
    Collects full system diagnostics for the Multimodal RAG installer and
    writes the result to diagnostics.ini so installer.iss / checks.iss can
    read it via GetIniString / GetIniInt / GetIniBool.

.PARAMETER OutputPath
    Full path to the diagnostics.ini file to write.
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$OutputPath
)

$ErrorActionPreference = 'SilentlyContinue'
$ProgressPreference = 'SilentlyContinue'

function Write-IniLine {
    param([string]$Path, [string]$Text)
    [System.IO.File]::AppendAllText($Path, "$Text`r`n", (New-Object System.Text.UTF8Encoding($false)))
}

function Write-IniSection {
    param([string]$Path, [string]$Section)
    Write-IniLine -Path $Path -Text "[$Section]"
}

function Write-IniValue {
    param([string]$Path, [string]$Key, [string]$Value)
    Write-IniLine -Path $Path -Text "$Key=$Value"
}

# Start with a clean file
if (Test-Path $OutputPath) { Remove-Item $OutputPath -Force }
New-Item -Path $OutputPath -ItemType File -Force | Out-Null

# ---------------------------------------------------------------------------
# [Windows]
# ---------------------------------------------------------------------------
$os = Get-CimInstance Win32_OperatingSystem
$osVersion = [System.Environment]::OSVersion.Version
$is64 = [System.Environment]::Is64BitOperatingSystem

Write-IniSection $OutputPath 'Windows'
Write-IniValue $OutputPath 'Caption' ($os.Caption -replace '=', '-')
Write-IniValue $OutputPath 'Version' "$($osVersion.Major).$($osVersion.Minor)"
Write-IniValue $OutputPath 'Build' "$($osVersion.Build)"
Write-IniValue $OutputPath 'Is64Bit' ($is64.ToString().ToLower())

# ---------------------------------------------------------------------------
# [CPU]
# ---------------------------------------------------------------------------
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
Write-IniSection $OutputPath 'CPU'
Write-IniValue $OutputPath 'Name' ($cpu.Name.Trim() -replace '=', '-')
Write-IniValue $OutputPath 'Cores' "$($cpu.NumberOfCores)"
Write-IniValue $OutputPath 'LogicalProcessors' "$($cpu.NumberOfLogicalProcessors)"

# ---------------------------------------------------------------------------
# [Memory]
# ---------------------------------------------------------------------------
$totalRamBytes = (Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory
$ramGB = [Math]::Round($totalRamBytes / 1GB)
Write-IniSection $OutputPath 'Memory'
Write-IniValue $OutputPath 'TotalRAMGB' "$ramGB"

# ---------------------------------------------------------------------------
# [Disk]
# ---------------------------------------------------------------------------
$sysDrive = $env:SystemDrive
$drive = Get-PSDrive -Name $sysDrive.TrimEnd(':')
$freeGB = [Math]::Round($drive.Free / 1GB)
Write-IniSection $OutputPath 'Disk'
Write-IniValue $OutputPath 'SystemDrive' "$sysDrive"
Write-IniValue $OutputPath 'FreeGB' "$freeGB"

# ---------------------------------------------------------------------------
# [Internet]
# ---------------------------------------------------------------------------
$internetOk = $false
try {
    $resp = Invoke-WebRequest -Uri 'https://ollama.com' -UseBasicParsing -TimeoutSec 8
    if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 400) { $internetOk = $true }
} catch { $internetOk = $false }
Write-IniSection $OutputPath 'Internet'
Write-IniValue $OutputPath 'Available' ($internetOk.ToString().ToLower())

# ---------------------------------------------------------------------------
# [GPU] / [CUDA]
# ---------------------------------------------------------------------------
$gpuName = 'None'
$vramGB = 0
$gpuAvailable = $false
$cudaAvailable = $false
$cudaVersion = ''

$gpus = Get-CimInstance Win32_VideoController | Where-Object {
    $_.Name -notmatch 'Basic Render|Remote Display|Microsoft Basic'
}

$nvidiaGpu = $gpus | Where-Object { $_.Name -match 'NVIDIA' } | Select-Object -First 1
if ($nvidiaGpu) {
    $gpuAvailable = $true
    $gpuName = $nvidiaGpu.Name
    if ($nvidiaGpu.AdapterRAM -gt 0) {
        $vramGB = [Math]::Round($nvidiaGpu.AdapterRAM / 1GB)
    }
} elseif ($gpus) {
    $gpuAvailable = $true
    $gpuName = ($gpus | Select-Object -First 1).Name
}

$nvidiaSmi = Get-Command 'nvidia-smi.exe' -ErrorAction SilentlyContinue
if ($nvidiaSmi) {
    try {
        $smiOutput = & nvidia-smi --query-gpu=memory.total,driver_version --format=csv,noheader 2>$null
        if ($smiOutput) {
            $vramGB = [Math]::Round(([double]($smiOutput -split ',')[0] -replace '[^0-9.]', '') / 1024)
        }
        $nvccVersionOutput = & nvidia-smi 2>$null | Select-String 'CUDA Version:\s*([\d\.]+)'
        if ($nvccVersionOutput) {
            $cudaVersion = $nvccVersionOutput.Matches[0].Groups[1].Value
            $cudaAvailable = $true
        }
    } catch { }
}

Write-IniSection $OutputPath 'GPU'
Write-IniValue $OutputPath 'Available' ($gpuAvailable.ToString().ToLower())
Write-IniValue $OutputPath 'Name' ($gpuName -replace '=', '-')
Write-IniValue $OutputPath 'VRAMGB' "$vramGB"

Write-IniSection $OutputPath 'CUDA'
Write-IniValue $OutputPath 'Available' ($cudaAvailable.ToString().ToLower())
Write-IniValue $OutputPath 'Version' "$cudaVersion"

# ---------------------------------------------------------------------------
# [VCRedist]
# ---------------------------------------------------------------------------
$vcInstalled = $false
$vcKey = 'HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\X64'
if (Test-Path $vcKey) {
    $installedProp = Get-ItemProperty -Path $vcKey -Name Installed -ErrorAction SilentlyContinue
    if ($installedProp -and $installedProp.Installed -eq 1) { $vcInstalled = $true }
}
Write-IniSection $OutputPath 'VCRedist'
Write-IniValue $OutputPath 'Installed' ($vcInstalled.ToString().ToLower())

# ---------------------------------------------------------------------------
# [Ollama]
# ---------------------------------------------------------------------------
$ollamaInstalled = $false
$ollamaPath = ''
$candidatePaths = @(
    "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe",
    "$env:ProgramFiles\Ollama\ollama.exe"
)
foreach ($p in $candidatePaths) {
    if (Test-Path $p) { $ollamaInstalled = $true; $ollamaPath = $p; break }
}
if (-not $ollamaInstalled) {
    $cmd = Get-Command 'ollama.exe' -ErrorAction SilentlyContinue
    if ($cmd) { $ollamaInstalled = $true; $ollamaPath = $cmd.Source }
}

$modelsInstalled = @()
if ($ollamaInstalled) {
    try {
        $listOutput = & $ollamaPath list 2>$null
        if ($listOutput) {
            $modelsInstalled = ($listOutput | Select-Object -Skip 1 | ForEach-Object {
                ($_ -split '\s+')[0]
            }) | Where-Object { $_ -ne '' }
        }
    } catch { }
}

Write-IniSection $OutputPath 'Ollama'
Write-IniValue $OutputPath 'Installed' ($ollamaInstalled.ToString().ToLower())
Write-IniValue $OutputPath 'Path' ($ollamaPath -replace '=', '-')
Write-IniValue $OutputPath 'Models' (($modelsInstalled -join ';') -replace '=', '-')

# ---------------------------------------------------------------------------
# [Python]
# ---------------------------------------------------------------------------
$pythonAvailable = $false
$pythonVersion = ''
$pyCmd = Get-Command 'python.exe' -ErrorAction SilentlyContinue
if ($pyCmd) {
    try {
        $verOut = & python --version 2>&1
        $pythonVersion = ($verOut -replace 'Python\s*', '').Trim()
        $pythonAvailable = $true
    } catch { }
}
Write-IniSection $OutputPath 'Python'
Write-IniValue $OutputPath 'Available' ($pythonAvailable.ToString().ToLower())
Write-IniValue $OutputPath 'Version' "$pythonVersion"

# ---------------------------------------------------------------------------
# [Architecture]
# ---------------------------------------------------------------------------
Write-IniSection $OutputPath 'Architecture'
Write-IniValue $OutputPath 'ProcessorArchitecture' "$env:PROCESSOR_ARCHITECTURE"

# Done
Write-Output "Diagnostics written to $OutputPath"
exit 0
