MULTIMODAL RAG - INSTALLER BUILD NOTES
=========================================

This directory contains the Inno Setup source for the Multimodal RAG
Windows installer. It compiles to release\MultimodalRagSetup.exe.

--------------------------------------------------------------------------
FOLDER STRUCTURE (do not change)
--------------------------------------------------------------------------
Minor Project/
  backend/                  Python/FastAPI backend source
  frontend/                 Frontend source
  assets/                   app.ico, installer.bmp, splash.png, logo.png
  installer/                This directory
    installer.iss            Main script - orchestration ONLY
    constants.iss             All #define constants
    globals.iss                All shared Pascal Script variables
    utils.iss                   Generic reusable helper functions
    logging.iss                 Central logging (installer.log)
    checks.iss                   System diagnostics + summary page
    prerequisites.iss            VC++ Redistributable
    install_ollama.iss           Ollama install only
    download_model.iss           AI model pull only
    first_run.iss                 Post-install app configuration
    updater.iss                    GitHub release version check
    firewall.iss                   Windows Firewall rule
    shortcuts.iss                  Desktop / Start Menu shortcuts
    services.iss                    App process start/stop helpers
    uninstall.iss                   Custom uninstall cleanup
    scripts/
      diagnostics.ps1               Full system info -> diagnostics.ini
      install_ollama.ps1            Verifies/starts the Ollama server
      download_model.ps1            Pulls + verifies an Ollama model
      first_run.ps1                 Creates app data folders/db
      cleanup.ps1                   Uninstall-time cleanup
    LICENSE.txt
    README.txt (this file)
  dist/MultimodalRag/        PyInstaller output (installer payload)
  release/                   Compiled MultimodalRagSetup.exe

--------------------------------------------------------------------------
BUILD PREREQUISITES
--------------------------------------------------------------------------
1. Inno Setup 6.3 or newer (https://jrsoftware.org/isinfo.php)
   - Required for the ArchitecturesInstallIn64BitMode=x64compatible syntax.
2. PyInstaller build of the app must already exist at:
     dist\MultimodalRag\MultimodalRag.exe
   and all supporting files/folders it needs at runtime.
3. Assets must exist at:
     assets\app.ico
     assets\installer.bmp   (164x314 wizard sidebar image)
     assets\splash.png
     assets\logo.png        (55x58 small wizard image)

--------------------------------------------------------------------------
BUILDING
--------------------------------------------------------------------------
Command line:
  "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\installer.iss

Or open installer\installer.iss in the Inno Setup Compiler IDE and press
Build (Ctrl+F9). Output is written to release\MultimodalRagSetup.exe.

--------------------------------------------------------------------------
WHAT THE INSTALLER DOES
--------------------------------------------------------------------------
Welcome -> License -> Choose Folder -> Desktop Shortcut Task ->
System Check (CPU/RAM/Disk/Internet/GPU/CUDA/VC++/Windows version) ->
Copy Application Files -> Install Ollama (if missing) -> Download AI
Model -> Configure Application (GPU/CPU mode, config.ini, data folders) ->
Create Shortcuts -> Configure Firewall -> Finish (optional launch).

All steps are logged to:
  %LocalAppData%\MultimodalRag\Logs\installer.log

--------------------------------------------------------------------------
DESIGN RULES FOR CONTRIBUTORS
--------------------------------------------------------------------------
- One responsibility per file. Do not add business logic to installer.iss.
- All configurable values go in constants.iss. Never hardcode.
- All shared state goes in globals.iss. No logic in that file.
- Every module logs through logging.iss (LogInfo/LogWarning/LogError/
  LogSuccess/LogSection). Never use MsgBox() for routine success messages.
- install_ollama.iss never touches models. download_model.iss never
  touches the Ollama installer itself. Keep concerns separated.
- PowerShell scripts do the heavy lifting (system queries, downloads,
  process management); .iss modules call them and interpret results.
