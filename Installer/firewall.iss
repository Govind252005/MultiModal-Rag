// ============================================================================
// firewall.iss
// ----------------------------------------------------------------------------
// Manages a single inbound Windows Firewall allow rule for the application's
// local FastAPI server so first launch is not interrupted by a firewall
// prompt. Optional — failures here are warnings, never fatal.
// ============================================================================

#ifndef FIREWALL_ISS
#define FIREWALL_ISS

function AddFirewallRule(): Boolean;
var
  ExitCode: Integer;
  Params: String;
  AppExePath: String;
begin
  LogSection('Firewall Configuration');
  AppExePath := ExpandConstant('{app}\{#APP_EXE_NAME}');

  Params := 'advfirewall firewall add rule name="{#FIREWALL_RULE_NAME}" ' +
    'dir=in action=allow program="' + AppExePath + '" ' +
    'protocol=TCP localport={#DEFAULT_PORT} enable=yes profile=private,domain';

  Result := ExecAndWait(ExpandConstant('{sys}\netsh.exe'), Params, '', ExitCode) and (ExitCode = 0);

  if Result then
    LogSuccess('Firewall rule "{#FIREWALL_RULE_NAME}" added for port {#DEFAULT_PORT}.')
  else
    LogWarning('Could not add firewall rule automatically. You may see a Windows Firewall prompt on first launch.');
end;

function RemoveFirewallRule(): Boolean;
var
  ExitCode: Integer;
  Params: String;
begin
  Params := 'advfirewall firewall delete rule name="{#FIREWALL_RULE_NAME}"';
  Result := ExecAndWait(ExpandConstant('{sys}\netsh.exe'), Params, '', ExitCode) and (ExitCode = 0);
  if Result then
    LogSuccess('Firewall rule "{#FIREWALL_RULE_NAME}" removed.')
  else
    LogWarning('Could not remove firewall rule "{#FIREWALL_RULE_NAME}" during uninstall.');
end;

#endif
