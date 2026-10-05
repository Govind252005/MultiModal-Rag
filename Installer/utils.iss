// ============================================================================
// utils.iss
// ----------------------------------------------------------------------------
// Generic, reusable helper functions. No application-specific business logic
// lives here — only building blocks other modules compose.
// ============================================================================

#ifndef UTILS_ISS
#define UTILS_ISS

// ---------------------------------------------------------------------------
// Filesystem helpers
// ---------------------------------------------------------------------------
function FileExistsSafe(const Path: String): Boolean;
begin
  Result := (Path <> '') and FileExists(Path);
end;

function DirectoryExistsSafe(const Path: String): Boolean;
begin
  Result := (Path <> '') and DirExists(Path);
end;

function EnsureDirectory(const Path: String): Boolean;
begin
  if DirectoryExistsSafe(Path) then
  begin
    Result := True;
    Exit;
  end;
  Result := ForceDirectories(Path);
  if Result then
    LogInfo('Created directory: ' + Path)
  else
    LogError('Failed to create directory: ' + Path);
end;

// ---------------------------------------------------------------------------
// OS helpers
// ---------------------------------------------------------------------------
function Is64Bit(): Boolean;
begin
  Result := Is64BitInstallMode;
end;

function IsWindows11(): Boolean;
var
  Version: TWindowsVersion;
begin
  GetWindowsVersionEx(Version);
  // Windows 11 reports major 10, minor 0, build >= 22000.
  Result := (Version.Major = 10) and (Version.Build >= 22000);
end;

function IsWindows10OrNewer(): Boolean;
var
  Version: TWindowsVersion;
begin
  GetWindowsVersionEx(Version);
  Result := (Version.Major >= 10);
end;

// ---------------------------------------------------------------------------
// Process execution
// ---------------------------------------------------------------------------
function ExecAndWait(const Filename, Params, WorkingDir: String; var ExitCode: Integer): Boolean;
begin
  Result := Exec(Filename, Params, WorkingDir, SW_HIDE, ewWaitUntilTerminated, ExitCode);
  if not Result then
    LogError('ExecAndWait failed to launch: ' + Filename + ' ' + Params)
  else
    LogInfo('ExecAndWait: "' + Filename + ' ' + Params + '" exited with code ' + IntToStr(ExitCode));
end;

function ExecAndWaitVisible(const Filename, Params, WorkingDir: String; var ExitCode: Integer): Boolean;
begin
  Result := Exec(Filename, Params, WorkingDir, SW_SHOWNORMAL, ewWaitUntilTerminated, ExitCode);
  LogInfo('ExecAndWaitVisible: "' + Filename + ' ' + Params + '" exited with code ' + IntToStr(ExitCode));
end;

// Runs a PowerShell script file and waits for completion. Returns True if the
// process exit code is 0.
function RunPowerShell(const ScriptPath, Arguments: String; var ExitCode: Integer): Boolean;
var
  PS: String;
  Params: String;
begin
  PS := ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe');
  Params := '-NoProfile -ExecutionPolicy Bypass -File "' + ScriptPath + '" ' + Arguments;
  LogInfo('Running PowerShell: ' + ScriptPath + ' ' + Arguments);
  Result := ExecAndWait(PS, Params, '', ExitCode) and (ExitCode = 0);
  if not Result then
    LogError('PowerShell script failed: ' + ScriptPath + ' (exit code ' + IntToStr(ExitCode) + ')');
end;

// ---------------------------------------------------------------------------
// Download helper (wraps Inno's DownloadTemporaryFile via idp-free approach:
// here we shell out to PowerShell's Invoke-WebRequest for reliability with
// large files and progress-friendly retries).
// ---------------------------------------------------------------------------
function DownloadFile(const Url, DestPath: String; TimeoutSec: Integer): Boolean;
var
  PS: String;
  Params: String;
  ExitCode: Integer;
  Script: String;
begin
  PS := ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe');
  Script :=
    '$ProgressPreference = ''SilentlyContinue''; ' +
    '$ErrorActionPreference = ''Stop''; ' +
    'try { ' +
    '  Invoke-WebRequest -Uri "' + Url + '" -OutFile "' + DestPath + '" -TimeoutSec ' + IntToStr(TimeoutSec) + '; ' +
    '  exit 0 ' +
    '} catch { ' +
    '  Write-Error $_.Exception.Message; ' +
    '  exit 1 ' +
    '}';
  Params := '-NoProfile -ExecutionPolicy Bypass -Command "' + Script + '"';
  LogInfo('Downloading: ' + Url + ' -> ' + DestPath);
  Result := ExecAndWait(PS, Params, '', ExitCode) and (ExitCode = 0) and FileExistsSafe(DestPath);
  if Result then
    LogSuccess('Download complete: ' + DestPath)
  else
    LogError('Download failed: ' + Url);
end;

// ---------------------------------------------------------------------------
// INI helpers (thin wrapper for readability / consistent section naming)
// ---------------------------------------------------------------------------
function ReadIni(const FilePath, Section, Key, Default: String): String;
begin
  Result := GetIniString(Section, Key, Default, FilePath);
end;

function ReadIniInt(const FilePath, Section, Key: String; Default: Integer): Integer;
begin
  Result := GetIniInt(Section, Key, Default, -2147483647, 2147483647, FilePath);
end;

function ReadIniBool(const FilePath, Section, Key: String; Default: Boolean): Boolean;
var
  DefaultStr, Val: String;
begin
  if Default then DefaultStr := 'true' else DefaultStr := 'false';
  Val := Lowercase(GetIniString(Section, Key, DefaultStr, FilePath));
  Result := (Val = 'true') or (Val = '1') or (Val = 'yes');
end;

procedure WriteIni(const FilePath, Section, Key, Value: String);
begin
  SetIniString(Section, Key, Value, FilePath);
end;

// ---------------------------------------------------------------------------
// Misc
// ---------------------------------------------------------------------------
function BoolToStrYesNo(B: Boolean): String;
begin
  if B then Result := 'Yes' else Result := 'No';
end;

function IIf(const Condition: Boolean; const TrueVal, FalseVal: String): String;
begin
  if Condition then
    Result := TrueVal
  else
    Result := FalseVal;
end;

function CheckInternetConnection(const TestUrl: String): Boolean;
var
  PS: String;
  Params: String;
  ExitCode: Integer;
  Script: String;
begin
  PS := ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe');
  Script :=
    '$ErrorActionPreference = ''Stop''; ' +
    'try { ' +
    '  $r = Invoke-WebRequest -Uri "' + TestUrl + '" -UseBasicParsing -TimeoutSec 8; ' +
    '  exit 0 ' +
    '} catch { exit 1 }';
  Params := '-NoProfile -ExecutionPolicy Bypass -Command "' + Script + '"';
  Result := ExecAndWait(PS, Params, '', ExitCode) and (ExitCode = 0);
end;

#endif
