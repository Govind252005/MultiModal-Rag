; ============================================================================
; constants.iss
; ----------------------------------------------------------------------------
; Single source of truth for every configurable value used by the installer.
; NOTHING in this file may contain logic. #define only.
; ============================================================================

#ifndef CONSTANTS_ISS
#define CONSTANTS_ISS

; ---------------------------------------------------------------------------
; Application identity
; ---------------------------------------------------------------------------
#define APP_NAME "Multimodal RAG"
#define APP_NAME_SAFE "MultimodalRag"
#define APP_VERSION "1.0.0"
#define APP_PUBLISHER "Govind"
#define APP_URL "https://example.com/multimodal-rag"
#define APP_EXE_NAME "MultimodalRag.exe"
#define APP_GUID "{A7B9C2E1-4F3D-4A6B-9E2C-1D8F5A6B7C90}"

; ---------------------------------------------------------------------------
; Paths (relative to installer source tree, resolved at compile time)
; ---------------------------------------------------------------------------
#define SRC_ROOT "..\"
#define SRC_BACKEND SRC_ROOT + "backend"
#define SRC_FRONTEND SRC_ROOT + "frontend"
#define SRC_ASSETS SRC_ROOT + "assets"
#define SRC_DIST SRC_ROOT + "dist\MultimodalRag"

#define ASSET_ICON SRC_ASSETS + "\app.ico"
#define ASSET_WIZARD_IMAGE SRC_ASSETS + "\installer.bmp"
#define ASSET_SPLASH SRC_ASSETS + "\splash.png"
#define ASSET_LOGO SRC_ASSETS + "\logo.png"

; ---------------------------------------------------------------------------
; Output
; ---------------------------------------------------------------------------
#define OUTPUT_DIR SRC_ROOT + "release"
#define OUTPUT_BASE_FILENAME "MultimodalRagSetup"

; ---------------------------------------------------------------------------
; Ollama
; ---------------------------------------------------------------------------
#define OLLAMA_DOWNLOAD_URL "https://ollama.com/download/OllamaSetup.exe"
#define OLLAMA_INSTALLER_FILENAME "OllamaSetup.exe"
#define OLLAMA_EXPECTED_INSTALL_PATH "{localappdata}\Programs\Ollama\ollama.exe"
#define OLLAMA_SERVICE_PORT "11434"
#define OLLAMA_STARTUP_TIMEOUT_SEC "60"

; ---------------------------------------------------------------------------
; AI Model
; ---------------------------------------------------------------------------
#define DEFAULT_MODEL "qwen3:8b"
#define DEFAULT_MODEL_FALLBACK "qwen2.5:3b"
#define MODEL_DOWNLOAD_MAX_RETRIES "3"
#define MODEL_DOWNLOAD_TIMEOUT "1800"

; ---------------------------------------------------------------------------
; Application runtime defaults
; ---------------------------------------------------------------------------
#define DEFAULT_PORT "8000"
#define DEFAULT_HOST "127.0.0.1"

; ---------------------------------------------------------------------------
; Network
; ---------------------------------------------------------------------------
#define DOWNLOAD_TIMEOUT "300"
#define INTERNET_CHECK_URL "https://ollama.com"

; ---------------------------------------------------------------------------
; System requirements
; ---------------------------------------------------------------------------
#define MIN_RAM_GB "8"
#define RECOMMENDED_RAM_GB "16"
#define MIN_DISK_GB "15"
#define MIN_WINDOWS_BUILD "17763"

; ---------------------------------------------------------------------------
; Prerequisites
; ---------------------------------------------------------------------------
#define VCREDIST_URL "https://aka.ms/vs/17/release/vc_redist.x64.exe"
#define VCREDIST_FILENAME "vc_redist.x64.exe"
#define VCREDIST_REGISTRY_KEY "SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\X64"

; ---------------------------------------------------------------------------
; Logging
; ---------------------------------------------------------------------------
#define LOG_DIRECTORY "{localappdata}\MultimodalRag\Logs"
#define LOG_FILE "installer.log"
#define DIAGNOSTICS_INI_NAME "diagnostics.ini"

; ---------------------------------------------------------------------------
; Application data directories (created at first run)
; ---------------------------------------------------------------------------
#define APP_DATA_DIR "{localappdata}\MultimodalRag"
#define APP_CONFIG_DIR APP_DATA_DIR + "\Config"
#define APP_DB_DIR APP_DATA_DIR + "\Data"
#define APP_MODELS_DIR APP_DATA_DIR + "\Models"
#define APP_CONFIG_FILE "config.ini"

; ---------------------------------------------------------------------------
; Updater
; ---------------------------------------------------------------------------
#define UPDATE_GITHUB_API "https://api.github.com/repos/YOUR_ORG/multimodal-rag/releases/latest"
#define UPDATE_CHECK_ENABLED "true"

; ---------------------------------------------------------------------------
; Firewall
; ---------------------------------------------------------------------------
#define FIREWALL_RULE_NAME "Multimodal RAG"

#endif
