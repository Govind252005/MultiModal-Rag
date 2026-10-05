// ============================================================================
// globals.iss
// ----------------------------------------------------------------------------
// Shared mutable state used across installer modules. Declarations only.
// No functions, no procedures, no business logic.
// ============================================================================

#ifndef GLOBALS_ISS
#define GLOBALS_ISS

var
  // ---- System diagnostics (populated by checks.iss from diagnostics.ini) ----
  WindowsVersion: String;
  WindowsBuild: Cardinal;
  Is64BitOS: Boolean;
  CPUName: String;
  CPUCores: Cardinal;
  RAMGB: Cardinal;
  DiskFreeGB: Cardinal;
  InternetAvailable: Boolean;

  GPUName: String;
  GPUAvailable: Boolean;
  VRAMGB: Cardinal;
  CUDAAvailable: Boolean;
  CUDAVersion: String;

  VCRedistInstalled: Boolean;
  PythonAvailable: Boolean;
  PythonVersion: String;

  // ---- Ollama / Model state ----
  OllamaInstalled: Boolean;
  OllamaPath: String;
  OllamaRunning: Boolean;
  ModelInstalled: Boolean;
  ModelName: String;

  // ---- Install mode decision ----
  UseGPUMode: Boolean;

  // ---- Wizard pages ----
  SystemCheckPage: TWizardPage;
  SummaryMemo: TNewMemo;
  ProgressPage: TOutputProgressWizardPage;

  // ---- Summary bookkeeping (installer.iss builds the final report from these) ----
  SummarySuccessList: TStringList;
  SummaryWarningList: TStringList;
  SummaryErrorList: TStringList;

  // ---- Misc runtime ----
  DiagnosticsIniPath: String;
  LogFilePath: String;
  InstallStartTime: String;

#endif
