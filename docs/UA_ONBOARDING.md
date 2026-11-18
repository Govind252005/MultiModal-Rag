# Multimodal-RAG: Complete Engineering Team Onboarding Guide

Welcome to the **MultiModal-RAG** platform codebase. This guide is automatically derived from the project's knowledge graph to help you get up to speed quickly on the architecture, subsystems, code conventions, and execution workflows.

---

## 1. Project Overview

* **Repository Name**: `multimodal-rag`
* **Core Functionality**: Enterprise Multimodal Retrieval-Augmented Generation (RAG) platform supporting document ingestion (PDF, DOCX, TXT), audio transcription (Whisper), image feature extraction, dual-stage hybrid retrieval (dense ChromaDB + sparse BM25), Cross-Encoder reranking, local/cloud LLM synthesis, and an interactive React citation UI with evidence-span highlighting.
* **Primary Tech Stack**:
  * **Backend**: Python 3.10+, FastAPI, PyTorch, HuggingFace Transformers, ChromaDB, Sentence-Transformers, Whisper, PyMuPDF (fitz), python-docx.
  * **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, Lucide Icons, SSE (Server-Sent Events) streaming.
  * **LLM Engine**: Ollama (local default), Groq, OpenAI, Anthropic via unified provider abstraction.
  * **Packaging & Infra**: Docker Compose, Kubernetes manifests, Windows Inno Setup (`.iss`), PyInstaller.
* **Active Branch / Revision**: `enterprise-security-performance` (`f8a0a085f25b7bb89fb7eac7cc5f89b33e9eb312`)

---

## 2. Architecture Layers

The repository is partitioned into 8 core architectural layers:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                   Frontend Presentation & Citation UI                       │
│      React 18 + Vite SPA, SSE Stream Parser, DocumentViewer, Composer       │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ HTTP / SSE (FastAPI)
┌──────────────────────────────────────▼──────────────────────────────────────┐
│                         API & Orchestration Layer                           │
│        backend/main.py, auth.py (JWT / Tenant Isolation), sessions.py        │
└──────────────────┬───────────────────────────────────┬──────────────────────┘
                   │ Ingest Workflow                   │ Query / Retrieval
┌──────────────────▼──────────────────┐ ┌──────────────▼──────────────────────┐
│     Multimodal Ingestion Pipeline   │ │   Hybrid Retrieval & Vector Store   │
│  PDF / DOCX, Audio (Whisper), Image │ │  ChromaDB (Dense) + BM25 (Sparse)   │
│  Chunker & Metadata Tagging         │ │  Reciprocal Rank Fusion + Reranking │
└──────────────────┬──────────────────┘ └──────────────┬──────────────────────┘
                   │                                   │ Top-K Chunks
                   │ Embeddings                        ▼
