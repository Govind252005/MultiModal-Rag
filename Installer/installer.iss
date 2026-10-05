; ============================================================================
; installer.iss
; ----------------------------------------------------------------------------
; Main installer entry point for {#APP_NAME}. This file ONLY orchestrates:
; application metadata, [Files]/[Icons]/[Registry] declarations, and the
; wizard lifecycle. All business logic lives in the included modules below.
; ============================================================================

#include "constants.iss"

[Setup]
AppId={{#APP_GUID}
AppName={#APP_NAME}
AppVersion={#APP_VERSION}
AppPublisher={#APP_PUBLISHER}
AppPublisherURL={#APP_URL}
AppSupportURL={#APP_URL}
AppUpdatesURL={#APP_URL}
DefaultDirName={autopf}\{#APP_NAME_SAFE}
DefaultGroupName={#APP_NAME}
DisableProgramGroupPage=no
OutputDir={#OUTPUT_DIR}
OutputBaseFilename={#OUTPUT_BASE_FILENAME}
Compression=lzma2/ultra64
SolidCompression=yes
SetupIconFile={#ASSET_ICON}
WizardImageFile={#ASSET_WIZARD_IMAGE}
WizardSmallImageFile={#ASSET_LOGO}
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#APP_EXE_NAME}
DisableWelcomePage=no
ChangesEnvironment=yes
MinVersion=10.0.{#MIN_WINDOWS_BUILD}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
; Application payload (built by PyInstaller into dist\MultimodalRag)
Source: "{#SRC_DIST}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; Assets bundled for shortcuts / uninstall UI
Source: "{#SRC_ASSETS}\app.ico"; DestDir: "{app}\assets"; Flags: ignoreversion
Source: "{#SRC_ASSETS}\logo.png"; DestDir: "{app}\assets"; Flags: ignoreversion

; Installer support docs, kept alongside the app for reference
Source: "LICENSE.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.txt"; DestDir: "{app}"; Flags: ignoreversion

; PowerShell scripts copied to a permanent location so cleanup.ps1 survives
; for the uninstaller to use (Flags: uninsneveruninstall keeps it in place
; until the uninstaller itself deletes it after running).
Source: "scripts\cleanup.ps1"; DestDir: "{app}\installer\scripts"; Flags: ignoreversion uninsneveruninstall

; Scripts needed only during Setup are extracted to {tmp} via
; ExtractTemporaryFile(), so they are declared with Flags: dontcopy here.
Source: "scripts\diagnostics.ps1"; DestDir: "{tmp}"; Flags: dontcopy
Source: "scripts\install_ollama.ps1"; DestDir: "{tmp}"; Flags: dontcopy
Source: "scripts\download_model.ps1"; DestDir: "{tmp}"; Flags: dontcopy
Source: "scripts\first_run.ps1"; DestDir: "{tmp}"; Flags: dontcopy

[Icons]
Name: "{group}\{#APP_NAME}"; Filename: "{app}\{#APP_EXE_NAME}"; IconFilename: "{app}\{#APP_EXE_NAME}"
Name: "{group}\Uninstall {#APP_NAME}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#APP_NAME}"; Filename: "{app}\{#APP_EXE_NAME}"; IconFilename: "{app}\{#APP_EXE_NAME}"; Tasks: desktopicon

[Registry]
Root: HKLM; Subkey: "Software\{#APP_PUBLISHER}\{#APP_NAME_SAFE}"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\{#APP_PUBLISHER}\{#APP_NAME_SAFE}"; ValueType: string; ValueName: "Version"; ValueData: "{#APP_VERSION}"; Flags: uninsdeletekey

[UninstallDelete]
Type: filesandordirs; Name: "{app}\installer"

[Code]

// ----------------------------------------------------------------------------
// Module includes (order matters: dependencies first). These MUST come after
// the [Code] section header above - each module contains Pascal Script
// (var blocks / functions / procedures), and Inno Setup only accepts Pascal
// Script inside an open [Code] section. Placing these includes before [Code]
// (e.g. directly under [UninstallDelete]) fails to compile.
// ----------------------------------------------------------------------------
#include "globals.iss"
#include "logging.iss"
#include "utils.iss"
#include "checks.iss"
#include "prerequisites.iss"
#include "install_ollama.iss"
#include "download_model.iss"
#include "shortcuts.iss"
#include "firewall.iss"
#include "services.iss"
#include "first_run.iss"
#include "updater.iss"
#include "uninstall.iss"

// ---------------------------------------------------------------------------
// Custom progress page used for the long-running Ollama / model steps
// ---------------------------------------------------------------------------
var
  InstallationFailed: Boolean;

procedure InitializeWizard();
begin
  InitLogging();
  LogSection('{#APP_NAME} {#APP_VERSION} - Setup Started');

  CreateSystemCheckPage();

  ProgressPage := CreateOutputProgressPage('Setting up {#APP_NAME}',
    'Please wait while the required components are installed.');

  InstallationFailed := False;
end;

// ---------------------------------------------------------------------------
// Wizard page navigation: run diagnostics when the System Check page is
// about to be shown, and block Next if hard requirements are not met.
// ---------------------------------------------------------------------------
procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = SystemCheckPage.ID then
  begin
    WizardForm.NextButton.Enabled := False;
    SummaryMemo.Lines.Text := 'Checking your system, please wait...';
    if PerformSystemCheck() then
      WizardForm.NextButton.Enabled := True
    else
      WizardForm.NextButton.Enabled := (SummaryErrorList.Count = 0);
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;

  if CurPageID = SystemCheckPage.ID then
  begin
    if SummaryErrorList.Count > 0 then
    begin
      MsgBox('Your system does not meet the minimum requirements for {#APP_NAME}:' + #13#10#13#10 
      + SummaryErrorList.Text, mbCriticalError, MB_OK);
      Result := False;
    end;
  end;
end;

// ---------------------------------------------------------------------------
// Main installation lifecycle
// ---------------------------------------------------------------------------
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
  begin
    // File copy is about to start (handled declaratively by [Files]).
    LogSection('Copying Application Files');
  end;

  if CurStep = ssPostInstall then
  begin
    ProgressPage.Show;
    try
      // 1. Prerequisites (VC++ Redistributable)
      ProgressPage.SetText('Checking prerequisites...', '');
      InstallVCRedist();

      // 2. Install / verify Ollama
      ProgressPage.SetText('Installing Ollama...', 'This may take a few minutes.');
      if not InstallOllama() then
      begin
        InstallationFailed := True;
        LogError('Ollama installation failed. The application will not function correctly until Ollama is installed manually.');
      end;

      // 3. Download AI model
      if not InstallationFailed then
      begin
        ProgressPage.SetText('Downloading AI model...', 'This may take a while depending on your connection.');
        if not DownloadModel() then
        begin
          LogWarning('AI model download failed. You can retry from within the application.');
        end;
      end;

      // 4. Configure application (folders, config.ini, GPU/CPU mode)
      ProgressPage.SetText('Configuring application...', '');
      RunFirstRunSetup();

      // 5. Shortcuts (declarative [Icons] already handles the normal case;
      //    these calls provide a scripted fallback / repair path).
      ProgressPage.SetText('Creating shortcuts...', '');
      CreateStartMenuShortcut();
      if IsTaskSelected('desktopicon') then
        CreateDesktopShortcut();

      // 6. Firewall rule for the local API server
      ProgressPage.SetText('Configuring Windows Firewall...', '');
      AddFirewallRule();

      LogSection('Installation Completed');
      if InstallationFailed then
        LogWarning('Setup completed with warnings. See the summary above.')
      else
        LogSuccess('{#APP_NAME} {#APP_VERSION} installed successfully.');

      FinishLogging();
    finally
      ProgressPage.Hide;
    end;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
  begin
    RunUninstallCleanup();
  end;
end;

[Run]
Filename: "{app}\{#APP_EXE_NAME}"; Description: "Launch {#APP_NAME}"; Flags: nowait postinstall skipifsilent unchecked

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM ""{#APP_EXE_NAME}"" /T"; Flags: runhidden; RunOnceId: "StopAppOnUninstall"
