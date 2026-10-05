// ============================================================================
// first_run.iss
// ----------------------------------------------------------------------------
// Runs after files are copied and Ollama/model are ready. Creates app
// folders, initializes the database, writes config.ini, configures GPU/CPU
// mode, and launches the application.
// ============================================================================

#ifndef FIRST_RUN_ISS
#define FIRST_RUN_ISS

function InitializeAppFolders(): Boolean;
var
  ScriptPath, Args: String;
  ExitCode: Integer;
begin
  LogSection('First-Run Initialization');
  ExtractTemporaryFile('first_run.ps1');
  ScriptPath := ExpandConstant('{tmp}\first_run.ps1');
  Args := '-DataDir "' + ExpandConstant('{#APP_DATA_DIR}') + '"';

  Result := RunPowerShell(ScriptPath, Args, ExitCode);
  if Result then
    LogSuccess('Application data folders and database initialized.')
  else
    LogError('Failed to initialize application data folders.');
end;

procedure WriteApplicationConfig();
var
  ConfigPath: String;
begin
  ConfigPath := ExpandConstant('{#APP_CONFIG_DIR}\{#APP_CONFIG_FILE}');
  EnsureDirectory(ExpandConstant('{#APP_CONFIG_DIR}'));

  WriteIni(ConfigPath, 'App', 'Name', '{#APP_NAME}');
  WriteIni(ConfigPath, 'App', 'Version', '{#APP_VERSION}');
  WriteIni(ConfigPath, 'App', 'InstallDir', ExpandConstant('{app}'));
  WriteIni(ConfigPath, 'App', 'DataDir', ExpandConstant('{#APP_DATA_DIR}'));

  WriteIni(ConfigPath, 'Server', 'Host', '{#DEFAULT_HOST}');
  WriteIni(ConfigPath, 'Server', 'Port', '{#DEFAULT_PORT}');

  WriteIni(ConfigPath, 'Ollama', 'Path', OllamaPath);
  WriteIni(ConfigPath, 'Ollama', 'Port', '{#OLLAMA_SERVICE_PORT}');
  WriteIni(ConfigPath, 'Ollama', 'Model', ModelName);

  WriteIni(ConfigPath, 'Compute', 'Mode', IIf(UseGPUMode, 'gpu', 'cpu'));
  WriteIni(ConfigPath, 'Compute', 'GPUName', GPUName);
  WriteIni(ConfigPath, 'Compute', 'VRAMGB', IntToStr(VRAMGB));
  WriteIni(ConfigPath, 'Compute', 'CUDAVersion', CUDAVersion);

  WriteIni(ConfigPath, 'Update', 'CheckForUpdates', '{#UPDATE_CHECK_ENABLED}');
  WriteIni(ConfigPath, 'Update', 'LastCheck', '');

  LogSuccess('Configuration written to ' + ConfigPath);
end;

procedure ConfigureComputeMode();
begin
  if UseGPUMode then
    LogSuccess('GPU mode configured: ' + GPUName + ' (' + IntToStr(VRAMGB) + ' GB VRAM, CUDA ' + CUDAVersion + ')')
  else
    LogInfo('CPU mode configured (no compatible GPU/CUDA detected).');
end;

// Full entry point called from installer.iss during the Configure Application step.
function RunFirstRunSetup(): Boolean;
begin
  Result := InitializeAppFolders();
  if not Result then Exit;

  WriteApplicationConfig();
  ConfigureComputeMode();

  Result := True;
end;

#endif
