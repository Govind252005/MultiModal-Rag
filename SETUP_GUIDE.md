# Multimodal Offline RAG — Full Setup Guide (Windows)

This is the complete, step-by-step guide to install, run, and demo the whole
project on your Windows laptop (i7-12650H, 16 GB RAM, 4 GB NVIDIA GPU).

Everything runs **fully offline** after the one-time model downloads.

> Follow the sections **in order** the first time. Total install time is
> roughly 30–60 min depending on your internet speed (models are big).

---

## 0. What you are installing (the big picture)

| Piece | What it does | How it's installed |
|-------|--------------|--------------------|
| **Python 3.10+** | Runs the backend | python.org installer |
| **Node.js 18+** | Runs the React frontend | nodejs.org installer |
| **Ollama** | Serves the local LLM (Qwen3) | ollama.com installer |
| **Tesseract OCR** | Reads text inside images | UB-Mannheim installer |
| **PyTorch (CUDA)** | GPU math for embeddings/Whisper/BLIP | pip |
| **Python libs** | Chroma, sentence-transformers, faster-whisper, etc. | pip |
| **Frontend libs** | React, Vite, Tailwind | npm |

The AI models (BGE text embedder, CLIP, BLIP caption, Whisper, Qwen3) are
downloaded automatically on first use and cached on disk. **You need internet
only for this first download** — after that, unplug and it still works.

---

## 1. Install the base tools

### 1.1 Python
1. Download **Python 3.11** (or 3.10) from <https://www.python.org/downloads/>.
2. Run the installer. **✅ Tick "Add python.exe to PATH"** on the first screen.
3. Verify in a new terminal (PowerShell):
   ```powershell
   python --version
   ```

### 1.2 Node.js
1. Download the **LTS** version from <https://nodejs.org/>.
2. Install with defaults. Verify:
   ```powershell
   node --version
   npm --version
   ```

### 1.3 Ollama (the local LLM server)
1. Download from <https://ollama.com/download> and install.
2. Ollama runs as a background service on `http://localhost:11434`.
3. Pull the model (one-time, ~4.7 GB download):
   ```powershell
   ollama pull qwen3:8b
   ```
   > 💡 If generation feels slow on your GPU, use a smaller model instead:
   > ```powershell
   > ollama pull qwen3:4b
   > ```
   > then set `LLM_MODEL=qwen3:4b` (see section 5).
4. Test it works:
   ```powershell
   ollama run qwen3:8b "say hello in one word"
   ```

### 1.4 Tesseract OCR (text inside images)
1. Download the Windows installer from
   <https://github.com/UB-Mannheim/tesseract/wiki>.
2. Install to the **default path**: `C:\Program Files\Tesseract-OCR\`.
   (The backend already looks here. If you install elsewhere, set the
   `TESSERACT_CMD` env var — see section 5.)
3. Verify:
   ```powershell
   & "C:\Program Files\Tesseract-OCR\tesseract.exe" --version
   ```

### 1.5 (Optional) FFmpeg — only if audio decoding fails
`faster-whisper` bundles its own audio decoder, so most files (mp3/wav/m4a/webm)
work out of the box. If you hit a decode error on some audio, install FFmpeg:
- Easiest: `winget install Gyan.FFmpeg` (then reopen the terminal), or
- Download from <https://www.gyan.dev/ffmpeg/builds/> and add its `bin` to PATH.

---

## 2. Backend setup

Open PowerShell **in the `backend` folder**:
```powershell
cd "C:\Users\Govind\Claude\Projects\Minor Project\backend"
```

### 2.1 Create and activate a virtual environment
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```
> If PowerShell blocks the script, run once:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` and try again.

You should now see `(venv)` at the start of your prompt.

### 2.2 Install PyTorch with CUDA (do this BEFORE requirements.txt)
This gets the GPU build that uses your NVIDIA card:
```powershell
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```
Verify the GPU is detected:
```powershell
python -c "import torch; print('CUDA:', torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')"
```
> If it prints `CUDA: False`, that's OK — everything still runs on CPU, just
> slower. (Usually means the NVIDIA driver needs updating.)

### 2.3 Install the rest of the Python libraries
```powershell
pip install -r requirements.txt
```

### 2.4 First run — download the AI models
The models download automatically the first time you ingest or query. To warm
them up now (and confirm everything imports), run a quick smoke test:
```powershell
python -c "from retrieval import embeddings; embeddings.warmup(); print('models ready')"
```
This downloads BGE (text) + CLIP (~600 MB total) and caches them under
`C:\Users\<you>\.cache\huggingface`. BLIP and Whisper download on first
image/audio ingest.

---

## 3. Run the backend

Still in `backend/` with the venv active:
```powershell
uvicorn main:app --reload --port 8000
```
- API docs (try endpoints in the browser): <http://localhost:8000/docs>
- Health check: <http://localhost:8000/api/health>

Leave this terminal running.

---

## 4. Run the frontend

Open a **second** PowerShell in the `frontend` folder:
```powershell
cd "C:\Users\Govind\Claude\Projects\Minor Project\frontend"
npm install        # one-time, downloads React/Vite/etc.
npm run dev
```
Open the app: **<http://localhost:5173>**

The frontend proxies all `/api/...` calls to the backend on port 8000, so both
must be running together.

---

## 5. Configuration knobs (optional)

Everything is in `backend/config.py`. The most useful overrides can also be set
as environment variables before launching uvicorn:

```powershell
$env:LLM_MODEL = "qwen3:8b"        # smaller/faster LLM
$env:WHISPER_MODEL = "base"          # faster transcription (tiny/base/small/medium)
$env:TESSERACT_CMD = "D:\Tesseract\tesseract.exe"   # custom Tesseract path
uvicorn main:app --reload --port 8000
```

Other tunables in `config.py`: `CHUNK_SIZE_WORDS`, `DEFAULT_TOP_K`,
`AUDIO_CHUNK_SECONDS`, `LLM_TEMPERATURE`.

---

## 6. How to use it (demo flow)

1. **Ingest data.** In the app, click **Library** (top right) and drag in a mix
   of PDFs, DOCX, images (PNG/JPG screenshots), and audio (mp3/wav). Watch the
   chunk counts appear. (First image/audio ingest is slow — models loading.)
2. **Ask a question.** Type in the chat box, e.g.
   *"Show me the report that describes international development in 2024."*
   You get a grounded answer with **numbered citations [1][2]**.
3. **Click a citation.** The Sources panel expands it — opens the PDF page,
   shows the full transcript segment, or displays the image with its metadata.
4. **Text → image search.** Set the modality filter to *Image* and search
   *"email screenshot"* to pull matching images.
5. **Image → everything.** Use the image button in the composer to upload a
   screenshot; the system captions + OCRs it and finds related docs/audio.
6. **Audio → everything.** Attach an audio clip; it's transcribed, then used to
   retrieve related text/images.
7. **Voice query.** Click the mic, speak your question; it's transcribed into
   the search box, then run as a normal query.

---

## 7. Test the backend WITHOUT the frontend (great for debugging)

With the venv active, in `backend/`:

```powershell
# Ingest a file or a whole folder from the command line
python -m ingestion.ingest "C:\path\to\some_report.pdf"
python -m ingestion.ingest "C:\path\to\a_folder_of_files"

