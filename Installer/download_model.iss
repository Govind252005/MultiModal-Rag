// ============================================================================
// download_model.iss
// ----------------------------------------------------------------------------
// Handles ONLY AI model acquisition: check installed models, pull the
// required model, verify it landed, retry on failure, show progress.
// Must NOT install Ollama itself — see install_ollama.iss for that.
// ============================================================================

#ifndef DOWNLOAD_MODEL_ISS
#define DOWNLOAD_MODEL_ISS

function IsModelAlreadyInstalled(const Model: String): Boolean;
var
  ExitCode: Integer;
  ResultsFile: String;
  ListOutput: AnsiString;
begin
  // Quick check via `ollama list` piped to a temp file (cheap, avoids
  // re-running the full PowerShell verification script for the common case).
  ResultsFile := ExpandConstant('{tmp}\ollama_list.txt');
  ExecAndWait(ExpandConstant('{cmd}'), '/C "' + OllamaPath + '" list > "' + ResultsFile + '"', '', ExitCode);

  Result := False;
  if FileExistsSafe(ResultsFile) then
  begin
    LoadStringFromFile(ResultsFile, ListOutput);
    Result := Pos(Lowercase(Model), Lowercase(ListOutput)) > 0;
  end;
end;

function PullModel(const Model: String): Boolean;
var
  ScriptPath, Args: String;
  ExitCode: Integer;
begin
  ExtractTemporaryFile('download_model.ps1');
  ScriptPath := ExpandConstant('{tmp}\download_model.ps1');
  Args := '-OllamaPath "' + OllamaPath + '" -ModelName "' + Model +
    '" -MaxRetries {#MODEL_DOWNLOAD_MAX_RETRIES}';

  LogInfo('Pulling model: ' + Model + ' (this may take a while for large models)');
  Result := RunPowerShell(ScriptPath, Args, ExitCode);

  if Result then
    LogSuccess('Model "' + Model + '" downloaded and verified.')
  else
    LogError('Failed to download model "' + Model + '" (exit code ' + IntToStr(ExitCode) + ').');
end;

// Full entry point called from installer.iss during the Download AI Model step.
function DownloadModel(): Boolean;
begin
  LogSection('AI Model Download');

  if not OllamaRunning then
  begin
    LogError('Cannot download model: Ollama is not running.');
    Result := False;
    Exit;
  end;

  ModelName := '{#DEFAULT_MODEL}';

  if IsModelAlreadyInstalled(ModelName) then
  begin
    LogSuccess('Model "' + ModelName + '" is already installed. Skipping download.');
    ModelInstalled := True;
    Result := True;
    Exit;
  end;

  Result := PullModel(ModelName);

  if not Result and (not UseGPUMode) then
  begin
    LogWarning('Primary model download failed. Attempting smaller fallback model for CPU mode: {#DEFAULT_MODEL_FALLBACK}');
    ModelName := '{#DEFAULT_MODEL_FALLBACK}';
    Result := PullModel(ModelName);
  end;

  ModelInstalled := Result;
end;

#endif
