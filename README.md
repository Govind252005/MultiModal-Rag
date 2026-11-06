# Enterprise Multimodal Offline RAG Platform (v2.0)

[![Release](https://img.shields.io/badge/release-v2.0--enterprise-blue.svg)](RELEASE_NOTES.md)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Security](https://img.shields.io/badge/security-hardened-success.svg)](SECURITY.md)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org/)
[![TypeScript](https://img.shields.io/badge/typescript-5.x-blue)](https://www.typescriptlang.org/)

An enterprise-grade, privacy-first, multimodal Retrieval-Augmented Generation (RAG) platform. Combines cross-lingual document intelligence, multi-vector indexing, OCR extraction, tabular data querying, and local LLM reasoning (via Ollama) with a modern React/TypeScript interface and zero-egress offline security.

---

## Architecture

```text
React 18 SPA (Vite + Tailwind CSS + Lucide + KaTeX)
       │
       ▼ (REST + SSE Streaming + Cookie Auth)
FastAPI Backend (Session & RBAC Management + Rate Limiter)
       │
   ┌───┴─────────────────────────────────────────────┐
   ▼                                                 ▼
Ingestion & Parsing Pipeline                 Retrieval & Generation Pipeline
├─ PDF (PyMuPDF with exact layout)           ├─ Non-Latin Query Safety Guard
├─ Word (python-docx)                        ├─ Hybrid Fusion (Dense + SQLite FTS5 BM25)
├─ Spreadsheets (openpyxl tabular)           ├─ Cross-Encoder Reranking (Latin-only guard)
├─ Images (CLIP embeddings + PaddleOCR)      ├─ Local LLM Engine (Ollama / Qwen3:4b)
└─ Audio (Faster-Whisper transcription)      └─ Citation & Exact Passage Anchoring
```

---

## Key Enterprise Capabilities

1. **Multilingual & Cross-Lingual RAG**:
   - Protected dense retrieval for Hindi/Devanagari, Arabic, Spanish, French, and German.
   - Non-Latin query guard protects non-Latin tokens from English-only cross-encoder corruption.
   - Verified benchmarks: **Hit@1 = 0.80**, **Hit@5 = 1.00**, **MRR = 0.90**, **NDCG@5 = 0.9262**.
2. **Interactive Evidence & Document Viewer**:
   - Side-by-side legal research workspace with citation navigation (`[1]`, `[2]`, `[3]`).
   - Character-accurate passage highlighting with Unicode and Devanagari support.
   - Responsive design adapting smoothly across Desktop (1440px), Laptop (1024px), Tablet (768px), and Mobile (390px).
3. **Multi-Tenant Security & RBAC**:
   - Strict role separation (`admin` vs `user`).
   - Disabled account instant session revocation.
   - Document deletion IDOR protection and isolated collection scoping.
   - Binary magic-byte upload validation and strict path traversal defense.
4. **Offline Privacy Guarantee**:
   - 100% on-premises execution by default for document processing, OCR, indexing, and LLM inference.
   - Clear disclosure banners for browser-level Web Speech API dictation.
5. **Enterprise Disaster Recovery**:
   - Atomic snapshot backup and restoration manager (`backend/backup_manager.py`) covering SQLite FTS5, ChromaDB collections, and session state.

---

## Quick Start

### 1. Prerequisites
- Python 3.10–3.12
- Node.js 18+ and npm
- [Ollama](https://ollama.com) running locally (`ollama serve`)

### 2. Setup Ollama Model
```bash
ollama pull qwen3:4b
```

### 3. Backend Setup
```bash
python -m venv backend/venv
# Windows:
.\backend\venv\Scripts\activate
# Linux/macOS:
source backend/venv/bin/activate

pip install -r backend/requirements.txt
```

### 4. Frontend Setup & Build
```bash
cd frontend
npm install
npm run build
cd ..
```

### 5. Launch Application
```bash
# Windows
.\scripts\run-windows.bat

# Linux/macOS
./scripts/run-unix.sh
```
Open **http://localhost:8000** in your browser.

---

## Documentation

- [Deployment Guide](DEPLOYMENT.md) — System requirements, containerization, and network sharing.
- [Security Architecture](SECURITY.md) — RBAC, threat model, file upload defenses, and privacy boundaries.
- [REST API Reference](API.md) — Endpoints, payloads, and authentication.
- [Release Notes](RELEASE_NOTES.md) — Version 2.0 changelog, empirical benchmarks, and regression results.