# Then hit the API directly (or use http://localhost:8000/docs)
```

You can also open <http://localhost:8000/docs> and try `/api/ingest`,
`/api/query`, `/api/query/image`, etc. interactively.

---

## 8. Troubleshooting

| Symptom | Fix |
|--------|-----|
| `Cannot reach the backend` in the UI | Make sure `uvicorn` is running on port 8000. |
| Answer says *"LLM unavailable"* | Ollama isn't running or model not pulled. Run `ollama list`, then `ollama pull qwen3:8b`. |
| OCR returns nothing / Tesseract error | Tesseract not installed or wrong path. Check section 1.4 / set `TESSERACT_CMD`. |
| `CUDA: False` | Update NVIDIA drivers, or just accept CPU mode (slower but works). |
| Whisper audio decode error | Install FFmpeg (section 1.5). |
| First query is very slow | Normal — models load into memory once. Later queries are fast. |
| Out of GPU memory | Use `qwen3:4b` and `WHISPER_MODEL=base`. |
| Want to start fresh | `POST /api/reset` (or delete `backend/storage/`). |

---

## 9. How this maps to the problem statement (for your report/viva)

| Requirement (SIH 25231) | Where it's implemented |
|--------------------------|------------------------|
| Ingest DOCX/PDF text | `ingestion/pdf_docx_parser.py` (PyMuPDF + python-docx) |
| Image embeddings | `ingestion/image_pipeline.py` (CLIP) + OCR (Tesseract) + caption (BLIP) |
| Speech-to-text | `ingestion/audio_pipeline.py` (faster-whisper, with timecodes) |
| Shared vector space | `retrieval/embeddings.py` + `retrieval/vector_store.py` (Chroma) |
| Natural-language query | `POST /api/query` → `retrieval/search.py` |
| Cross-modal (text↔image) | `retrieval/search.py` (BGE text channel + CLIP image channel) |
| Grounded answers + citations | `generation/answer.py` + `generation/prompt_templates.py` |
| Cross-format links | Every chunk stores file/page/timecode metadata → citations |
| Citation navigation | `GET /api/source/{id}` + `GET /api/media/{file}` + Sources panel |
| Voice / image / audio query (optional) | `/api/transcribe`, `/api/query/image`, `/api/query/audio` |
| Fully offline | Ollama LLM + local models + embedded Chroma (no cloud) |

---

## 10. Architecture at a glance

```
          ┌──────────── INGESTION ────────────┐
 PDF/DOCX ─► PyMuPDF/python-docx ─► chunks ────┤
 Images  ─► OCR + BLIP caption + CLIP ─────────┤─► embeddings ─► ChromaDB
 Audio   ─► faster-whisper (timecodes) ────────┘   (BGE text +   (2 collections,
                                                    CLIP image)    rich metadata)
                                                                        │
 User query (text / image / audio / voice)                             │
        │                                                              ▼
        └─► search.py  ── retrieve top-K ──►  answer.py ── Ollama (Qwen3) ─►
                     (text + CLIP channels)      (grounded prompt)     answer
                                                                     + [1][2] citations
                                                                        │
                                                              GET /api/source/{id}
                                                              GET /api/media/{file}
                                                              (click to open source)
```

See `README.md` for the folder layout and a shorter overview.
```
