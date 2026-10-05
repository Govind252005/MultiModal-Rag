# Multimodal Offline RAG — Full Setup Guide (Ubuntu Linux & WSL)

This is the complete, step-by-step guide to install, run, and demo the whole
project on **Ubuntu Linux** — either a native Ubuntu machine/server or
**WSL 2** (Ubuntu) on Windows. Every command is copy-paste ready for a Linux
CLI.

Everything runs **fully offline** after the one-time model downloads.

> The code itself is already cross-platform (all paths use `pathlib`, the
> device is auto-detected as CUDA or CPU, and the only Windows-specific path —
> Tesseract — is guarded so Linux just uses the `tesseract` on your `PATH`).
> **No source changes are needed to run on Ubuntu.** This guide is only about
> installing the right system packages and following the run steps.

> Tested target: Ubuntu 22.04 / 24.04 (and the same versions under WSL 2).
> First-time install is roughly 30–60 min depending on internet speed
> (the AI models are large).

---

## 0. What you are installing (the big picture)

| Piece | What it does | How it's installed on Ubuntu |
|-------|--------------|------------------------------|
| **Python 3.10+** | Runs the backend | `apt` (usually preinstalled) |
| **Node.js 18+** | Runs the React frontend | NodeSource `apt` repo |
| **Ollama** | Serves the local LLM (Qwen3) | official install script |
| **Tesseract OCR** | Reads text inside images | `apt` |
| **FFmpeg** | Audio decoding for Whisper | `apt` |
| **Poppler** | PDF→image for `pdf2image` | `apt` (`poppler-utils`) |
| **PyTorch (CUDA or CPU)** | GPU/CPU math for models | `pip` |
| **Python libs** | Chroma, sentence-transformers, faster-whisper, etc. | `pip` |
| **Frontend libs** | React, Vite, Tailwind | `npm` |

The AI models (multilingual MiniLM text embedder, CLIP, BLIP caption, Whisper,
Qwen3) download automatically on first use and cache under
`~/.cache/huggingface`. **You need internet only for that first download** —
after that it runs fully offline.

---

## Section A — WSL users only (skip if you're on native Ubuntu)

If you're on a Linux machine or server already, jump to **Section 1**.

### A.1 Install WSL 2 with Ubuntu (run in Windows PowerShell as Administrator)

```powershell
wsl --install -d Ubuntu
```

Reboot if prompted. On first launch Ubuntu asks you to create a Linux username
and password (this is separate from your Windows login).

Confirm you're on WSL **2** (not 1):

```powershell
wsl -l -v
```

The `VERSION` column should say `2`. If it says `1`, run
`wsl --set-version Ubuntu 2`.

### A.2 Open the Ubuntu terminal

Launch **"Ubuntu"** from the Start menu (or type `wsl` in PowerShell). Every
command from Section 1 onward runs **inside this Ubuntu shell**.

### A.3 Where your project files live

Your Windows project folder is visible inside WSL under `/mnt/c/...`:

```bash
cd "/mnt/c/Users/Govind/Claude/Projects/Minor Project"
```

