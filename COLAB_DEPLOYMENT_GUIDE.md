# Colab Deployment Guide

This guide explains how to run the existing Multimodal Offline RAG project on Google Colab with GPU acceleration while keeping the current architecture mostly intact.

## 1. Project overview

This repository already contains a working multimodal RAG stack:

- React frontend in `frontend/`
- FastAPI backend in `backend/`
- ChromaDB as the embedded vector database
- local LLM via Ollama
- text and visual embeddings
- document, image, and audio ingestion

The main Colab adaptation is not a rewrite of the app. It is mostly about:

- moving writable data to Google Drive
- exposing the backend through a public tunnel
- running the app in a notebook environment
- handling local `localhost` assumptions
- adjusting model runtime settings for GPU

## 2. What stays the same

These parts can remain mostly unchanged:

- FastAPI backend structure in `backend/main.py`
- vector retrieval logic in `backend/retrieval/search.py`
- Chroma usage in `backend/retrieval/vector_store.py`
- ingestion logic in `backend/ingestion/ingest.py`
- frontend app structure in `frontend/src/`
- API contracts between frontend and backend

## 3. What changes for Colab

The project currently assumes a local machine runtime:

- `http://localhost:11434` for Ollama in `backend/config.py`
- `http://localhost:8000` in `frontend/vite.config.ts`
- local file storage under the project tree
- local Tesseract installation

In Colab, these become environment-driven values and public URLs.

## 4. Recommended Colab architecture

For a simple and reliable setup:

```text
User Browser
    ↓
React Frontend (optional local or dev build)
    ↓
Public HTTPS tunnel (ngrok / Cloudflare)
    ↓
Google Colab
    ↓
FastAPI backend
    ↓
Hybrid retrieval pipeline
    ↓
GPU-backed model inference
```

## 5. Project folder strategy

Use this structure inside the Colab runtime:

```text
/content/
  project/
    backend/
    frontend/
    .env
    data/
    storage/
    logs/
    models/
```

Persistent state should live in Google Drive:

```text
/content/drive/MyDrive/MultimodalRag/
  backend/
  data/
  storage/
  models/
  logs/
```

Recommended mapping:

- source code: `/content/project`
- documents/uploads: Drive folder
- vector DB: Drive folder
- model cache: Drive folder
- generated logs: Drive folder
- temporary runtime files: `/tmp` or Colab ephemeral storage

## 6. Mount Google Drive

Run this in a Colab notebook:

```python
from google.colab import drive

drive.mount('/content/drive')

PROJECT_ROOT = '/content/drive/MyDrive/MultimodalRag'
!mkdir -p "$PROJECT_ROOT"
print("Drive mounted:", PROJECT_ROOT)
```

Then clone or copy the repo into your working directory:

```bash
cd /content
git clone https://github.com/Govind252005/Rag.git project
cd project
```

If you want to keep the project inside Drive and sync it there instead, use a Drive-backed working folder:

```bash
cd /content/drive/MyDrive/MultimodalRag
# then copy your project here or git clone here
```

## 7. Set environment variables for Colab

Use environment variables instead of hardcoded local values.

```python
import os

os.environ['RAG_DATA_HOME'] = '/content/drive/MyDrive/MultimodalRag'
os.environ['OLLAMA_HOST'] = 'http://localhost:11434'
os.environ['LLM_MODEL'] = 'qwen3:8b'
os.environ['DEFAULT_PROVIDER'] = 'ollama'
os.environ['OCR_ENGINE'] = 'paddleocr'
```

The project already reads many values from environment variables in `backend/config.py`, so this is the correct Colab pattern.

## 8. GPU validation

Check that the Colab runtime is actually using a GPU:

```python
import torch

print('CUDA available:', torch.cuda.is_available())
print('Device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')
print('Device count:', torch.cuda.device_count())

x = torch.randn(2, 3).cuda()
print('Tensor device:', x.device)
```

Expected result:

- `CUDA available: True`
- device name such as `Tesla T4`, `L4`, or `A100`
- tensor device prints `cuda:0`

## 9. Install dependencies in the correct order

Do not use a blind one-line install if you want fewer dependency problems.

```bash
!pip install --upgrade pip setuptools wheel
!pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
!pip install sentence-transformers==3.3.1
!pip install transformers==4.47.1
!pip install chromadb
!pip install fastapi==0.115.6 uvicorn[standard]==0.34.0 python-multipart==0.0.20
!pip install "pydantic>=2.12.5" "pydantic-settings>=2.7.1"
!pip install paddleocr==3.7.0 pytesseract==0.3.13 pdf2image==1.17.0
!pip install faster-whisper==1.1.0
!pip install PyMuPDF==1.25.1 python-docx==1.1.2
!pip install "ollama>=0.5.1"
!pip install "google-genai>=0.3.0" "openai>=1.0.0" "anthropic>=0.30.0" "groq>=0.9.0"
!pip install "cryptography>=42.0.0"
!pip install numpy==1.26.4 python-dotenv==1.0.1 rank-bm25==0.2.2 redis==5.0.8
```

