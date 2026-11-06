# Enterprise Production Deployment Guide

## 1. System Requirements

### Hardware Requirements
- **Minimum**: 4 CPU cores, 16 GB RAM, 20 GB SSD storage.
- **Recommended (Local GPU Acceleration)**: 8+ CPU cores, 32 GB RAM, NVIDIA RTX 3060 / 4060 or better with 8 GB+ VRAM (CUDA 12.x+), 50 GB NVMe SSD.

### Software Prerequisites
- **Operating System**: Windows 10/11 64-bit, Ubuntu 22.04/24.04 LTS, or macOS 13+ (Apple Silicon).
- **Python**: 3.10 to 3.12 64-bit.
- **Node.js**: v18.x or v20.x LTS + npm.
- **Ollama**: v0.3.0+ for serving local models (`qwen3:4b` or `qwen2.5:7b`).

---

## 2. Local Ollama Model Setup

1. Install Ollama from [ollama.com](https://ollama.com).
2. Start the Ollama background service:
   ```bash
   ollama serve
   ```
3. Pull the recommended local models:
   ```bash
   ollama pull qwen3:4b
   ```

---

## 3. Backend Setup & Configuration

1. Set up a virtual environment and install dependencies:
   ```bash
   python -m venv backend/venv
   # Windows:
   .\backend\venv\Scripts\activate
   # Linux/macOS:
   source backend/venv/bin/activate

   pip install -r backend/requirements.txt
   ```
2. Configure environment variables:
   ```bash
   cp .env.example .env
   ```
   Key environment variables:
   - `OLLAMA_HOST=http://localhost:11434`
   - `LLM_MODEL=qwen3:4b`
   - `TEXT_EMBED_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
   - `ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173`

---

## 4. Frontend Production Build

1. Install dependencies:
   ```bash
   cd frontend
   npm install
   ```
2. Build the optimized static bundle:
   ```bash
   npm run build
   ```
   The production assets are compiled into `frontend/dist/`.

---

## 5. Running the Application

### Native Single-Process Mode (FastAPI serves built frontend)
```bash
# Windows
.\scripts\run-windows.bat

# Linux/macOS
./scripts/run-unix.sh
```
Open **http://localhost:8000** in your browser.

### Development Mode (Hot-Reload)
```bash
# Windows
.\scripts\dev-windows.bat
```
Backend runs on **http://localhost:8000**, frontend Vite dev server runs on **http://localhost:5173**.

---

## 6. Enterprise Backup & Disaster Recovery

The system includes automated backup and restore capabilities:
```python
from backend.backup_manager import create_backup, restore_backup
from pathlib import Path

# Create an encrypted snapshot
archive = create_backup(Path("backups/snapshot_20261106.zip"))

# Restore to destination
restore_backup(
    archive_path=Path("backups/snapshot_20261106.zip"),
    target_data_dir=Path("data/"),
    target_store_dir=Path("storage/")
)
```