> ⚠️ **Performance tip:** running heavy Python/Node workloads directly on
> `/mnt/c` is noticeably slower because it crosses the Windows↔Linux file
> boundary. For the best speed, copy the project into the Linux filesystem
> instead:
> ```bash
> mkdir -p ~/projects && cp -r "/mnt/c/Users/Govind/Claude/Projects/Minor Project" ~/projects/
> cd ~/projects/"Minor Project"
> ```
> Then work from `~/projects/Minor Project`. (If you do this, remember it's a
> **copy** — edits there won't sync back to the Windows folder automatically.)

### A.4 GPU on WSL (optional)

WSL 2 can use your NVIDIA GPU if you have an up-to-date **Windows** NVIDIA
driver (the one with WSL/CUDA support). You do **not** install a Linux NVIDIA
driver inside WSL — only the CUDA-enabled PyTorch wheel (Section 2.2). If the
GPU isn't detected, everything still runs on CPU, just slower.

---

## 1. Install the base system tools

Run these in the Ubuntu terminal.

### 1.1 Update apt and install system packages

```bash
sudo apt update
sudo apt install -y \
  python3 python3-venv python3-pip \
  build-essential \
  tesseract-ocr tesseract-ocr-hin \
  ffmpeg \
  poppler-utils \
  git curl
```

What these are for:
- `python3-venv` / `python3-pip` — Python virtual environments + pip.
- `build-essential` — C toolchain some Python wheels need to build.
- `tesseract-ocr` (+ `tesseract-ocr-hin` for Hindi) — OCR text inside images.
- `ffmpeg` — audio decoding for `faster-whisper`.
- `poppler-utils` — provides `pdftoppm`, required by `pdf2image`.

Verify the key ones:

```bash
python3 --version        # 3.10+ expected
tesseract --version
ffmpeg -version | head -n 1
pdftoppm -v              # from poppler-utils
```

> The backend's `TESSERACT_CMD` defaults to plain `tesseract` on Linux, so as
> long as the command above works, OCR is configured — nothing else to set.

### 1.2 Node.js 18+ (for the frontend)

Ubuntu's default `apt` Node can be old. Install a current LTS from NodeSource:

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
node --version           # v20.x expected
npm --version
```

### 1.3 Ollama (the local LLM server)

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Start it (on native Ubuntu it's typically a systemd service already; under WSL
you usually start it manually):

```bash
# Native Ubuntu with systemd:
sudo systemctl enable --now ollama

# WSL (no systemd by default) — run in its own terminal and leave it open:
ollama serve
```

Pull the model (one-time, ~4.7 GB). This project ships a helper script:

```bash
bash scripts/pull-models-unix.sh
# equivalent to:  ollama pull qwen3:8b
```

> 💡 If generation feels slow (small GPU or CPU-only), use a lighter model:
> ```bash
> ollama pull qwen3:4b
> ```
> then set `LLM_MODEL=qwen3:4b` (see section 5).

Test it:

```bash
ollama run qwen3:8b "say hello in one word"
```

---

## 2. Backend setup

From the project root, go into `backend`:

```bash
cd backend
```

### 2.1 Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

You should now see `(venv)` at the start of your prompt.

### 2.2 Install PyTorch FIRST (before requirements.txt)

Pick **one** of the following depending on your hardware.

**With an NVIDIA GPU (CUDA 12.1 build):**

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

**CPU-only (no NVIDIA GPU, or a Linux server without one):**

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
```

Verify device detection:

```bash
python -c "import torch; print('CUDA:', torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU mode')"
```

> `CUDA: False` is fine — the backend's `DEVICE` auto-falls back to CPU. It's
> just slower for embeddings/Whisper/BLIP.

### 2.3 Install the rest of the Python libraries

```bash
pip install -r requirements.txt
```

### 2.4 First run — warm up the models

Download + cache the text and image embedders (and confirm imports work):

```bash
python -c "from retrieval import embeddings; embeddings.warmup(); print('models ready')"
```

This pulls the multilingual MiniLM text embedder + CLIP (~600 MB total) into
`~/.cache/huggingface`. BLIP (captioning) and Whisper (audio) download on first
image/audio ingest.

---

## 3. Run the backend

Still in `backend/` with the venv active:

```bash
uvicorn main:app --reload --port 8000
```

- API docs (interactive): <http://localhost:8000/docs>
- Health check: <http://localhost:8000/api/health>

Leave this terminal running.

> **LAN / server access:** to reach it from other machines, bind all
> interfaces: `uvicorn main:app --host 0.0.0.0 --port 8000`. On WSL, the app is
> also reachable from Windows at `http://localhost:8000` automatically.

---

## 4. Run the frontend

Open a **second** Ubuntu terminal, go to `frontend/`:

```bash
cd "<project root>/frontend"
npm install        # one-time, downloads React/Vite/etc.
npm run dev
```

Open the app: **<http://localhost:5173>**

The dev server proxies all `/api/...` calls to the backend on port 8000, so
both must be running together.

### 4.1 Production mode (one server, no dev proxy)

To serve the built frontend from the backend itself (single port 8000), use the
included script from the project root:

```bash
bash scripts/run-unix.sh
```

This builds `frontend/dist` (if missing) and launches uvicorn on `0.0.0.0:8000`
serving both the API and the compiled UI. `config.py` already points
`STATIC_DIR` at `frontend/dist`, so the app is served at
<http://localhost:8000>.

---

## 5. Configuration knobs (optional)

Everything lives in `backend/config.py`, and the useful values are
environment-overridable. Set them before launching uvicorn:

```bash
export LLM_MODEL="qwen3:4b"       # smaller/faster LLM
export WHISPER_MODEL="base"          # faster transcription (tiny/base/small/medium)
export OLLAMA_HOST="http://localhost:11434"
export REDIS_URL="redis://localhost:6379/0"
uvicorn main:app --reload --port 8000
```

Other tunables: `CHUNK_SIZE_WORDS`, `DEFAULT_TOP_K`, `AUDIO_CHUNK_SECONDS`,
`LLM_TEMPERATURE`, `OCR_ENGINE` (`paddleocr` default, or `tesseract`).

### 5.1 Redis (optional cache)

Redis is only used as a cache/session layer and the app runs without it. If you
want it:

```bash
sudo apt install -y redis-server
sudo systemctl enable --now redis-server   # native Ubuntu
# WSL without systemd:  sudo service redis-server start
redis-cli ping        # -> PONG
```

### 5.2 Advanced Phase-3 features (all OFF by default)

These are opt-in and disabled unless you set the flag. Enable per need:

```bash
export QUERY_REWRITE_ENABLED=1     # rewrite follow-ups into standalone queries
export HYDE_ENABLED=1              # hypothetical-document embedding for dense recall
export MULTIHOP_ENABLED=1          # decompose complex questions into sub-questions
export COLBERT_ENABLED=1           # late-interaction rerank (needs: pip install ragatouille)
```

Leaving them unset keeps the retrieval pipeline byte-for-byte identical to the
default behavior.

---

## 6. Command-line testing (no frontend needed)

With the venv active, in `backend/`:

```bash
# Ingest a single file or a whole folder
python -m ingestion.ingest "/path/to/some_report.pdf"
python -m ingestion.ingest "/path/to/a_folder_of_files"
```

Then hit the API directly, or open <http://localhost:8000/docs> and try
`/api/ingest`, `/api/query`, `/api/query/image`, etc. interactively.

Quick health/query smoke test with `curl`:

```bash
curl http://localhost:8000/api/health
```

---

## 7. Troubleshooting (Linux/WSL specific)

| Symptom | Fix |
|--------|-----|
| `tesseract: command not found` | `sudo apt install -y tesseract-ocr tesseract-ocr-hin` |
| `pdf2image` errors / `Unable to get page count` | Install Poppler: `sudo apt install -y poppler-utils` |
| Whisper audio decode error | Install FFmpeg: `sudo apt install -y ffmpeg` |
| Answer says *"LLM unavailable"* | Ollama not running/model not pulled. Run `ollama list`; start with `ollama serve` (WSL) or `sudo systemctl start ollama`. |
| `Cannot reach the backend` in UI | Ensure `uvicorn` is running on port 8000. |
| `CUDA: False` but you have a GPU | Update the **Windows** NVIDIA driver (WSL) or install the CUDA PyTorch wheel; otherwise CPU mode still works. |
| Ollama won't start on WSL | WSL has no systemd by default — just run `ollama serve` in a dedicated terminal. |
| Very slow file access on WSL | Move the project off `/mnt/c` into the Linux home (`~/projects/...`) — see A.3. |
| `npm run build` fails on native Linux | Delete `frontend/node_modules` and re-run `npm install` **on this Linux machine** so it fetches Linux-native binaries. |
| First query is very slow | Normal — models load into memory once; later queries are fast. |
| Out of GPU memory | Use `qwen3:4b` and `WHISPER_MODEL=base`. |
| Want to start fresh | `POST /api/reset` (or delete `backend/storage/`). |

> **Note on `node_modules`:** if you copied this project from a Windows machine
> where `npm install` was already run, the `node_modules` there contains
> **Windows** binaries (e.g. rollup). On a real Linux box you must re-run
> `npm install` inside `frontend/` so npm downloads the Linux builds.

---

## 8. Quick reference — full clean install (copy-paste)

For a fresh Ubuntu 22.04/24.04 (native or WSL), from the project root:

```bash
# 1. System packages
sudo apt update
sudo apt install -y python3 python3-venv python3-pip build-essential \
  tesseract-ocr tesseract-ocr-hin ffmpeg poppler-utils git curl

# 2. Node.js 20 LTS
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# 3. Ollama + model
curl -fsSL https://ollama.com/install.sh | sh
ollama serve &                      # or: sudo systemctl enable --now ollama
bash scripts/pull-models-unix.sh

# 4. Backend
cd backend
python3 -m venv venv && source venv/bin/activate
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu   # or cu121 for GPU
pip install -r requirements.txt
python -c "from retrieval import embeddings; embeddings.warmup(); print('models ready')"
uvicorn main:app --host 0.0.0.0 --port 8000

# 5. Frontend (second terminal, from project root)
cd frontend && npm install && npm run dev
```

Open **<http://localhost:5173>** (dev) or **<http://localhost:8000>**
(production via `scripts/run-unix.sh`).

---

## 9. What was verified for Linux

- The codebase uses `pathlib` for all paths and auto-creates its data/store
  directories, so nothing is hard-coded to a Windows drive.
- `DEVICE` auto-detects CUDA and falls back to CPU — the same code runs on a
  GPU laptop or a CPU-only server.
- The only OS-specific line (`TESSERACT_CMD`) is guarded by `os.name == "nt"`;
  on Linux it defaults to the `tesseract` on your `PATH`.
- Required system packages (`tesseract-ocr`, `ffmpeg`, `poppler-utils`) match
  what the project's `backend/Dockerfile` already installs, so behavior is
  consistent between a manual Ubuntu install and the container.

No application source changes are needed to run on Ubuntu — this guide covers
the environment only.