Install OCR system dependency too:

```bash
!apt-get update
!apt-get install -y tesseract-ocr
```

## 10. Start the backend in Colab

From the project root:

```bash
cd /content/project/backend
!uvicorn main:app --host 0.0.0.0 --port 8000
```

For a persistent notebook run, use a background process:

```python
import subprocess, os

backend_cmd = ['uvicorn', 'main:app', '--host', '0.0.0.0', '--port', '8000']
proc = subprocess.Popen(backend_cmd, cwd='/content/project/backend', stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
print('Backend process started with PID:', proc.pid)
```

Then verify the health endpoint:

```python
import requests

resp = requests.get('http://127.0.0.1:8000/api/health')
print(resp.status_code)
print(resp.json())
```

## 11. Expose the backend publicly

The simplest approach is `ngrok`.

```bash
!pip install pyngrok
```

Then:

```python
from pyngrok import ngrok

public_url = ngrok.connect(8000, 'http')
print(public_url)
print(public_url.public_url)
```

Use the returned public URL as the backend location for your frontend or external clients.

## 12. Frontend integration for Colab

The frontend is designed to call relative `/api` paths during local dev, as shown in `frontend/vite.config.ts`.

For Colab, you should change the API base to the public backend URL or set a runtime environment variable.

### Option A: keep the frontend local

Run the Vite app locally on your machine and point it to the public Colab backend:

```bash
cd frontend
npm install
VITE_API_BASE=https://<your-ngrok-url> npm run dev
```

Then update the client to use the environment variable instead of `/api` only.

### Option B: run frontend in Colab too

```bash
cd /content/project/frontend
!npm install
!npm run dev -- --host 0.0.0.0 --port 5173
```

Then expose the frontend port with another tunnel if needed.

## 13. Update frontend API base

The project currently uses relative URLs in `frontend/src/api.ts`, which is correct for local Vite proxying. For Colab, you should either:

- set a runtime base URL override,
- or replace relative calls with explicit remote URL values.

Example approach:

```ts
const API_BASE = import.meta.env.VITE_API_BASE || ''

fetch(`${API_BASE}/api/health`)
```

## 14. CORS configuration

The FastAPI backend already includes a permissive CORS middleware in `backend/main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=False,
    allow_methods=['*'],
    allow_headers=['*'],
)
```

This is enough for a browser frontend hitting the Colab backend.

## 15. Persistent storage strategy

Store all heavy or long-lived data in Google Drive:

```bash
mkdir -p /content/drive/MyDrive/MultimodalRag/data
mkdir -p /content/drive/MyDrive/MultimodalRag/storage/chroma
mkdir -p /content/drive/MyDrive/MultimodalRag/models
mkdir -p /content/drive/MyDrive/MultimodalRag/logs
```

Then ensure the backend uses those paths.

## 16. Ollama on Colab

This project is written around Ollama in `backend/config.py`:

```python
OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
LLM_MODEL = os.getenv('LLM_MODEL', 'qwen3:8b')
```

This works in Colab if you run Ollama in the same runtime or if you keep the metadata consistent with a local service. For a more robust Colab GPU setup, direct Transformers-based model loading is often easier to manage than Ollama.

## 17. Best-practice recommendation

For this repository, the most reliable deployment pattern is:

1. keep the current backend logic
2. mount Drive for persistence
3. run backend directly with uvicorn
4. expose through ngrok
5. keep the frontend local or run it separately
6. use a smaller Qwen model if memory is tight
7. keep the existing API contract intact

## 18. Common errors and fixes

### Error: local endpoints fail

Cause: backend still points to localhost in config or frontend.

Fix:

- set `OLLAMA_HOST` to the correct service URL
- point frontend to public backend URL

### Error: GPU is not detected

Fix:

```python
import torch
print(torch.cuda.is_available())
```

If false, runtime type needs to be changed or CUDA-enabled environment used.

### Error: model loading takes too long or runs out of memory

Fix:

- switch to a smaller model
- lower `LLM_NUM_CTX`
- run with quantization
- reduce batch sizes

### Error: CORS or frontend cannot reach backend

Fix:

- validate the public URL from ngrok
- confirm backend port is 8000
- keep CORS on the backend

### Error: uploaded files disappear after runtime restart

Fix:

- store documents and vector database in Drive
- ensure `RAG_DATA_HOME` points to persistent storage

## 19. Final Colab deployment checklist

Before running the app:

- [ ] Google Drive mounted
- [ ] project copied to Colab
- [ ] Python packages installed
- [ ] GPU detected
- [ ] backend env variables set
- [ ] model available or loaded
- [ ] backend started on port 8000
- [ ] public tunnel created
- [ ] frontend hitting the public backend URL
- [ ] Drive persistence enabled

## 20. Production-ready recommendation

For a real Colab deployment of this project, use this path:

- backend on Colab
- GPU-enabled runtime
- Drive-backed storage
- ngrok or Cloudflare tunnel
- local or separate frontend
- minimal changes to the existing architecture

This preserves the current app behavior while making it possible to run it in a GPU environment without rebuilding the project from scratch.
