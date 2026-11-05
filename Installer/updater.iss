// ============================================================================
// updater.iss
// ----------------------------------------------------------------------------
// Lightweight update-check support for the installer's Finish page ("Check
// for updates on launch") and for a future standalone updater executable.
// This module only prepares the plumbing (recorded settings + a one-shot
// version check); it does not implement the full auto-update download/apply
// cycle, which belongs in a dedicated updater component run by the app itself.
// ============================================================================

#ifndef UPDATER_ISS
#define UPDATER_ISS

// Extracts the next dot-separated numeric component from S, starting at
// position Pos (1-based), and advances Pos past the delimiter. Returns 0
// (and leaves Pos beyond the string) once there are no more components.
function NextVersionComponent(const S: String; var Pos: Integer): Integer;
var
  StartPos: Integer;
  Piece: String;
begin
  if Pos > Length(S) then
  begin
    Result := 0;
    Exit;
  end;

  StartPos := Pos;
  while (Pos <= Length(S)) and (Copy(S, Pos, 1) <> '.') do
    Pos := Pos + 1;

  Piece := Copy(S, StartPos, Pos - StartPos);
  Result := StrToIntDef(Piece, 0);

  if Pos <= Length(S) then
    Pos := Pos + 1; // skip the '.'
end;

// Compares two "x.y.z" version strings. Returns 1 if A > B, -1 if A < B, 0 if equal.
function CompareVersions(A, B: String): Integer;
var
  PosA, PosB, AN, BN: Integer;
begin
  Result := 0;
  PosA := 1;
  PosB := 1;

  // Three components (major.minor.patch) is enough for this project, but the
  // loop is written so it keeps comparing as long as either string still has
  // characters left to consume.
  while (PosA <= Length(A)) or (PosB <= Length(B)) do
  begin
    AN := NextVersionComponent(A, PosA);
    BN := NextVersionComponent(B, PosB);

    if AN > BN then
    begin
      Result := 1;
      Exit;
    end
    else if AN < BN then
    begin
      Result := -1;
      Exit;
    end;
  end;
end;

// Queries the GitHub Releases API for the latest tag. Returns '' on failure.
function GetLatestVersionFromGitHub(): String;
var
  PS, Params, Script: String;
  ExitCode: Integer;
  OutFile: String;
  RawResult: AnsiString;
begin
  Result := '';
  OutFile := ExpandConstant('{tmp}\latest_release.json');
  PS := ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe');

  Script :=
    '$ErrorActionPreference = ''Stop''; ' +
    'try { ' +
    '  $r = Invoke-RestMethod -Uri "{#UPDATE_GITHUB_API}" -TimeoutSec 10; ' +
    '  $r.tag_name | Out-File -FilePath "' + OutFile + '" -Encoding UTF8; ' +
    '  exit 0 ' +
    '} catch { exit 1 }';

  Params := '-NoProfile -ExecutionPolicy Bypass -Command "' + Script + '"';

  if ExecAndWait(PS, Params, '', ExitCode) and (ExitCode = 0) and FileExistsSafe(OutFile) then
  begin
    LoadStringFromFile(OutFile, RawResult);
    RawResult := Trim(RawResult);
    // Strip a leading "v" if present (e.g. "v1.2.0" -> "1.2.0")
    if (Length(RawResult) > 0) and (Copy(RawResult, 1, 1) = 'v') then
      RawResult := Copy(RawResult, 2, Length(RawResult) - 1);
    Result := RawResult;
  end;
end;

// Returns True if a newer version is available on GitHub than APP_VERSION.
function IsUpdateAvailable(var LatestVersion: String): Boolean;
begin
  Result := False;
  LatestVersion := GetLatestVersionFromGitHub();

  if LatestVersion = '' then
  begin
    LogWarning('Could not check for updates (network or API unavailable).');
    Exit;
  end;

  Result := CompareVersions(LatestVersion, '{#APP_VERSION}') > 0;

  if Result then
    LogInfo('Update available: ' + LatestVersion + ' (installed: {#APP_VERSION})')
  else
    LogInfo('No update available. Latest: ' + LatestVersion + ', installed: {#APP_VERSION}');
end;

// Records the last update-check timestamp/result into config.ini.
procedure RecordUpdateCheck(const LatestVersion: String; UpdateFound: Boolean);
var
  ConfigPath: String;
begin
  ConfigPath := ExpandConstant('{#APP_CONFIG_DIR}\{#APP_CONFIG_FILE}');
  WriteIni(ConfigPath, 'Update', 'LastCheck', GetDateTimeString('yyyy-mm-dd hh:nn:ss', #0, #0));
  WriteIni(ConfigPath, 'Update', 'LatestKnownVersion', LatestVersion);
  WriteIni(ConfigPath, 'Update', 'UpdateAvailable', BoolToStrYesNo(UpdateFound));
end;

#endif
