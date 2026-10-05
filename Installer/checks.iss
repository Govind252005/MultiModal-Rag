// ============================================================================
// checks.iss
// ----------------------------------------------------------------------------
// System diagnostics. Runs diagnostics.ps1, loads results into globals,
// validates minimum requirements, and renders the system-check summary page.
// This module MUST NOT install anything.
// ============================================================================

#ifndef CHECKS_ISS
#define CHECKS_ISS

function GetDiagnosticsScriptPath(): String;
begin
  Result := ExpandConstant('{tmp}\diagnostics.ps1');
end;

// Extracts the embedded diagnostics.ps1 (packaged via [Files] with flag
// dontcopy) to {tmp} so it can be executed before installation begins.
procedure ExtractDiagnosticsScript();
begin
  ExtractTemporaryFile('diagnostics.ps1');
end;

// Runs diagnostics.ps1 and populates DiagnosticsIniPath. Returns True on
// success (script executed and produced an ini file).
function RunDiagnostics(): Boolean;
var
  ExitCode: Integer;
  ScriptPath, Args: String;
begin
  LogSection('System Diagnostics');
  ExtractDiagnosticsScript();
  ScriptPath := GetDiagnosticsScriptPath();
  DiagnosticsIniPath := ExpandConstant('{tmp}\{#DIAGNOSTICS_INI_NAME}');
  Args := '-OutputPath "' + DiagnosticsIniPath + '"';

  Result := RunPowerShell(ScriptPath, Args, ExitCode) and FileExistsSafe(DiagnosticsIniPath);

  if Result then
    LogSuccess('Diagnostics collected successfully')
  else
    LogError('Diagnostics collection failed (exit code ' + IntToStr(ExitCode) + ')');
end;

// Reads diagnostics.ini into the shared globals declared in globals.iss.
procedure LoadDiagnosticsIntoGlobals();
begin
  WindowsVersion := ReadIni(DiagnosticsIniPath, 'Windows', 'Caption', 'Unknown');
  WindowsBuild := ReadIniInt(DiagnosticsIniPath, 'Windows', 'Build', 0);
  Is64BitOS := ReadIniBool(DiagnosticsIniPath, 'Windows', 'Is64Bit', True);

  CPUName := ReadIni(DiagnosticsIniPath, 'CPU', 'Name', 'Unknown CPU');
  CPUCores := ReadIniInt(DiagnosticsIniPath, 'CPU', 'Cores', 1);

  RAMGB := ReadIniInt(DiagnosticsIniPath, 'Memory', 'TotalRAMGB', 0);
  DiskFreeGB := ReadIniInt(DiagnosticsIniPath, 'Disk', 'FreeGB', 0);
  InternetAvailable := ReadIniBool(DiagnosticsIniPath, 'Internet', 'Available', False);

  GPUAvailable := ReadIniBool(DiagnosticsIniPath, 'GPU', 'Available', False);
  GPUName := ReadIni(DiagnosticsIniPath, 'GPU', 'Name', 'None');
  VRAMGB := ReadIniInt(DiagnosticsIniPath, 'GPU', 'VRAMGB', 0);

  CUDAAvailable := ReadIniBool(DiagnosticsIniPath, 'CUDA', 'Available', False);
  CUDAVersion := ReadIni(DiagnosticsIniPath, 'CUDA', 'Version', '');

  VCRedistInstalled := ReadIniBool(DiagnosticsIniPath, 'VCRedist', 'Installed', False);

  OllamaInstalled := ReadIniBool(DiagnosticsIniPath, 'Ollama', 'Installed', False);
  OllamaPath := ReadIni(DiagnosticsIniPath, 'Ollama', 'Path', '');

  PythonAvailable := ReadIniBool(DiagnosticsIniPath, 'Python', 'Available', False);
  PythonVersion := ReadIni(DiagnosticsIniPath, 'Python', 'Version', '');

  // Decide GPU vs CPU mode: require both a usable NVIDIA GPU and CUDA.
  UseGPUMode := GPUAvailable and CUDAAvailable and (VRAMGB >= 4);

  LogInfo('Windows: ' + WindowsVersion + ' (build ' + IntToStr(WindowsBuild) + ')');
  LogInfo('CPU: ' + CPUName + ' (' + IntToStr(CPUCores) + ' cores)');
  LogInfo('RAM: ' + IntToStr(RAMGB) + ' GB | Disk free: ' + IntToStr(DiskFreeGB) + ' GB');
  LogInfo('GPU: ' + GPUName + ' | VRAM: ' + IntToStr(VRAMGB) + ' GB | CUDA: ' + BoolToStrYesNo(CUDAAvailable));
  LogInfo('Internet: ' + BoolToStrYesNo(InternetAvailable));
  LogInfo('Ollama already installed: ' + BoolToStrYesNo(OllamaInstalled));
  LogInfo('Selected mode: ' + IIf(UseGPUMode, 'GPU', 'CPU'));
end;