┌──────────────────▼──────────────────────────────────────────────────────────┐
│                      LLM Generation & Provider Engine                       │
│    answer.py (Context & Citations), prompt_templates.py, llm_client.py      │
│               Active Provider Router: Ollama | Groq | OpenAI                │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Telemetry & Benchmarks
┌──────────────────────────────────────▼──────────────────────────────────────┐
│                    Evaluation & Benchmarking Framework                      │
│     ablation_evaluator.py, citation_evaluator.py, unit & security tests     │
└─────────────────────────────────────────────────────────────────────────────┘
```

1. **Frontend Presentation & Citation UI** (`layer:frontend-presentation` — 143 nodes)  
   User-facing interactive dashboard, streaming Markdown chat, document manager, and canvas-based document viewer with real-time evidence span highlighting.
2. **API & Orchestration Layer** (`layer:api-orchestration` — 38 nodes)  
   FastAPI server, application lifespan hooks, JWT authentication, per-tenant workspace isolation, and server lifecycle automation.
3. **Multimodal Ingestion Pipeline** (`layer:multimodal-ingestion` — 37 nodes)  
   Format-specific parsers (`pdf_docx_parser.py`, `audio_pipeline.py`, `image_pipeline.py`) that convert files into normalized chunk streams with bounding boxes and timestamps.
4. **Hybrid Retrieval & Vector Search** (`layer:hybrid-retrieval` — 38 nodes)  
   Dense vector similarity search via ChromaDB, sparse keyword matching via BM25, late-interaction ColBERT mechanisms, and cross-encoder neural rerankers.
5. **LLM Generation & Provider Engine** (`layer:llm-generation` — 54 nodes)  
   Grounded generation engine assembling prompt contexts with indexed citations `[1]`, `[2]`, managing active provider fallbacks (Ollama $\to$ Groq $\to$ OpenAI/Anthropic), and streaming answers via SSE.
6. **Evaluation & Benchmarking Framework** (`layer:evaluation-testing` — 479 nodes)  
   Automated ablation tests, precision/recall benchmarks, modality evaluation, and security isolation tests.
7. **Infrastructure & Desktop Packaging** (`layer:infrastructure-deployment` — 94 nodes)  
   Docker containers, compose definitions, Kubernetes manifests, and Windows Inno Setup desktop installer scripts.
8. **Documentation & System Configuration** (`layer:documentation-configuration` — 138 nodes)  
   API specifications, production runbooks, environment variable templates, and technical guides.

---

## 3. Key Concepts & Design Patterns

1. **Dual-Stage Hybrid Retrieval with RRF**  
   Queries are executed concurrently against ChromaDB (dense semantic similarity via Sentence-Transformers) and an in-memory BM25 index (sparse exact keyword matching). Results are merged via **Reciprocal Rank Fusion (RRF)**:
   $$RRF(d) = \sum_{m \in \{dense, sparse\}} \frac{1}{60 + \text{rank}_m(d)}$$
   The top candidates are then passed through a neural Cross-Encoder (`bge-reranker-large` / `ms-marco-MiniLM-L-6-v2`) to re-score query-passage relevance.

2. **Grounded Provenance & Citation Brackets**  
   LLM prompt templates mandate that factual assertions must cite the source index in square brackets (e.g., `According to the report [1], total revenue grew 14%...`). The backend verifies every citation tag against the retrieved top-k chunks, extracting exact `evidence_span` substrings and bounding coordinates.

3. **Multi-Tenant Workspace Isolation**  
   All session queries, vector collections, and document uploads are scoped to authenticated tenant IDs (`tenant_id`). Cross-tenant access is strictly denied at both the REST API middleware level and the vector database collection partitioning layer.

4. **Resilient Provider Routing**  
   `active_provider.py` and `llm_client.py` implement an automated health check and fallback hierarchy: if local Ollama daemon is unreachable or out of VRAM, the system dynamically routes requests to cloud Groq or OpenAI without dropping the user's session.

---

## 4. Guided Codebase Tour (Learning Path)

Follow this 7-step sequence when exploring the codebase for the first time:

* **Step 1: System Entry Points & Configuration**  
  * Read `backend/main.py`: Understand how FastAPI initializes, loads CORS middleware, mounts `/api/v1` routes, and controls server lifespan.  
  * Read `backend/config.py`: See how environment variables, embedding models, vector dimensions, and chunk limits are centralized.  
  * Read `frontend/src/App.tsx`: Examine the root React application state, view tabs, and theme controls.
* **Step 2: Multimodal Ingestion Pipeline**  
  * Read `backend/ingestion/ingest.py`: Core ingestion coordinator routing incoming files by MIME type.  
  * Read `backend/ingestion/pdf_docx_parser.py`: PDF layout extraction with PyMuPDF, table parsing, image extraction, and DOCX paragraph analysis.  
  * Read `backend/ingestion/chunker.py`: Sliding-window semantic chunking with metadata inheritance (page, header, row-index).
* **Step 3: Hybrid Retrieval & Vector Store**  
  * Read `backend/retrieval/vector_store.py`: ChromaDB collection management, embedding storage, and similarity search.  
  * Read `backend/retrieval/lexical_index.py`: In-memory BM25 index with tokenization, stopword removal, and term frequency scoring.  
  * Read `backend/retrieval/search.py`: Hybrid search coordinator executing dense + BM25 search, RRF merging, and Cross-Encoder reranking.
* **Step 4: LLM Generation & Provider Engine**  
  * Read `backend/generation/answer.py`: Context assembly, citation verification, evidence span extraction, and confidence scoring.  
  * Read `backend/generation/llm_client.py`: Multi-provider LLM client with streaming support and Ollama warmup.  
  * Read `backend/generation/prompt_templates.py`: Strict system prompts enforcing verifiable citations and tone.
* **Step 5: Frontend Presentation & Citation UI**  
  * Read `frontend/src/components/ChatPanel.tsx`: Chat history, streaming message rendering, and citation pill triggers.  
  * Read `frontend/src/components/Composer.tsx`: Query input box, file attachment drops, and model switcher.  
  * Read `frontend/src/components/DocumentViewer.tsx`: PDF and document inspector rendering exact text highlight spans (`evidence_span`).
* **Step 6: Evaluation, Ablation & Testing**  
  * Read `evaluation/evaluators/ablation_evaluator.py`: Benchmark measuring precision drops when turning off rerankers or lexical search.  
  * Read `tests/security/test_tenant_isolation.py`: Security assertions proving strict tenant boundary enforcement.
* **Step 7: Production Packaging & Deployment**  
  * Inspect `docker-compose.yml`: Multi-container configuration for backend, frontend, and ChromaDB.  
  * Inspect `Installer/installer.iss`: Inno Setup Windows installer compiling the standalone offline executable package.

---

## 5. File Map by Architectural Layer

### API & Orchestration
* `backend/main.py`: FastAPI application root, route definitions, lifespan, CORS.
* `backend/auth.py`: JWT token generation, verification, and role-based access control (RBAC).
* `backend/sessions.py`: In-memory and persisted chat session state management.
* `backend/launcher.py`: Desktop application startup script managing local subprocesses.

### Multimodal Ingestion
* `backend/ingestion/ingest.py`: Ingestion controller orchestrating parsers and vector store commits.
* `backend/ingestion/pdf_docx_parser.py`: High-fidelity PDF, DOCX, and text layout parser.
* `backend/ingestion/audio_pipeline.py`: Whisper-based audio transcription pipeline.
* `backend/ingestion/image_pipeline.py`: Image OCR and visual embedding extractor.
* `backend/ingestion/chunker.py`: Semantic text chunker preserving document hierarchy.

### Hybrid Retrieval
* `backend/retrieval/search.py`: Main hybrid retrieval pipeline (BM25 + Chroma + Reranker).
* `backend/retrieval/vector_store.py`: Vector database interface for ChromaDB collections.
* `backend/retrieval/lexical_index.py`: Sparse BM25 index implementation.
* `backend/retrieval/embeddings.py`: Sentence-Transformers dense embedding loader.
* `backend/retrieval/late_interaction.py`: ColBERT multi-vector scoring mechanism.

### LLM Generation
* `backend/generation/answer.py`: Answer generation logic, streaming assembler, citation builder.
* `backend/generation/llm_client.py`: Unified API wrapper for Ollama, Groq, OpenAI, and Anthropic.
* `backend/generation/active_provider.py`: Health checking, provider selection, and automatic failover.
* `backend/generation/prompt_templates.py`: Few-shot prompts with provenance citation rules.

### Frontend
* `frontend/src/App.tsx`: Top-level application component managing layout and active modals.
* `frontend/src/api.ts`: Typed API client for FastAPI endpoints and SSE streams.
* `frontend/src/components/ChatPanel.tsx`: Chat stream container with clickable citation pills.
* `frontend/src/components/DocumentViewer.tsx`: Document viewer with fuzzy evidence span matching.
* `frontend/src/components/SourcesPanel.tsx`: Drawer listing all retrieved sources and similarity scores.

---

## 6. Complexity Hotspots (Approach with Care)

The knowledge graph identifies these high-complexity modules that require extra attention when modifying:

1. **`backend/generation/answer.py` (1,880 lines — Complex)**  
   Contains complex regular expressions, extractive fallbacks (`_semantic_extractive_rescue`), citation verification algorithms, and direct field extractors. Be cautious with edge-case citation bracket parsing.
2. **`frontend/src/components/DocumentViewer.tsx` (1,692 lines — Complex)**  
   Handles multi-page PDF rendering, canvas zooming, full-screen popouts, and intricate string normalization (`findExactHighlightRange`) to highlight citations across line breaks and hyphens.
3. **`backend/retrieval/search.py` (1,169 lines — Complex)**  
   Coordinates async multi-threaded vector queries, BM25 scoring, score normalization, RRF rank fusion, and cross-encoder batching. Changes here directly affect overall query latency and recall.
4. **`backend/ingestion/pdf_docx_parser.py` (685 lines — Moderate/Complex)**  
   Complex table detection, row-aligned text extraction, and bounding box coordinate calculation. Ensure layout coordinates match what `DocumentViewer.tsx` expects.

---

## 7. Developer Quick Start

```bash
# 1. Start the development environment (Backend + Frontend)
.\dev.bat

# 2. Run test suites
pytest tests/unit/ tests/security/

# 3. Build Windows standalone installer
.\build-installer-windows.bat
```
