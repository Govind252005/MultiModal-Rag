// ============================================================================
// uninstall.iss
// ----------------------------------------------------------------------------
// Custom uninstall cleanup. Stops the running app, removes the firewall
// rule, and optionally removes user data (config/logs/cache). Ollama and
// downloaded models are intentionally left in place, since they are a
// shared system-wide dependency the user may want to keep for other tools.
// ============================================================================

#ifndef UNINSTALL_ISS
#define UNINSTALL_ISS

// Asks the user, on uninstall, whether to also delete their application
// data (config, logs, cached embeddings/history). Inno's uninstaller does
// not support arbitrary custom wizard pages the way Setup does, so this
// confirmation is shown via a plain dialog instead of a custom page.
function AskRemoveUserData(): Boolean;
begin
  Result := (MsgBox('Do you also want to delete your {#APP_NAME} application data ' +
    '(configuration, logs, and cached data)?' + #13#10#13#10 +
    'Choose "No" to keep your data in case you reinstall later.',
    mbConfirmation, MB_YESNO) = IDYES);
end;

procedure RunUninstallCleanup();
var
  ScriptPath, TmpScript, Args: String;
  ExitCode: Integer;
  RemoveData: Boolean;
begin
  // Stop the app first regardless of the data-removal choice.
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM "{#APP_EXE_NAME}" /T',
    '', SW_HIDE, ewWaitUntilTerminated, ExitCode);

  // Remove the firewall rule we added during install.
  Exec(ExpandConstant('{sys}\netsh.exe'),
    'advfirewall firewall delete rule name="{#FIREWALL_RULE_NAME}"',
    '', SW_HIDE, ewWaitUntilTerminated, ExitCode);

  RemoveData := AskRemoveUserData();

  // The uninstaller ships cleanup.ps1 alongside itself via [UninstallDelete]/
  // [Files] with flag "uninsneveruninstall" so it survives to run here.
  TmpScript := ExpandConstant('{app}\installer\scripts\cleanup.ps1');
  if not FileExists(TmpScript) then
    TmpScript := ExpandConstant('{tmp}\cleanup.ps1');

  if FileExists(TmpScript) then
  begin
    Args := '-NoProfile -ExecutionPolicy Bypass -File "' + TmpScript +
      '" -DataDir "' + ExpandConstant('{#APP_DATA_DIR}') + '" -RemoveUserData ' +
      IIf(RemoveData, 'true', 'false');
    Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'), Args,
      '', SW_HIDE, ewWaitUntilTerminated, ExitCode);
  end;
end;

#endif