// Validates hard requirements. Returns False if installation cannot proceed.
function ValidateRequirements(): Boolean;
begin
  Result := True;

  if not Is64BitOS then
  begin
    LogError('64-bit Windows is required.');
    Result := False;
  end;

  if WindowsBuild < {#MIN_WINDOWS_BUILD} then
  begin
    LogError('Windows build ' + IntToStr(WindowsBuild) + ' is below the minimum required build {#MIN_WINDOWS_BUILD}.');
    Result := False;
  end;

  if RAMGB < StrToIntDef('{#MIN_RAM_GB}', 8) then
  begin
    LogError('Insufficient RAM: ' + IntToStr(RAMGB) + ' GB detected, {#MIN_RAM_GB} GB required.');
    Result := False;
  end
  else if RAMGB < StrToIntDef('{#RECOMMENDED_RAM_GB}', 16) then
  begin
    LogWarning('RAM below recommended {#RECOMMENDED_RAM_GB} GB (' + IntToStr(RAMGB) + ' GB detected). Performance may be reduced.');
  end;

  if DiskFreeGB < StrToIntDef('{#MIN_DISK_GB}', 15) then
  begin
    LogError('Insufficient disk space: ' + IntToStr(DiskFreeGB) + ' GB free, {#MIN_DISK_GB} GB required.');
    Result := False;
  end;

  if not InternetAvailable then
  begin
    LogError('No internet connection detected. Internet access is required to download Ollama and the AI model.');
    Result := False;
  end;

  if not CUDAAvailable then
    LogWarning('No CUDA-capable GPU detected. The application will run in CPU mode (slower inference).');
end;

// ---------------------------------------------------------------------------
// Wizard UI: system check / summary page
// ---------------------------------------------------------------------------
procedure CreateSystemCheckPage();
begin
  SystemCheckPage := CreateCustomPage(wpSelectTasks, 'System Check',
    'The installer is verifying your system meets the requirements for {#APP_NAME}.');

  SummaryMemo := TNewMemo.Create(SystemCheckPage);
  SummaryMemo.Parent := SystemCheckPage.Surface;
  SummaryMemo.Left := 0;
  SummaryMemo.Top := 0;
  SummaryMemo.Width := SystemCheckPage.SurfaceWidth;
  SummaryMemo.Height := SystemCheckPage.SurfaceHeight;
  SummaryMemo.ReadOnly := True;
  SummaryMemo.ScrollBars := ssVertical;
  SummaryMemo.Font.Name := 'Consolas';
  SummaryMemo.Font.Size := 9;
end;

function BuildSummaryText(): String;
var
  S: String;
begin
  S := 'SYSTEM SUMMARY' + #13#10;
  S := S + '========================================' + #13#10#13#10;
  S := S + 'Operating System : ' + WindowsVersion + #13#10;
  S := S + 'Architecture     : ' + IIf(Is64BitOS, '64-bit', '32-bit (unsupported)') + #13#10;
  S := S + 'CPU              : ' + CPUName + ' (' + IntToStr(CPUCores) + ' cores)' + #13#10;
  S := S + 'RAM              : ' + IntToStr(RAMGB) + ' GB' + #13#10;
  S := S + 'Free Disk Space  : ' + IntToStr(DiskFreeGB) + ' GB' + #13#10;
  S := S + 'Internet         : ' + BoolToStrYesNo(InternetAvailable) + #13#10#13#10;
  S := S + 'GPU              : ' + GPUName + #13#10;
  S := S + 'VRAM             : ' + IntToStr(VRAMGB) + ' GB' + #13#10;
  S := S + 'CUDA             : ' + BoolToStrYesNo(CUDAAvailable) + ' ' + CUDAVersion + #13#10;
  S := S + 'VC++ Redist      : ' + BoolToStrYesNo(VCRedistInstalled) + #13#10#13#10;
  S := S + 'Ollama Installed : ' + BoolToStrYesNo(OllamaInstalled) + #13#10;
  S := S + 'Selected Mode    : ' + IIf(UseGPUMode, 'GPU (accelerated)', 'CPU (compatibility)') + #13#10#13#10;

  if SummaryErrorList.Count > 0 then
  begin
    S := S + 'ERRORS (installation cannot continue):' + #13#10;
    S := S + SummaryErrorList.Text + #13#10;
  end;

  if SummaryWarningList.Count > 0 then
  begin
    S := S + 'WARNINGS:' + #13#10;
    S := S + SummaryWarningList.Text + #13#10;
  end;

  if (SummaryErrorList.Count = 0) then
    S := S + 'Your system meets the requirements. Click Next to continue.' + #13#10;

  Result := S;
end;

procedure RefreshSystemCheckPage();
begin
  SummaryMemo.Lines.Text := BuildSummaryText();
end;

// Full entry point called from installer.iss during wizard init / page change.
function PerformSystemCheck(): Boolean;
begin
  Result := RunDiagnostics();
  if not Result then
  begin
    MsgBox('System diagnostics could not be completed. Please check your internet connection and try again.', mbCriticalError, MB_OK);
    Exit;
  end;

  LoadDiagnosticsIntoGlobals();
  Result := ValidateRequirements();
  RefreshSystemCheckPage();
end;

#endif
