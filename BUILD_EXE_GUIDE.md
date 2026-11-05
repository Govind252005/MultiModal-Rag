# Building `MultimodalRag.exe` (Windows)

This guide turns the whole project — FastAPI backend, the retrieval pipeline,
and the compiled React UI — into a single double-clickable Windows app using
**PyInstaller**. The exe starts the server, opens your browser to the app, and
serves everything on one port. **Ollama stays a separate install** (it's a
system LLM server, too big and license-bound to embed).

> Nothing in the app's behavior changes. The retrieval pipeline, embeddings,
> reranking, and answer generation are identical to the source run. The only
> additions are: a `launcher.py` entry point, a frozen-aware data path in
> `config.py`, and the packaging files (`MultimodalRag.spec`,
> `build-exe-windows.bat`).

---

## 0. What you get (and what you don't)

| Bundled into the exe | NOT bundled (external) |
|----------------------|------------------------|
| Python + FastAPI backend | **Ollama** (install once from ollama.com) |
| The full retrieval pipeline + all Python ML libs | The Qwen model weights (pulled once by Ollama) |
| PyTorch (CPU or CUDA, whichever is in your venv) | — |
| The compiled React UI (served on the same port) | — |
| CLIP / MiniLM / BLIP / Whisper *code* | Their HF weights (auto-download on first use, cached in `%USERPROFILE%\.cache\huggingface`) |

So the finished app is **self-contained for code**, but on first run it still
needs (a) Ollama running with the model pulled, and (b) an internet connection
once to download the embedding/vision model weights. After that it's offline.

> **Build on the same kind of machine you'll run on.** PyInstaller does not
> cross-compile. Build on 64-bit Windows to get a 64-bit Windows exe. If you
> want a GPU build, install the CUDA PyTorch wheel in the venv *before*
> building; for a portable CPU build, install the CPU wheel.

---

## 1. Prerequisites

Do these once before building.

1. **A working source setup.** Follow `SETUP_GUIDE.md` first and confirm the app
   runs the normal way (`uvicorn main:app` + `npm run dev`). If it doesn't run
   from source, it won't run as an exe. In particular your `backend\venv` should
   already have `torch`, `torchvision`, and everything in `requirements.txt`
   installed.
2. **Node.js** (for `npm run build`) — you already have this from setup.
3. **PyInstaller** in the *same* venv as the backend:
   ```powershell
   cd "C:\Users\Govind\Claude\Projects\Minor Project\backend"
   .\venv\Scripts\Activate.ps1
   pip install pyinstaller
   ```
   > It must be the backend venv, because PyInstaller freezes *that*
   > interpreter's packages. If you build from a different Python, you'll ship
   > the wrong (or missing) libraries.

---

## 2. One-command build

From the **project root**, with the backend venv active:

```powershell
.\build-exe-windows.bat
```

The script:

1. builds the frontend (`npm install` if needed, then `npm run build` → `frontend\dist`),
2. installs PyInstaller if it's missing,
3. cleans old `build\` / `dist\` folders,
4. runs `pyinstaller MultimodalRag.spec`.

Result:

```
dist\MultimodalRag\MultimodalRag.exe      <- double-click this
dist\MultimodalRag\_internal\...          <- bundled libraries (keep together)
```

> Keep the whole `dist\MultimodalRag\` folder together. In onedir mode the exe
> needs its sibling files. To distribute, zip the **folder** (or wrap it with an
> installer — see §6).

---

## 3. Manual build (if you prefer step-by-step)

```powershell
# from project root, backend venv active
cd frontend
npm install          # first time only
npm run build        # produces frontend\dist
cd ..

pip install pyinstaller
pyinstaller MultimodalRag.spec --noconfirm --clean
```

The spec (`MultimodalRag.spec`) already:

- uses `backend\launcher.py` as the entry point,
- `collect_all()`s the heavy ML packages (torch, transformers,
  sentence-transformers, chromadb, paddleocr, faster-whisper, PyMuPDF, opencv,
  PIL, onnxruntime, …),
- bundles `frontend\dist` as `frontend_dist`,
- lists the app's own flat modules (`config`, `main`, `retrieval.*`,
  `ingestion.*`, `generation.*`) as hidden imports,
- builds **onedir** (a folder, not a single monster file) with a visible
  console so you can see logs.

---

## 4. First run

1. **Install + start Ollama** and pull the model (one time):
   ```powershell
   ollama pull qwen3:8b
   ```
   Ollama runs as a background service on `http://localhost:11434`.
2. Double-click **`dist\MultimodalRag\MultimodalRag.exe`** (or run it from a
   terminal to watch the logs).
