# Multimodal Offline RAG

A production-style multimodal Retrieval-Augmented Generation project for searching and chatting over documents, images, and audio. The application combines a React frontend with a FastAPI backend, a persistent ChromaDB vector store, and local open-source models for retrieval and answer generation.

This project is designed for offline or semi-offline local use, with support for Ollama-based local LLMs and cloud fallback providers. It is optimized for research, internal knowledge bases, and private document Q&A workflows.

## Overview

The system allows a user to:

- Upload PDFs, DOCX files, images, and audio clips
- Parse and index content into a shared semantic space
- Search by text, image, and audio context
- Retrieve relevant citations with page, image, or timestamp metadata
- Ask grounded questions using a local LLM
- Review answers with clickable source references

## Architecture

```text
React Frontend
      ↓
FastAPI Backend
      ↓
Session + Auth + File Management
      ↓
Document / Image / Audio Ingestion
      ↓
SentenceTransformers + CLIP Embeddings
      ↓
ChromaDB Vector Store
      ↓
Hybrid Retrieval (dense + BM25 + CLIP)
      ↓
Cross-encoder Reranking
      ↓
Local LLM (Ollama / Qwen)
      ↓
Grounded Answer with Citations
```

## Key features

- Chat sessions with isolated per-user and per-session libraries
- Scoped search by file and modality
- PDF and DOCX indexing
- OCR for images and scanned documents
- BLIP-based image captioning
- Audio transcription and timestamp-aware retrieval
- Text-to-image and image-to-document retrieval
- Numbered source citations for answer transparency
- Multilingual support via text and OCR configuration
- Local-first architecture with optional cloud providers

## Tech stack

- Frontend: React + TypeScript + Vite + Tailwind
- Backend: FastAPI + Python
- Embeddings: SentenceTransformers
- Cross-modal embeddings: CLIP
- Vector database: ChromaDB
- OCR: PaddleOCR + Tesseract fallback
- Audio: faster-whisper
- Document parsing: PyMuPDF + python-docx
- LLM: Ollama + Qwen family
- Optional cloud providers: Gemini, OpenAI, Anthropic, Groq

## Repository structure

```text
Minor Project/
├── README.md
├── SETUP_GUIDE.md
├── DEPLOYMENT.md
├── WHATS_NEW.md
├── docker-compose.yml
├── backend/
│   ├── config.py
│   ├── main.py
│   ├── requirements.txt
│   ├── ingestion/
│   ├── retrieval/
│   ├── generation/
│   ├── data/
│   └── storage/
├── frontend/
│   ├── src/
│   ├── package.json
│   ├── vite.config.ts
│   └── index.html
├── scripts/
├── docker/
├── Installer/
├── assets/
└── k8s/
```

## Prerequisites

Before starting, ensure you have:

- Python 3.10+
- Node.js 18+
- npm
- Git
- Ollama installed locally
- Tesseract OCR installed (recommended for OCR fallback)
- CUDA-capable GPU optional but recommended for faster inference

## Quick start

### 1. Install the local LLM model

```bash
ollama pull qwen3:4b
```

### 2. Backend setup

```bash
cd backend
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Then open:

- API docs: http://localhost:8000/docs

### 3. Frontend setup

```bash
cd frontend
npm install
npm run dev
```

Open the app at:

- http://localhost:5173

## Environment configuration

The backend is configured in [backend/config.py](backend/config.py). Important settings include:

- `OLLAMA_HOST`
- `LLM_MODEL`
- `TEXT_EMBED_MODEL`
- `OCR_ENGINE`
- `DEFAULT_PROVIDER`
- `DATA_DIR` / `STORE_DIR`

A sample environment file is available in [backend/.env.example](backend/.env.example) if present in the project structure, or you can create your own from the config values.

## API and app behavior

The backend exposes the main routes for:

- auth
- session management
- ingestion
- file listing
- query execution
- image/audio query support
- source/media retrieval
- provider configuration

The frontend uses relative `/api` endpoints, routed through Vite during local development.

## Local usage examples

### Ingest a local folder

```bash
cd backend
python -m ingestion.ingest "C:/path/to/folder"
```

### Check health

```bash
curl http://localhost:8000/api/health
```

## Deployment options

This project supports:

- local development
- Docker Compose deployment
- LAN sharing
- Windows installer packaging
- Colab-style remote GPU setups

See the following guides in the repo:

- [SETUP_GUIDE.md](SETUP_GUIDE.md)
- [DEPLOYMENT.md](DEPLOYMENT.md)
- [LINUX_SETUP_GUIDE.md](LINUX_SETUP_GUIDE.md)
- [BUILD_EXE_GUIDE.md](BUILD_EXE_GUIDE.md)

## Project notes

- The app is designed for local-first operation and private knowledge usage.
- RAG retrieval is scoped by session and user.
- Retrieval is hybrid, combining text, BM25, and image/visual retrieval paths.
- The project intentionally supports both offline and cloud-backed generation flows.

## Known limitations

- Some OCR and model setups are hardware-dependent.
- Local LLM inference is slower than hosted APIs but keeps the system private.
- Colab and Docker deployments may require environment adjustments due to localhost assumptions.
- Very large document batches can consume significant RAM and VRAM.

## Contributing

Contributions are welcome. For meaningful changes, please:

1. Open an issue or describe the feature request.
2. Create a feature branch.
3. Keep the backend and frontend changes aligned.
4. Validate the app locally before submitting a PR.

## License

This project is currently distributed as a local research and application codebase. Add a license file if you want to publish it publicly with clear legal terms.

## Support and documentation

See these files for deeper usage:

- [RUN_AND_VERIFICATION_GUIDE.md](docs/RUN_AND_VERIFICATION_GUIDE.md) — **Complete Step-by-Step Run, Testing & Verification Guide**
- [SETUP_GUIDE.md](SETUP_GUIDE.md)
- [DEPLOYMENT.md](DEPLOYMENT.md)
- [WHATS_NEW.md](WHATS_NEW.md)
- [LLM_PROVIDERS_AND_EVALUATION.md](docs/LLM_PROVIDERS_AND_EVALUATION.md)
- [PROJECT_DOCUMENTATION.md](PROJECT_DOCUMENTATION.md)
- [documentation.md](documentation.md)

---

Made for private multimodal RAG workflows, document intelligence, and offline AI search over your local knowledge base.
