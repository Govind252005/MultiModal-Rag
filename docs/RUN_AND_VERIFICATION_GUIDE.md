# Complete End-to-End Run, Testing, Evaluation & Verification Guide

> **Target Audience:** Developers, research evaluators, and system auditors.  
> **Source of Truth:** This guide is written directly against the actual codebase of `minor-main`. All file paths, API endpoints, parameters, models, and metric names correspond to verified source code.

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Architecture](#2-architecture)
3. [System Requirements](#3-system-requirements)
4. [Installation](#4-installation)
5. [Backend Setup](#5-backend-setup)
6. [Frontend Setup](#6-frontend-setup)
7. [Ollama Setup](#7-ollama-setup)
8. [Groq Setup](#8-groq-setup)
9. [Provider Switching](#9-provider-switching)
10. [Document Ingestion](#10-document-ingestion)
11. [Frontend Usage](#11-frontend-usage)
12. [Per-Query Metrics](#12-per-query-metrics)
13. [Terminal Evaluation](#13-terminal-evaluation)
14. [Ollama Evaluation](#14-ollama-evaluation)
15. [Groq Evaluation](#15-groq-evaluation)
16. [Ollama vs Groq Comparison](#16-ollama-vs-groq-comparison)
17. [Full Re-Evaluation](#17-full-re-evaluation)
18. [Metrics Reference](#18-metrics-reference)
19. [Reports & Artifacts](#19-reports--artifacts)
20. [API Testing Without Frontend](#20-api-testing-without-frontend)
21. [Complete Testing Matrix](#21-complete-testing-matrix)
22. [Troubleshooting](#22-troubleshooting)
23. [Reproducibility Guide](#23-reproducibility-guide)
24. [Research & Paper Verification](#24-research--paper-verification)
25. [Final Verification Checklist](#25-final-verification-checklist)
26. [Command Cheat Sheet](#26-command-cheat-sheet)
27. [Expected Final State](#27-expected-final-state)

---

## 1. Introduction

This project is a production-grade, multimodal Retrieval-Augmented Generation (RAG) system with an integrated, research-grade evaluation and benchmarking suite. It allows users to:
1. Ingest heterogeneous files: PDFs, DOCX, text files, images (with OCR and CLIP), and audio recordings (with Whisper transcription).
2. Retrieve grounded evidence using hybrid search: Dense vector search (SentenceTransformers) + Sparse Lexical search (SQLite FTS5 BM25) + Visual cross-modal embeddings (CLIP) + Reciprocal Rank Fusion (RRF) + Cross-Encoder neural reranking.
3. Generate grounded answers using either a fully offline local LLM (Ollama with `qwen3:4b`) or an ultra-low-latency cloud LLM (Groq with `llama-3.3-70b-versatile`).
4. Perform real-time, terminal-only telemetry for live user queries, displaying latency breakdowns, token counts, throughput (tokens/sec), and semantic faithfulness scores without cluttering the frontend chat UI.
5. Execute offline, 12-stage benchmark evaluations against the canonical `evaluation/datasets/rag_test_dataset.json` and generate side-by-side provider comparisons (CSV, JSON, publication-ready PNG graphs, and LaTeX paper tables).

---

## 2. Architecture

### 2.1 Complete System Dataflow

```
User Query (Frontend Web UI or REST API)
                    ↓
           FastAPI Backend (`/api/query` or `/api/query/stream`)
                    ↓
  ┌─────────────────────────────────────────────────────────────┐
  │                 Multimodal Retrieval Pipeline               │
  │  - Dense Retrieval: SentenceTransformers (MiniLM-L12-v2)    │
  │  - Sparse Retrieval: SQLite FTS5 (Lexical BM25)             │
  │  - Visual Retrieval: OpenAI CLIP (clip-ViT-B-32)            │
  │  - Fusion: Reciprocal Rank Fusion (RRF)                     │
  │  - Reranking: Cross-Encoder (ms-marco-MiniLM-L-6-v2)        │
  └──────────────────────────────┬──────────────────────────────┘
                                 ↓
            Context Construction & Citation Mapping
                                 ↓
            LLM Selection via Dynamic Router & Keystore
             ├── Local: Ollama (`qwen3:4b`) via HTTP 11434
             └── Cloud: Groq (`llama-3.3-70b-versatile`) via Groq SDK
                                 ↓
            Grounded Answer Generation + Citations ([1], [2])
                                 ↓
  ┌─────────────────────────────────────────────────────────────┐
  │            Per-Query Evaluation Engine (`query_eval.py`)     │
  │  - Latency: Retrieval ms, Generation ms, TTFT ms, Total ms  │
  │  - Throughput: Prompt tokens, Completion tokens, Tokens/sec │
  │  - Semantic Faithfulness: LLM Judge claim-level grounding   │
  └──────────────┬───────────────────────────────┬──────────────┘
                 ↓                               ↓
    Printed to Backend Terminal       Persisted to Session JSON
    (Clean ASCII-Safe Scorecard)      (`backend/storage/sessions/`)
```

### 2.2 Distinction Between Execution Modes

| Dimension | Live Frontend Query Mode | Standalone Evaluation Benchmark Mode | Provider Comparison Mode |
|---|---|---|---|
| **Trigger** | User types in React UI or calls `/api/query` | CLI: `python evaluation/run_eval.py` | CLI: `python evaluation/run_eval.py --provider both` |
| **Server State** | Backend server **must** be running on `:8000` | Can run against live server or via `--self-test` | Can run against live server or offline |
| **Dataset** | User's ad-hoc query against uploaded session files | Fixed benchmark dataset (190 ground-truth questions) | Same 190 questions on identical retrieved context |
| **Ground Truth** | Not required (evaluates faithfulness to retrieved context) | Required for Recall@K, Precision@K, MRR, MAP, nDCG | Required for relative accuracy & generation scoring |
| **Output** | Chat answer + Citations in UI; Scorecard in terminal | Full report suite: CSV, JSON, PNG graphs, LaTeX | Grouped bar chart (`.png`), `provider_comparison.csv` |

---

## 3. System Requirements

### Hardware Requirements
- **Operating System:** Windows 10/11 (64-bit), Ubuntu 20.04/22.04 LTS, or macOS 12+ (Apple Silicon supported).
- **RAM:** Minimum 8 GB; 16 GB+ strongly recommended (SentenceTransformers + CLIP + Cross-Encoder reside in RAM/VRAM).
- **NVIDIA GPU (Optional but Recommended):** CUDA 11.8+ or 12.1+. Tested with PyTorch `2.5.1+cu121`. When present, embeddings and local reranking run on `cuda`; falls back cleanly to `cpu`.
- **Disk Space:** At least 10 GB free space (for Python packages, PyTorch, Hugging Face models, Ollama models, and ChromaDB vector storage).

### Software Requirements
- **Python:** 3.10 or 3.11 (tested and verified on Python 3.11).
- **Node.js & npm:** Node.js 18+ and npm 9+ (for building and serving the frontend).
- **Git:** Standard git version control.
- **Ollama:** Installed locally from [ollama.com](https://ollama.com).
- **Groq API Key:** Required for cloud generation; free tier available from [console.groq.com](https://console.groq.com).
- **Internet Access:** Required only for downloading initial Hugging Face weights and calling Groq API. Ollama runs 100% offline.

---

## 4. Installation

All commands are run from the project root directory: `c:\Users\Govind\Downloads\files\minor-main` (or your repository clone path).

### 4.1 Step 1: Set Up Python Virtual Environment
Check Python version and activate the virtual environment:

```powershell
# In PowerShell (Windows)
python --version   # Must be 3.10.x or 3.11.x

# Create virtual environment if it does not already exist
python -m venv .venv

# Activate the virtual environment
.\.venv\Scripts\Activate.ps1
```

*For Linux / macOS:*
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 4.2 Step 2: Install Backend Dependencies
Install PyTorch with CUDA (or CPU) followed by repository requirements:

```powershell
# If using NVIDIA CUDA 12.1:
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

# Install project backend dependencies:
pip install -r backend/requirements.txt
```

Verify backend installation:
```powershell
$env:PYTHONIOENCODING="utf-8"
python backend.verify_backend.py
```
*Expected Output:*
```
✓ keystore: roundtrip, encryption-at-rest, isolation, delete
✓ registry: ['ollama', 'gemini', 'openai', 'claude', 'groq']
✓ router: default = ollama
✓ answer.py: provider + user_id in all three functions

All checks passed.
```

---

## 5. Backend Setup

The backend is built with FastAPI and Uvicorn.

### 5.1 Starting the Server
From the project root, run:

```powershell
# Set console encoding to UTF-8 to ensure unicode metric characters print properly
$env:PYTHONIOENCODING="utf-8"

# Start the FastAPI server using the dedicated virtual environment
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Alternatively, from the `backend/` folder:
```powershell
cd backend
$env:PYTHONIOENCODING="utf-8"
..\.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000
```

### 5.2 Verifying Backend Health
Check that the server starts up properly:
- Open browser or execute:
```powershell
curl http://localhost:8000/api/health
```
*Expected JSON Response:*
```json
{
  "status": "ok",
  "device": "cuda",
  "ollama": {
    "host": "http://localhost:11434",
    "model": "qwen3:4b"
  }
}
```
Interactive OpenAPI documentation is live at: `http://localhost:8000/docs`.

---

## 6. Frontend Setup

The frontend is built with React 18, TypeScript, TailwindCSS, and Vite.

### 6.1 Install Frontend Dependencies
From the `frontend/` directory:
```powershell
cd frontend
npm install
```

### 6.2 Option A: Production Build (Recommended)
Building the production assets allows the FastAPI backend to serve the entire app from `http://localhost:8000/`:
```powershell
cd frontend
npm run build
```
*Expected Output:*
```
vite v5.4.21 building for production...
transforming...
✓ 1591 modules transformed.
rendering chunks...
dist/index.html                   1.08 kB
dist/assets/index-vZDSYmwR.css   38.56 kB
dist/assets/index-DBVJGUU0.js   230.07 kB
✓ built in 2.09s
```

### 6.3 Option B: Development Server (Vite HMR)
If actively editing React code:
```powershell
cd frontend
npm run dev
```
Runs at `http://localhost:5173`. Proxies `/api` requests to backend at `http://localhost:8000`.

---

## 7. Ollama Setup

The primary offline model is **Qwen3 4B** (`qwen3:4b`).

### 7.1 Verify Ollama Daemon
Ensure Ollama is installed and running:
```powershell
ollama --version
ollama list
```

### 7.2 Pull Required Model
Pull the verified model used across configuration and benchmarks:
```powershell
ollama pull qwen3:4b
```

### 7.3 Test Model Inference Directly
```powershell
ollama run qwen3:4b "What is multimodal RAG?"
```
*Expected Output:* Ollama streams an explanation and returns to the prompt.

### 7.4 What Happens if Ollama is Offline?
If Ollama is stopped or the model is missing:
- Live frontend queries trigger an extractive fallback:
  `[LLM unavailable — showing top retrieved source]` followed by the top retrieved chunk.
- The system never crashes and logs a classified provider error in the terminal.

---

## 8. Groq Setup

Groq provides ultra-fast cloud inference on Groq LPUs.

### 8.1 Obtaining an API Key
1. Navigate to [https://console.groq.com/keys](https://console.groq.com/keys).
2. Log in and generate a new key (`gsk_...`).

### 8.2 Two Ways to Configure the Key

#### Method A: Via Frontend UI (Encrypted Storage)
1. Open `http://localhost:8000/`.
2. Click **LLM Providers** in the header.
3. In the Groq card, enter your `gsk_...` key.
4. Click **Save Key & Validate**.
5. The backend validates the key against `https://api.groq.com/openai/v1/models`.
6. Once validated, the **Model** dropdown populates automatically with live Groq models.
7. Click **Activate Provider**.

#### Method B: Via Environment Variable (For Evaluation Scripts)
The offline evaluation scripts (`evaluation/run_eval.py`) run independently of the web browser. Set the environment variable:
```powershell
$env:GROQ_API_KEY="gsk_your_actual_key_here"
```

### 8.3 Security: Zero-Leak Encryption at Rest
- Runtime keys entered in the frontend are encrypted using **Fernet (AES-128-CBC + HMAC-SHA256)**.
- Master secret: `backend/storage/keys.secret`.
- Ciphertext storage: `backend/storage/provider_keys.json` with user isolation (`user_id -> provider -> ciphertext`).
- Plaintext API keys are **never** logged to stdout or saved unencrypted.

---

## 9. Provider Switching

### 9.1 How Switching Works
1. Validating or saving a key does **not** silently change the active LLM.
2. The user must explicitly **activate** a provider and model.
3. The active provider state is persisted per-user in `backend/storage/active_provider.json`.

### 9.2 Switching Endpoints

#### 1. Discover Available Models
```http
GET /api/providers/groq/models
Authorization: Bearer <user_token>
```
*Returns live Groq models (e.g. `llama-3.3-70b-versatile`, `llama-3.1-8b-instant`, `mixtral-8x7b-32768`).*

#### 2. Get Current Active Provider
```http
GET /api/llm/active
Authorization: Bearer <user_token>
```
*Response:*
```json
{
  "provider": "groq",
  "model": "llama-3.3-70b-versatile",
  "is_cloud": true
}
```

#### 3. Activate Provider with Model Selection
```http
POST /api/llm/providers/groq/activate
Authorization: Bearer <user_token>
Content-Type: application/json

{"model": "llama-3.3-70b-versatile"}
```

To switch back to local Ollama:
```http
POST /api/llm/providers/ollama/activate
Authorization: Bearer <user_token>
Content-Type: application/json

{"model": "qwen3:4b"}
```

### 9.3 Visual Indicator in Frontend Header
The frontend Header dynamically displays:
- **`Ollama — qwen3:4b`** with an **emerald green** dot (offline local mode).
- **`GROQ — llama-3.3-70b-versatile`** with a **sky blue** dot (cloud inference mode).

---

## 10. Document Ingestion

### 10.1 Supported File Formats & Processing

| Format | Extensions | Processing Details |
|---|---|---|
| **Documents** | `.pdf`, `.docx`, `.doc` | Extracted via PyMuPDF / python-docx; page-aware chunking; table detection; embedded image extraction. |
| **Images** | `.png`, `.jpg`, `.jpeg`, `.bmp`, `.tiff`, `.webp` | Processed via PaddleOCR / Tesseract; visual embedding via OpenAI CLIP (`clip-ViT-B-32`); optional BLIP captioning. |
| **Audio** | `.mp3`, `.wav`, `.m4a`, `.flac`, `.ogg`, `.aac` | Transcribed via `faster-whisper` (90+ languages); timestamped chunking (`start_time` / `end_time`). |

### 10.2 Ingestion Modes
The system supports three ingestion depth modes:
- **`fast`**: Text extraction and SentenceTransformers embeddings only. No OCR fallback, no image captioning.
- **`balanced`**: Text extraction + selective OCR for image-heavy pages + CLIP image embeddings.
- **`max_quality`** (Default): Full multimodal pipeline — OCR, table extraction, embedded image extraction, BLIP captions, and CLIP.

---

## 11. Frontend Usage

Follow these steps for a complete visual testing workflow:

1. **Start Backend:** Run `uvicorn backend.main:app --port 8000`.
2. **Open Browser:** Navigate to `http://localhost:8000/`.
3. **Register / Login:**
   - Enter an email and password (minimum 8 characters).
   - Accounts are stored locally in `backend/storage/users.json`.
4. **Create a Session:**
   - Click **New Chat** in the left sidebar.
   - Each chat session is completely isolated (`backend/storage/sessions/{session_id}.json`).
5. **Upload Documents:**
   - Drag and drop test files (e.g. `rag_test.pdf`, `rag_test.txt`, or image files).
   - Watch the upload progress and chunk confirmation in the sources panel.
6. **Ask Questions:**
   - Type: `"What language model does this project use?"`
   - Observe the streamed answer with numbered citations (`[1]`).
   - Click on a citation to open the source snippet and page metadata modal.
7. **Switch LLM Provider:**
   - Open **LLM Providers**, choose Groq, select `llama-3.3-70b-versatile`, click **Activate**.
   - Notice the header badge updates to `GROQ — llama-3.3-70b-versatile`.
   - Ask: `"Which database is used for storing vectors?"`
   - Observe the instant cloud response.

---

## 12. Per-Query Metrics

### 12.1 Execution Flow
Whenever a query runs (via `POST /api/query` or SSE `POST /api/query/stream`), the backend executes `backend/generation/query_eval.py`:

```
User Query → Retrieval → Generation → Query Evaluator
                                           ├── 1. FaithfulnessJudge checks claims against snippets
                                           ├── 2. Terminal Scorecard written to stdout
                                           └── 3. Saved to session JSON (messages[].metrics)
```

### 12.2 Metrics Calculated per Query

| Metric | Source / Formula | Output |
|---|---|---|
| **Retrieval Latency** | Timer over hybrid retrieval, RRF, and Cross-Encoder reranking | Milliseconds (ms) |
| **Hit Count** | Number of retrieved chunks passed to generation prompt | Integer count |
| **Generation Latency** | Timer over LLM generation execution | Milliseconds (ms) |
| **TTFT** | Time To First Token (captured from streaming response) | Milliseconds (ms) |
| **Total E2E Latency** | Retrieval ms + Generation ms | Milliseconds (ms) |
| **Prompt Tokens** | Token length of system prompt + context + history + query | Integer count |
| **Completion Tokens** | Generated response token count | Integer count |
| **Tokens per Second** | `completion_tokens / (generation_ms / 1000)` | Float (tokens/sec) |
| **Faithfulness Score** | Supported claims / Total claims via `FaithfulnessJudge` | Float [0.0 - 1.0] |
| **Claim Grounding** | `supported_claims` out of `total_claims` | Ratio string (e.g. 4/4) |

---

## 13. Terminal Scorecard

### Example Live Terminal Output
Whenever a question is asked from the frontend, look at the backend terminal window:

```
================================================================
[EVAL] RAG QUERY METRICS | Session: 4572aff42854
================================================================
  Query:            "What language model does this project use?"
  Active LLM:       OLLAMA (qwen3:4b)
  LLM Used:         Yes
----------------------------------------------------------------
  LATENCY BREAKDOWN:
    - Retrieval:        145.2 ms  (Hits: 3)
    - Generation:       850.5 ms
    - TTFT:             220.0 ms
    - Total E2E:        995.7 ms
----------------------------------------------------------------
  THROUGHPUT & TOKENS:
    - Prompt Tokens:        350
    - Completion Tokens:     45
    - Total Tokens:         395
    - Output Speed:        52.9 tokens/sec
----------------------------------------------------------------
  QUALITY & FAITHFULNESS:
    - Faithfulness:      1.00 (100.0% grounded) [HIGH]
    - Claim Grounding:   2/2 claims supported by sources
================================================================
```

---

## 14. Ollama Evaluation

Run offline benchmark evaluation solely using the local Ollama provider.

### 14.1 Execution Command
```powershell
$env:PYTHONIOENCODING="utf-8"
.\.venv\Scripts\python.exe evaluation/run_eval.py --provider ollama --all
```

### 14.2 What It Executes
1. Loads the canonical 250-question benchmark dataset (`evaluation/datasets/rag_test_dataset.json`).
2. Performs deterministic hybrid retrieval across benchmark topics.
3. Generates answers using Ollama `qwen3:4b`.
4. Evaluates retrieval ranking, answer correctness, semantic faithfulness, citation precision, and system resources.
5. Saves reports, graphs, and paper tables under `reports/evaluation/<timestamp>/`.

---

## 15. Groq Evaluation

Run offline benchmark evaluation using the cloud Groq provider.

### 15.1 Prerequisites
Ensure your Groq API key is set in your terminal environment:
```powershell
$env:GROQ_API_KEY="gsk_your_actual_key_here"
```

### 15.2 Execution Command
```powershell
$env:PYTHONIOENCODING="utf-8"
.\.venv\Scripts\python.exe evaluation/run_eval.py --provider groq --all
```

### 15.3 Expected Output & Behavior
- Connects to Groq cloud API using model `llama-3.3-70b-versatile`.
- Records generation latency, TTFT, token throughput (~250-400+ tokens/s), and answer correctness.
- Generates a full report suite under `reports/evaluation/<timestamp>/`.

---

## 16. Ollama vs Groq Comparison

This experiment executes **Requirement 18: Provider Comparison**.

### 16.1 Execution Command
```powershell
$env:PYTHONIOENCODING="utf-8"
$env:GROQ_API_KEY="gsk_your_actual_key_here"
.\.venv\Scripts\python.exe evaluation/run_eval.py --provider both --all
```

### 16.2 Controlled Comparison Architecture
```
                     Benchmark Question
                             ↓
                   Deterministic Retrieval
                             ↓
                    Same Retrieved Context
                   ↙                      ↘
     Ollama (qwen3:4b)          Groq (llama-3.3-70b-versatile)
           ↓                                  ↓
  Local Generation Metrics           Cloud Generation Metrics
           ↘                                  ↙
                Provider Comparison Engine
                             ↓
              reports/evaluation/<timestamp>/
               ├── provider_comparison.csv
               ├── provider_comparison.json
               └── provider_comparison.png
```

### 16.3 Generated Comparison Metrics
The comparison directly measures:
- **Answer Correctness (Mean):** Semantic alignment with ground truth.
- **Answer Relevance (Mean):** Relevance of answer to question.
- **Semantic Faithfulness (Mean):** Proportion of claims directly supported by retrieved context.
- **Token F1 (Mean):** Token-level overlap between generated and reference answers.
- **Citation Presence Rate:** Percentage of answers containing valid source citations.
- **Claim Citation Accuracy:** Accuracy of specific claim-to-source mappings.
- **Source Citation Precision:** Ratio of cited sources that were actually relevant.
- **Total Tokens Used:** Overall token consumption.

---

## 17. Full Re-Evaluation

### 17.1 Self-Test Mode (Verification Without Server)
Runs synthetic validation across all 12 pipeline stages to verify that evaluators, judges, math calculations, and graphing pipelines function with 0 errors:
```powershell
$env:PYTHONIOENCODING="utf-8"
.\.venv\Scripts\python.exe evaluation/run_eval.py --self-test
```
*Expected Result:*
```
[1/12] Dataset validation        PASS
[2/12] Query Execution            PASS
[3/12] Retrieval evaluation      PASS
[4/12] Generation evaluation     PASS
[5/12] Citation evaluation       PASS
[6/12] Performance evaluation    PASS
[7/12] Modality evaluation       PASS
[8/12] OCR evaluation            NOT RUN (requires verified OCR dataset)
[9/12] Audio evaluation          NOT RUN (requires verified audio dataset)
[10/12] Ablation experiments     PASS
[11/12] Provider Comparison      PASS (when --provider both)
[12/12] Reporting & Graphs       PASS
```

### 17.2 Re-Running Evaluation After Pipeline Modifications
If you modify:
- Chunk size or overlap in `backend/config.py`
- Embedding model (`TEXT_EMBED_MODEL`)
- Reranking model (`ms-marco-MiniLM-L-6-v2`)
- System prompt in `backend/generation/prompt_templates.py`

Run a full re-evaluation against the live backend:
```powershell
.\.venv\Scripts\python.exe evaluation/run_eval.py --base-url http://localhost:8000 --session-id real-eval-v1 --all
```
*Note: Each run generates a unique, timestamped folder under `reports/evaluation/` so historical benchmark data is never overwritten.*

---

## 18. Metrics Reference

| Category | Metric Name | Live Query? | Benchmark? | Comparison? | Ground Truth Needed? | Theoretical Formula / Logic |
|---|---|---|---|---|---|---|
| **Retrieval** | `Precision@K` | No | Yes | No | Yes | `(relevant items in top K) / K` |
| **Retrieval** | `Recall@K` | No | Yes | No | Yes | `(relevant items in top K) / (total relevant items)` |
| **Retrieval** | `F1@K` | No | Yes | No | Yes | Harmonic mean of `Precision@K` and `Recall@K` |
| **Retrieval** | `Hit@K` | No | Yes | No | Yes | `1.0` if at least 1 relevant item in top K, else `0.0` |
| **Retrieval** | `MRR` | No | Yes | No | Yes | `mean(1.0 / rank of first relevant item)` |
| **Retrieval** | `MAP` | No | Yes | No | Yes | `mean(Average Precision across queries)` |
| **Retrieval** | `nDCG@K` | No | Yes | No | Yes | `DCG@K / IDCG@K` with logarithmic discount |
| **Retrieval** | `ROC-AUC / PR-AUC` | No | Yes | No | Yes | Binary classification curve over retrieval confidence scores |
| **Generation** | `Answer Correctness` | No | Yes | Yes | Yes | Hybrid: `0.5 * Token_F1 + 0.5 * Semantic_Cosine_Sim` |
| **Generation** | `Answer Relevance` | No | Yes | Yes | No | Embedding similarity between question and generated answer |
| **Generation** | `Semantic Faithfulness`| Yes | Yes | Yes | No | `supported_claims / total_claims` via `FaithfulnessJudge` |
| **Generation** | `Token F1` | No | Yes | Yes | Yes | Harmonic mean of token-level precision and recall |
| **Generation** | `Exact Match` | No | Yes | No | Yes | Normalized string equality (`1.0` or `0.0`) |
| **Generation** | `Abstention Accuracy` | No | Yes | No | Yes | Accuracy of refusing unanswerable questions |
| **Citations** | `Citation Presence` | No | Yes | Yes | No | Percentage of answers containing at least one citation |
| **Citations** | `Claim Accuracy` | No | Yes | Yes | Yes | Citations that directly substantiate their associated claim |
| **Citations** | `Source Precision` | No | Yes | Yes | Yes | Ratio of cited sources that were in the ground-truth set |
| **Citations** | `Completeness` | No | Yes | No | Yes | Ratio of verifiable claims that received a citation |
| **Performance** | `Retrieval Latency` | Yes | Yes | Yes | No | End-to-end duration of search & reranking (ms) |
| **Performance** | `Generation Latency`| Yes | Yes | Yes | No | Time taken by LLM to complete generation (ms) |
| **Performance** | `TTFT` | Yes | Yes | Yes | No | Time to First Token from streaming chunk (ms) |
| **Performance** | `Throughput (tokens/s)`| Yes | Yes | Yes | No | `completion_tokens / (generation_seconds)` |
| **Performance** | `Latency Percentiles`| No | Yes | Yes | No | `P50`, `P75`, `P90`, `P95`, `P99` stage-wise latencies |

---

## 19. Reports & Artifacts

### 19.1 Output Directory Structure
Every evaluation run creates an isolated directory:
```
reports/
└── evaluation/
    └── 2026-09-30_121500/
        ├── summary.md                     <-- High-level markdown summary
        ├── summary.txt                    <-- ASCII terminal summary
        ├── summary.json                   <-- Full machine-readable metrics
        ├── raw_results.json               <-- Per-question evaluation breakdown
        ├── config.json                    <-- Evaluation configuration copy
        ├── environment.json               <-- Host, GPU, OS, package metadata
        ├── retrieval_metrics.csv          <-- P@K, R@K, MRR, MAP, nDCG
        ├── generation_metrics.csv         <-- Correctness, relevance, F1
        ├── citation_metrics.csv           <-- Precision, accuracy, completeness
        ├── performance_metrics.csv        <-- Stage latencies and percentiles
        ├── resource_metrics.csv           <-- CPU, RAM, GPU, VRAM usage
        ├── modality_metrics.csv           <-- Performance sliced by modality
        ├── ablation_results.csv           <-- Dense vs BM25 vs Hybrid comparisons
        ├── provider_comparison.csv        <-- (When --provider both)
        ├── provider_comparison.json       <-- (When --provider both)
        ├── provider_comparison.png        <-- (When --provider both)
        ├── graphs/
        │   ├── 01_precision_recall_at_k.png
        │   ├── 02_ranking_metrics.png
        │   ├── 05_stage_latencies.png
        │   ├── 06_generation_and_citations.png
        │   ├── 07_resource_usage.png
        │   └── 08_modality_comparison.png
        └── paper_tables/
            ├── table1_retrieval.tex
            ├── table2_generation.tex
            └── table3_ablation.tex
```

---

## 20. API Testing Without Frontend

You can test all endpoints using `curl` or PowerShell without the web frontend.

### 20.1 User Registration and Login
```powershell
# Register user
curl -X POST "http://localhost:8000/api/auth/register" `
  -H "Content-Type: application/json" `
  -d '{"email":"test@example.com","password":"Password123!"}'

# Login to get Bearer token
$loginResp = curl -X POST "http://localhost:8000/api/auth/login" `
  -H "Content-Type: application/json" `
  -d '{"email":"test@example.com","password":"Password123!"}' | ConvertFrom-Json

$token = $loginResp.token
Write-Host "Token: $token"
```

### 20.2 Test Active Provider & Discovery
```powershell
# Get active provider
curl -X GET "http://localhost:8000/api/llm/active" `
  -H "Authorization: Bearer $token"

# List Groq models
curl -X GET "http://localhost:8000/api/providers/groq/models" `
  -H "Authorization: Bearer $token"
```

### 20.3 Validate and Activate Groq Provider
```powershell
# Validate key
curl -X POST "http://localhost:8000/api/providers/validate" `
  -H "Authorization: Bearer $token" `
  -H "Content-Type: application/json" `
  -d '{"provider":"groq","api_key":"gsk_your_key_here"}'

# Store key encrypted
curl -X POST "http://localhost:8000/api/providers/key" `
  -H "Authorization: Bearer $token" `
  -H "Content-Type: application/json" `
  -d '{"provider":"groq","api_key":"gsk_your_key_here"}'

# Activate Groq with specific model
curl -X POST "http://localhost:8000/api/llm/providers/groq/activate" `
  -H "Authorization: Bearer $token" `
  -H "Content-Type: application/json" `
  -d '{"model":"llama-3.3-70b-versatile"}'
```

### 20.4 Query Endpoint
```powershell
curl -X POST "http://localhost:8000/api/query" `
  -H "Authorization: Bearer $token" `
  -H "Content-Type: application/json" `
  -d '{"session_id":"test-session-1","query":"What language model does this project use?","top_k":5}'
```

---

## 21. Complete Testing Matrix

| Test Case | Command / Action | Expected Result | Where to Verify |
|---|---|---|---|
| **Python Env** | `python -c "import torch; print(torch.__version__)"` | Displays PyTorch version (e.g. `2.5.1+cu121`) | Terminal stdout |
| **Backend Unit Test** | `python backend/verify_backend.py` | `All checks passed.` | Terminal stdout |
| **Backend Startup** | `uvicorn backend.main:app --port 8000` | Uvicorn running on `http://0.0.0.0:8000` | Terminal stdout |
| **Health Check** | `curl http://localhost:8000/api/health` | `{"status":"ok", ...}` | Browser / curl |
| **Frontend Build** | `npm run build` (in `frontend/`) | `✓ built in X.XXs` with 0 errors | Terminal stdout |
| **Frontend UI** | Open `http://localhost:8000/` | Chat UI renders with Sidebar & Header | Browser |
| **Ollama Daemon** | `ollama list` | Displays `qwen3:4b` | Terminal stdout |
| **Key Encryption** | Save key via ProviderPanel | Key encrypted in `provider_keys.json` | `backend/storage/` |
| **Provider Switch** | Select Groq & model in UI | Header badge switches to `GROQ — model` | Frontend Header |
| **Live Chat Query** | Ask question in chat UI | Streamed markdown answer with citations | Chat Window |
| **Terminal Scorecard**| Observe server terminal | Formatted ASCII evaluation scorecard | Backend Terminal |
| **Session Storage** | Inspect `storage/sessions/` | Message history includes `metrics` object | Session JSON file |
| **Self-Test Suite** | `python evaluation/run_eval.py --self-test`| All 12 evaluation stages pass with 0 errors | Terminal stdout |
| **Ollama Benchmark** | `python evaluation/run_eval.py --provider ollama --all` | Generates full evaluation report | `reports/evaluation/` |
| **Groq Benchmark** | `python evaluation/run_eval.py --provider groq --all` | Generates full evaluation report | `reports/evaluation/` |
| **Comparison** | `python evaluation/run_eval.py --provider both --all` | Produces CSV, JSON, and PNG comparison | `reports/evaluation/` |

---

## 22. Troubleshooting

### 1. UnicodeEncodeError in Terminal (`charmap codec can't encode character '\u2713'`)
- **Cause:** Windows PowerShell console defaults to `cp1252` legacy encoding.
- **Fix:** Run this before running Python commands:
  ```powershell
  $env:PYTHONIOENCODING="utf-8"
  ```

### 2. ModuleNotFoundError: No module named 'torch'
- **Cause:** Using global Python instead of the virtual environment.
- **Fix:** Always use the dedicated virtual environment Python:
  ```powershell
  .\.venv\Scripts\python.exe <command>
  ```

### 3. Groq API Key Rejected or Unauthorized (401)
- **Cause:** Key is expired, invalid, or has whitespace.
- **Fix:** Verify key with curl:
  ```powershell
  curl -H "Authorization: Bearer $env:GROQ_API_KEY" "https://api.groq.com/openai/v1/models"
  ```

### 4. Ollama Shows Offline / Extractive Fallback Triggered
- **Cause:** Ollama daemon is stopped or listening on a non-standard port.
- **Fix:** Start Ollama service (`ollama serve` or open Ollama desktop app) and verify `ollama list`.

### 5. Backend Port Conflict (Port 8000 already in use)
- **Fix:** Identify and stop the occupying process:
  ```powershell
  Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess | Stop-Process
  ```

---

## 23. Reproducibility Guide

To ensure experimental reproducibility across runs:
1. **Deterministic Random Seed:** All evaluators seed Python random, NumPy, and PyTorch with `seed: 42` (configured in `evaluation/config/evaluation_config.yaml`).
2. **Deterministic Retrieval:** Comparative experiments execute retrieval once and feed identical candidate chunks to both Ollama and Groq.
3. **Environment Capture:** Every run generates an `environment.json` recording:
   - Operating system and kernel version
   - CPU model and core count
   - RAM capacity and GPU model / VRAM
   - Exact Python version and pip package freeze
   - Ollama host and model tag
   - Groq model and SDK version

---

## 24. Research & Paper Verification

The benchmark suite is specifically structured to produce artifacts ready for academic and technical papers:
- **Retrieval Metrics (`table1_retrieval.tex`):** Reports P@K, R@K, F1@K, MRR, MAP, and nDCG@K.
- **Generation & Citation Metrics (`table2_generation.tex`):** Reports Answer Correctness, Semantic Faithfulness, Token-F1, Claim Citation Accuracy, and Source Citation Precision.
- **Ablation Studies (`ablation_results.csv`):** Quantifies contributions of Dense vs BM25 vs Hybrid retrieval vs RRF reranking.
- **Provider Comparison Chart (`provider_comparison.png`):** High-resolution (300 DPI) grouped bar chart suitable for publication.

---

## 25. Final Verification Checklist

Use this checklist to confirm the entire project is operating at 100%:

- [ ] Python 3.11 virtual environment active with PyTorch and CUDA.
- [ ] Backend smoke test passes: `python backend/verify_backend.py`.
- [ ] Backend starts up with 0 errors on `http://localhost:8000`.
- [ ] Frontend builds cleanly with 0 errors: `npm run build`.
- [ ] Frontend loads in browser at `http://localhost:8000`.
- [ ] Ollama daemon running with `qwen3:4b` pulled.
- [ ] Groq API key validated and stored encrypted in `backend/storage/provider_keys.json`.
- [ ] Provider switching functions between Ollama and Groq with live model discovery.
- [ ] Header banner displays active provider and model with appropriate status dot.
- [ ] Sample document ingested into a chat session.
- [ ] User query answered with clickable source citations.
- [ ] Backend terminal displays clean, ASCII-safe evaluation scorecard on live query.
- [ ] Session JSON file contains query evaluation metrics under `messages[].metrics`.
- [ ] Evaluation self-test passes all 12 stages: `python evaluation/run_eval.py --self-test`.
- [ ] Ollama benchmark evaluation runs: `python evaluation/run_eval.py --provider ollama --all`.
- [ ] Groq benchmark evaluation runs: `python evaluation/run_eval.py --provider groq --all`.
- [ ] Provider comparison runs: `python evaluation/run_eval.py --provider both --all`.
- [ ] Comparison CSV, JSON, and PNG charts generated in `reports/evaluation/`.

---

## 26. Command Cheat Sheet

```powershell
# ============================================================
# 1. ENVIRONMENT & BACKEND STARTUP
# ============================================================
$env:PYTHONIOENCODING="utf-8"
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

# ============================================================
# 2. FRONTEND PRODUCTION BUILD
# ============================================================
cd frontend
npm run build
cd ..

# ============================================================
# 3. OLLAMA VERIFICATION
# ============================================================
ollama list
ollama pull qwen3:4b

# ============================================================
# 4. EVALUATION PIPELINE EXECUTION
# ============================================================
# Self-Test (Plumbing verification, no live server needed)
.\.venv\Scripts\python.exe evaluation/run_eval.py --self-test

# Ollama Evaluation
.\.venv\Scripts\python.exe evaluation/run_eval.py --provider ollama --all

# Groq Evaluation (Cloud)
$env:GROQ_API_KEY="gsk_your_key_here"
.\.venv\Scripts\python.exe evaluation/run_eval.py --provider groq --all

# Comparative Evaluation (Ollama vs. Groq)
.\.venv\Scripts\python.exe evaluation/run_eval.py --provider both --all
```

---

## 27. Expected Final State

When all verification steps in this guide have been completed:
1. **Production Web Application:** Running at `http://localhost:8000`, serving the compiled React frontend, handling multi-user registration, chat sessions, document uploads, and live streaming answers.
2. **Dual-Provider Runtime:** Users can switch back and forth between local offline inference (`Ollama / qwen3:4b`) and cloud acceleration (`Groq / llama-3.3-70b-versatile`) with live model discovery.
3. **Telemetry & Auditability:** Live queries generate instantaneous terminal scorecards with zero clutter in the user chat UI, while persisting metrics to session storage.
4. **Research Benchmark Suite:** The `reports/evaluation/` directory contains complete, reproducible evaluation bundles including CSV metric matrices, structured JSON summaries, publication-ready PNG graphs, and LaTeX paper tables.