3. A console window shows startup; when the server is healthy it prints the URL
   and **opens your browser** to `http://127.0.0.1:8000`.
4. If Ollama isn't running, the app **still opens** — it just prints a warning
   and local answers won't work until you start Ollama (cloud providers with an
   API key work regardless).

### Where the app stores data

A packaged exe can't write inside its own bundle, so writable data is redirected
to:

```
%LOCALAPPDATA%\MultimodalRag\
    data\
    storage\
        chroma\        <- vector DB
        sessions\
        users.json
        secret.key
```

To put it elsewhere (e.g. a portable drive), set an env var before launching:

```powershell
set RAG_DATA_HOME=D:\MultimodalRagData
MultimodalRag.exe
```

Other launch knobs: `RAG_HOST` (default `127.0.0.1`), `RAG_PORT` (default
`8000`), `RAG_NO_BROWSER=1` to skip auto-opening the browser.

---

## 5. Troubleshooting

| Symptom | Fix |
|---------|-----|
| `ModuleNotFoundError: No module named 'X'` at runtime | Add `X` to `hiddenimports` in `MultimodalRag.spec` (or to `HEAVY_PACKAGES` if it ships data files), then rebuild. |
| Exe starts but UI is blank / only JSON at `/` | `frontend\dist` wasn't bundled. Run `npm run build` in `frontend\` first, confirm `frontend\dist\index.html` exists, rebuild. |
| `Answer says "LLM unavailable"` | Ollama isn't running or model not pulled. `ollama list`, then `ollama pull qwen3:8b`. |
| Build fails on `torch` / DLL load errors at runtime | Keep `upx=False` (already set). Make sure the venv's torch actually imports: `python -c "import torch"`. |
| Antivirus flags the exe | Common with PyInstaller onefile; onedir (this spec) is less prone. Sign the exe or whitelist it. |
| Huge bundle size (several GB) | Expected — torch + CUDA + models are large. Use the **CPU** torch wheel for a smaller, more portable build. |
| Slow first launch | Normal — models load into memory once; later queries are fast. |
| `RuntimeError: ... _MEIPASS` / temp path issues | You're likely on onefile; this spec is onedir on purpose. Rebuild with the provided spec. |
| Want to reset all data | Delete `%LOCALAPPDATA%\MultimodalRag\storage`. |

---

## 6. Optional — a real Windows installer (Inno Setup)

Onedir gives you a folder. To ship a proper `Setup.exe` that installs to
`Program Files`, adds a Start-menu shortcut, and can pull the model on first
run, wrap the `dist\MultimodalRag\` folder with **Inno Setup**
(<https://jrsoftware.org/isinfo.php>). A minimal script:

```iss
[Setup]
AppName=Multimodal RAG
AppVersion=1.0
DefaultDirName={autopf}\MultimodalRag
DefaultGroupName=Multimodal RAG
OutputBaseFilename=MultimodalRag-Setup
Compression=lzma2
SolidCompression=yes

[Files]
Source: "dist\MultimodalRag\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Multimodal RAG"; Filename: "{app}\MultimodalRag.exe"
Name: "{commondesktop}\Multimodal RAG"; Filename: "{app}\MultimodalRag.exe"

[Run]
; Optional: open Ollama's site if it's not installed, or run a post-install
; script that does `ollama pull qwen3:8b`.
Filename: "{app}\MultimodalRag.exe"; Description: "Launch Multimodal RAG"; Flags: nowait postinstall skipifsilent
```

Compile that `.iss` in the Inno Setup Compiler to get `MultimodalRag-Setup.exe`.
You'd still document that Ollama must be installed separately (bundling Ollama
inside the installer is possible via its own silent installer, but keep it a
distinct step so updates stay simple).

---

## 7. Files added for packaging (all additive)

| File | Purpose |
|------|---------|
| `backend/launcher.py` | Frozen-aware entry point: starts uvicorn in-process, waits for health, opens the browser, warns if Ollama is down. |
| `backend/config.py` (edited) | `DATA_HOME` redirects writable data out of the read-only bundle when frozen; `STATIC_DIR` resolves the bundled UI from `_MEIPASS`. Dev behavior unchanged. |
| `MultimodalRag.spec` | PyInstaller recipe (onedir, hidden imports, `collect_all` for ML libs, bundles `frontend/dist`). |
| `build-exe-windows.bat` | One-command build: frontend build → PyInstaller. |
| `BUILD_EXE_GUIDE.md` | This guide. |

None of these touch `retrieval/search.py` or the retrieval/embedding/rerank
logic — the pipeline is byte-for-byte the same as the source app.



