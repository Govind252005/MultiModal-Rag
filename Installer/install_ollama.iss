// ============================================================================
// install_ollama.iss
// ----------------------------------------------------------------------------
// Handles ONLY Ollama installation: locate, download, run, verify, start.
// Must NOT download or manage AI models — see download_model.iss for that.
// ============================================================================

#ifndef INSTALL_OLLAMA_ISS
#define INSTALL_OLLAMA_ISS

// Checks the common install locations for ollama.exe. Mirrors the paths
// diagnostics.ps1 already checks, so a system-wide (Program Files) install
// is not incorrectly reported as missing.
function FindOllamaOnDisk(var FoundPath: String): Boolean;
begin
  FoundPath := ExpandConstant('{#OLLAMA_EXPECTED_INSTALL_PATH}');
  Result := FileExistsSafe(FoundPath);
  if not Result then
  begin
    FoundPath := ExpandConstant('{pf}\Ollama\ollama.exe');
    Result := FileExistsSafe(FoundPath);
  end;
end;

function LocateOllama(): Boolean;
var
  FoundPath: String;
begin
  Result := OllamaInstalled and FileExistsSafe(OllamaPath);
  if not Result then
  begin
    // Re-check common install locations in case diagnostics.ini is stale
    // (e.g. Ollama was installed earlier in this same session).
    if FindOllamaOnDisk(FoundPath) then
    begin
      OllamaPath := FoundPath;
      OllamaInstalled := True;
      Result := True;
    end;
  end;
end;

function DownloadOllamaInstaller(var DestPath: String): Boolean;
begin
  DestPath := ExpandConstant('{tmp}\{#OLLAMA_INSTALLER_FILENAME}');
  Result := DownloadFile('{#OLLAMA_DOWNLOAD_URL}', DestPath, StrToIntDef('{#DOWNLOAD_TIMEOUT}', 300));
end;

function RunOllamaInstaller(const InstallerPath: String): Boolean;
var
  ExitCode: Integer;
begin
  LogInfo('Launching Ollama installer silently...');
  // The official Ollama installer supports a silent switch.
  Result := ExecAndWait(InstallerPath, '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART', '', ExitCode);
  Result := Result and ((ExitCode = 0) or (ExitCode = 3010));
  if Result then
    LogSuccess('Ollama installer completed (exit code ' + IntToStr(ExitCode) + ').')
  else
    LogError('Ollama installer failed (exit code ' + IntToStr(ExitCode) + ').');
end;

function VerifyOllamaInstalled(): Boolean;
var
  FoundPath: String;
begin
  Result := FindOllamaOnDisk(FoundPath);
  if Result then
  begin
    OllamaPath := FoundPath;
    OllamaInstalled := True;
    LogSuccess('Verified Ollama binary at ' + OllamaPath);
  end
  else
    LogError('Ollama binary not found after installation.');
end;

function StartOllamaService(): Boolean;
var
  ScriptPath, Args: String;
  ExitCode: Integer;
begin
  ExtractTemporaryFile('install_ollama.ps1');
  ScriptPath := ExpandConstant('{tmp}\install_ollama.ps1');
  Args := '-OllamaPath "' + OllamaPath + '" -TimeoutSec {#OLLAMA_STARTUP_TIMEOUT_SEC}';

  Result := RunPowerShell(ScriptPath, Args, ExitCode);
  OllamaRunning := Result;

  if Result then
    LogSuccess('Ollama server is running on port {#OLLAMA_SERVICE_PORT}.')
  else
    LogWarning('Ollama server did not confirm it was running within the timeout. It may still start on its own.');
end;

// Full entry point called from installer.iss during the Install Ollama step.
function InstallOllama(): Boolean;
var
  InstallerPath: String;
begin
  LogSection('Ollama Installation');

  if LocateOllama() then
  begin
    LogSuccess('Ollama is already installed at ' + OllamaPath + '. Skipping download.');
    Result := StartOllamaService();
    Exit;
  end;

  if not DownloadOllamaInstaller(InstallerPath) then
  begin
    LogError('Failed to download the Ollama installer.');
    Result := False;
    Exit;
  end;

  if not RunOllamaInstaller(InstallerPath) then
  begin
    Result := False;
    Exit;
  end;

  if not VerifyOllamaInstalled() then
  begin
    Result := False;
    Exit;
  end;

  Result := StartOllamaService();
end;

#endif
