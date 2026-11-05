// ============================================================================
// services.iss
// ----------------------------------------------------------------------------
// Multimodal RAG runs its backend as a plain user-mode process (not a Windows
// Service) launched by the packaged executable, so this module's job is
// limited to starting/stopping that process cleanly around install/uninstall,
// and making sure no stale instance is left running before we upgrade files.
// ============================================================================

#ifndef SERVICES_ISS
#define SERVICES_ISS

function IsAppRunning(): Boolean;
var
  ResultCode: Integer;
  TmpFile: String;
  Output: AnsiString;
begin
  TmpFile := ExpandConstant('{tmp}\tasklist_check.txt');
  Exec(ExpandConstant('{cmd}'), '/C tasklist /FI "IMAGENAME eq {#APP_EXE_NAME}" > "' + TmpFile + '"',
    '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

  Result := False;
  if FileExistsSafe(TmpFile) then
  begin
    LoadStringFromFile(TmpFile, Output);
    Result := Pos(Lowercase('{#APP_EXE_NAME}'), Lowercase(Output)) > 0;
  end;
end;

procedure StopApp();
var
  ExitCode: Integer;
begin
  if IsAppRunning() then
  begin
    LogInfo('Stopping running instance of {#APP_NAME} before proceeding...');
    ExecAndWait(ExpandConstant('{sys}\taskkill.exe'), '/F /IM "{#APP_EXE_NAME}" /T', '', ExitCode);
    Sleep(1000);
  end;
end;

function LaunchApp(): Boolean;
var
  AppExePath: String;
  ExitCode: Integer;
begin
  AppExePath := ExpandConstant('{app}\{#APP_EXE_NAME}');
  if not FileExistsSafe(AppExePath) then
  begin
    LogError('Cannot launch application: executable not found at ' + AppExePath);
    Result := False;
    Exit;
  end;

  LogInfo('Launching {#APP_NAME}...');
  Result := Exec(AppExePath, '', ExpandConstant('{app}'), SW_SHOWNORMAL, ewNoWait, ExitCode);

  if Result then
    LogSuccess('{#APP_NAME} launched.')
  else
    LogError('Failed to launch {#APP_NAME}.');
end;

#endif
