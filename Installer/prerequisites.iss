// ============================================================================
// prerequisites.iss
// ----------------------------------------------------------------------------
// Handles ONLY third-party runtime prerequisites (currently VC++ Redist).
// Must not touch Ollama, models, or application files.
// ============================================================================

#ifndef PREREQUISITES_ISS
#define PREREQUISITES_ISS

function InstallVCRedist(): Boolean;
var
  DestPath: String;
  ExitCode: Integer;
begin
  LogSection('VC++ Redistributable');

  if VCRedistInstalled then
  begin
    LogSuccess('VC++ Redistributable already installed. Skipping.');
    Result := True;
    Exit;
  end;

  DestPath := ExpandConstant('{tmp}\{#VCREDIST_FILENAME}');

  if not DownloadFile('{#VCREDIST_URL}', DestPath, StrToIntDef('{#DOWNLOAD_TIMEOUT}', 300)) then
  begin
    LogWarning('Could not download VC++ Redistributable. The application may fail to start if it is missing.');
    Result := False;
    Exit;
  end;

  LogInfo('Installing VC++ Redistributable silently...');
  if not ExecAndWait(DestPath, '/install /quiet /norestart', '', ExitCode) then
  begin
    LogWarning('VC++ Redistributable installer could not be launched.');
    Result := False;
    Exit;
  end;

  // 0 = success, 3010 = success but reboot required, 1638 = newer version already present
  Result := (ExitCode = 0) or (ExitCode = 3010) or (ExitCode = 1638);

  if Result then
  begin
    LogSuccess('VC++ Redistributable installed successfully (exit code ' + IntToStr(ExitCode) + ').');
    VCRedistInstalled := True;
    if ExitCode = 3010 then
      LogWarning('A system restart is recommended to complete the VC++ Redistributable installation.');
  end
  else
    LogWarning('VC++ Redistributable installation returned exit code ' + IntToStr(ExitCode) + '.');
end;

#endif
