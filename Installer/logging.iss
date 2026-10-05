// ============================================================================
// logging.iss
// ----------------------------------------------------------------------------
// Central logging system. Every module writes through these functions so the
// installer produces one consistent, timestamped installer.log.
// ============================================================================

#ifndef LOGGING_ISS
#define LOGGING_ISS

procedure InitLogging();
var
  LogDir: String;
begin
  LogDir := ExpandConstant('{#LOG_DIRECTORY}');
  if not DirExists(LogDir) then
  begin
    if not ForceDirectories(LogDir) then
    begin
      // Fall back to temp if we truly cannot create the log directory.
      LogDir := ExpandConstant('{tmp}');
    end;
  end;

  LogFilePath := AddBackslash(LogDir) + '{#LOG_FILE}';
  InstallStartTime := GetDateTimeString('yyyy-mm-dd hh:nn:ss', #0, #0);

  SaveStringToFile(LogFilePath,
    '================================================================' + #13#10 +
    '{#APP_NAME} {#APP_VERSION} - Installer Log' + #13#10 +
    'Started: ' + InstallStartTime + #13#10 +
    '================================================================' + #13#10,
    False);

  SummarySuccessList := TStringList.Create;
  SummaryWarningList := TStringList.Create;
  SummaryErrorList := TStringList.Create;
end;

procedure WriteLogLine(const Prefix, Msg: String);
var
  Line: String;
begin
  if LogFilePath = '' then Exit;
  Line := '[' + GetDateTimeString('hh:nn:ss', #0, #0) + '] [' + Prefix + '] ' + Msg;
  SaveStringToFile(LogFilePath, Line + #13#10, True);
end;

procedure LogInfo(const Msg: String);
begin
  WriteLogLine('INFO', Msg);
end;

procedure LogWarning(const Msg: String);
begin
  WriteLogLine('WARN', Msg);
  if SummaryWarningList <> nil then
    SummaryWarningList.Add(Msg);
end;

procedure LogError(const Msg: String);
begin
  WriteLogLine('ERROR', Msg);
  if SummaryErrorList <> nil then
    SummaryErrorList.Add(Msg);
end;

procedure LogSuccess(const Msg: String);
begin
  WriteLogLine('OK', Msg);
  if SummarySuccessList <> nil then
    SummarySuccessList.Add(Msg);
end;

procedure LogSection(const Title: String);
begin
  WriteLogLine('----', '---------------------------------------------');
  WriteLogLine('----', Title);
  WriteLogLine('----', '---------------------------------------------');
end;

procedure FinishLogging();
begin
  if LogFilePath = '' then Exit;
  WriteLogLine('INFO', 'Installer finished at ' +
    GetDateTimeString('yyyy-mm-dd hh:nn:ss', #0, #0));
  WriteLogLine('INFO', 'Success items: ' + IntToStr(SummarySuccessList.Count) +
    ' | Warnings: ' + IntToStr(SummaryWarningList.Count) +
    ' | Errors: ' + IntToStr(SummaryErrorList.Count));
end;

#endif
