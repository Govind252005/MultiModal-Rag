# Deployment & Sharing Guide

Two ways to share this so another person can run it **locally and offline** on
their own machine. Pick whichever suits them.

---

## Option A — Docker (one command, most portable)

Best when the other person just wants it to work without installing Python,
Node, Tesseract, etc. They only need **Docker Desktop**.

```bash
# 1. Copy/clone the whole project folder to their machine
# 2. From the project root:
docker compose up -d --build

# 3. Pull the LLM once (needs internet ONCE, then fully offline):
docker compose exec ollama ollama pull qwen3:8b
```

Open **http://localhost:8080**.

- Everything (Ollama + backend + frontend) runs in containers.
- Models, the vector index, and uploads persist in Docker volumes, so it stays
  offline and keeps data across restarts.
- **GPU (optional):** install the NVIDIA Container Toolkit and uncomment the
  `deploy.resources` block under the `ollama` service in `docker-compose.yml`.
  Without it, it runs on CPU (slower but works).

Stop / start:
```bash
docker compose down          # stop
docker compose up -d         # start again (no rebuild)
```

---

## Option B — Native scripts (best performance, uses their GPU)

Best when the person is technical / wants full GPU speed. Requires the one-time
setup from **SETUP_GUIDE.md** (Python, Node, Ollama, Tesseract, PyTorch-CUDA).

**Windows**
```bat
scripts\pull-models-windows.bat     :: one-time: pull the LLM
scripts\run-windows.bat             :: build frontend + serve everything on :8000
```
Open **http://localhost:8000**.

For development with hot-reload instead:
```bat
scripts\dev-windows.bat             :: backend :8000 + Vite :5173
```

**macOS / Linux**
```bash
./scripts/pull-models-unix.sh
./scripts/run-unix.sh
```

In production mode the FastAPI backend serves the built React app itself
(from `frontend/dist`), so there's a single URL and a single process.

---

## Sharing on the same Wi-Fi (LAN) — test on your phone

Both options bind to `0.0.0.0`, so other devices on the same network can reach
your machine:

1. Find your machine's IP:
   - Windows: `ipconfig` → "IPv4 Address" (e.g. `192.168.1.42`)
   - macOS/Linux: `hostname -I` or `ifconfig`
2. On the phone/other laptop, open:
   - Docker:  `http://192.168.1.42:8080`
   - Native:  `http://192.168.1.42:8000`
3. Allow the port through Windows Firewall the first time if prompted.

The UI is mobile-responsive, so it works on a phone screen.

---

## What "offline" means here

After the **first** run downloads the models (LLM via Ollama, plus the
embedding / CLIP / BLIP / Whisper models via HuggingFace), you can disconnect
from the internet entirely and everything keeps working — ingestion, search,
transcription, and answering are all local.

To pre-bundle models for a truly air-gapped machine, copy these folders from a
machine that has already run it once:
- Ollama models:  `~/.ollama` (or the `ollama_models` Docker volume)
- HF model cache: `~/.cache/huggingface` (or the `hf_cache` Docker volume)
