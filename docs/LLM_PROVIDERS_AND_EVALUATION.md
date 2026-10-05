# LLM Providers & Evaluation Architecture Guide

This guide details the dual-provider LLM infrastructure (Ollama & Groq), runtime switching, encrypted API key management, frontend-triggered per-query terminal metrics, and the research-grade evaluation pipeline.

---

## Table of Contents

1. [Architectural Overview](#1-architectural-overview)
2. [Ollama vs. Groq Capabilities](#2-ollama-vs-groq-capabilities)
3. [Groq Setup & API Key Management](#3-groq-setup--api-key-management)
4. [Runtime Switching & Model Discovery](#4-runtime-switching--model-discovery)
5. [Frontend-Triggered Query Evaluation (Terminal-Only)](#5-frontend-triggered-query-evaluation-terminal-only)
6. [Metric Persistence & Session Storage](#6-metric-persistence--session-storage)
7. [Running the Terminal Evaluation Suite](#7-running-the-terminal-evaluation-suite)
8. [Ollama vs. Groq Comparative Experiments](#8-ollama-vs-groq-comparative-experiments)
9. [Troubleshooting & Verification](#9-troubleshooting--verification)

---

## 1. Architectural Overview

The system features a hybrid inference engine supporting both local and cloud LLM execution:

```
                  ┌─────────────────────────────────────────┐
                  │       Frontend UI (React + Vite)        │
                  │   - Active Provider / Model Banner      │
                  │   - ProviderPanel: Key Input & Dropdown │
                  └────────────────────┬────────────────────┘
                                       │ HTTP / SSE Stream
                                       ▼
                  ┌─────────────────────────────────────────┐
                  │           FastAPI Backend               │
                  │   - /api/query & /api/query/stream      │
                  │   - active_provider (per-user state)    │
                  │   - keystore (Fernet AES-128-CBC)       │
                  └─────────┬─────────────────────┬─────────┘
                            │                     │
               ┌────────────▼──────────┐ ┌────────▼──────────┐
               │    Ollama (Local)     │ │    Groq (Cloud)   │
               │  - Host: 11434        │ │  - SDK / OpenAI   │
               │  - Model: qwen3:4b    │ │  - Llama 3.3 70B  │
               │  - Fully Offline      │ │  - Ultra-low TTFT │
               └────────────┬──────────┘ └────────┬──────────┘
                            │                     │
                            └──────────┬──────────┘
                                       │
                                       ▼
                  ┌─────────────────────────────────────────┐
                  │      Terminal Metric Scorecard          │
                  │   - Latency (Retrieval, Gen, TTFT, E2E) │
                  │   - Tokens & Throughput (tokens/sec)    │
                  │   - Semantic Faithfulness & Grounding   │
                  │   - Persisted in session storage        │
                  └─────────────────────────────────────────┘
```

---

## 2. Ollama vs. Groq Capabilities

| Feature | Ollama (Local) | Groq (Cloud) |
|---|---|---|
| **Privacy & Modality** | 100% Offline, on-device data processing | Cloud inference via Groq LPUs |
| **Default Model** | `qwen3:4b` (configurable via `LLM_MODEL`) | `llama-3.3-70b-versatile` |
| **Speed / TTFT** | Dependent on local GPU/VRAM (~20-50 tokens/s) | Ultra-fast (~150-300+ tokens/s, <250ms TTFT) |
| **Model Selection** | Pre-pulled Ollama models | Live dynamic discovery via Groq API |
| **Hardware Reqs** | GPU with 4GB+ VRAM recommended | Any hardware (cloud API) |
| **Failure Handling** | Local fallback extractor | Automatic failover to local Ollama |

---

## 3. Groq Setup & API Key Management

### Step 1: Obtain a Free Groq API Key
1. Go to [Groq Console](https://console.groq.com/).
2. Create an account or sign in.
3. Navigate to **API Keys** and click **Create API Key**.
4. Copy the generated key (`gsk_...`).

### Step 2: Configure via Frontend UI
1. Open the application at `http://localhost:8000/`.
2. Click the **LLM Providers** button in the header.
3. In the Groq section:
   - Paste your API key into the **API Key** input.
   - Click **Save Key & Validate**.
   - The backend validates the key against `https://api.groq.com/openai/v1/models`.
   - Once validated, the **Model** dropdown populates with all live Groq models.
   - Choose your preferred model (e.g. `llama-3.3-70b-versatile`, `llama-3.1-8b-instant`).
   - Click **Activate Provider**.

### Step 3: Zero-Leak Encryption at Rest
All API keys are encrypted using Fernet (AES-128-CBC with SHA256 HMAC):
- **Secret Key:** Generated once and saved to `backend/storage/keys.secret` (600 permissions).
- **Encrypted Keys:** Saved in `backend/storage/provider_keys.json` with strict user isolation (`user_id -> provider -> encrypted_blob`).
- Plaintext API keys **never** appear in logs or unencrypted disk files.

---

## 4. Runtime Switching & Model Discovery

### Dynamic Model Discovery
When a valid Groq API key is present, the backend queries the live Groq models endpoint:
```http
GET /api/providers/groq/models
Authorization: Bearer <user_token>
```
Response:
```json
{
  "provider": "groq",
  "models": [
    {"id": "llama-3.3-70b-versatile", "name": "llama-3.3-70b-versatile", "context_window": 128000},
    {"id": "llama-3.1-8b-instant", "name": "llama-3.1-8b-instant", "context_window": 128000},
    {"id": "mixtral-8x7b-32768", "name": "mixtral-8x7b-32768", "context_window": 32768}
  ],
  "default_model": "llama-3.3-70b-versatile",
  "source": "api"
}
```
*Note: If the network is unavailable during lookup, it seamlessly falls back to the curated built-in default models list.*

### Switching Providers via REST API
To switch to Groq with a specific model:
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

### Checking Active Provider State
```http
GET /api/llm/active
Authorization: Bearer <user_token>
```
Returns:
```json
{
  "provider": "groq",
  "model": "llama-3.3-70b-versatile",
  "is_cloud": true
}
```

---

## 5. Frontend-Triggered Query Evaluation (Terminal-Only)

### Design Principle: No UI Clutter, Complete Terminal Telemetry
When a query is submitted from the frontend UI:
1. The frontend initiates retrieval and answer streaming.
2. The user sees a clean, professional chat experience with markdown answers, citations, and source inspection.
3. The frontend **does not** display complex evaluation metrics in the chat UI.
4. Concurrently, the backend calculates all performance and quality metrics and writes a structured scorecard directly to the server terminal (`stdout`).

### Example Terminal Scorecard Output
```
================================================================
[EVAL] RAG QUERY METRICS | Session: c7e1f40d-fa20-410a-b28d-192a83e0bb42
================================================================
  Query:            "Explain how cross-attention works in multimodal models"
  Active LLM:       GROQ (llama-3.3-70b-versatile)
  LLM Used:         Yes
----------------------------------------------------------------
  LATENCY BREAKDOWN:
    - Retrieval:        142.6 ms  (Hits: 5)
    - Generation:       728.3 ms
    - TTFT:             185.0 ms
    - Total E2E:        870.9 ms
----------------------------------------------------------------
  THROUGHPUT & TOKENS:
    - Prompt Tokens:        1140
    - Completion Tokens:     284
    - Total Tokens:         1424
    - Output Speed:        390.0 tokens/sec
----------------------------------------------------------------
  QUALITY & FAITHFULNESS:
    - Faithfulness:      0.95 (95.0% grounded) [HIGH]
    - Claim Grounding:   4/4 claims supported by sources
================================================================
```

### Metrics Tracked in Scorecard:
- **Retrieval Latency:** Time spent on hybrid dense + sparse BM25 + CLIP + RRF + Cross-Encoder reranking.
- **Generation Latency:** Total generation execution duration.
- **TTFT (Time to First Token):** Time elapsed until the first generated token arrives.
- **Total E2E Latency:** Complete request turn-around time.
- **Prompt & Completion Tokens:** Context consumption and response length.
- **Output Speed:** Tokens generated per second.
- **Faithfulness Score:** Evaluated via `FaithfulnessJudge`, verifying generated statements against retrieved context.

---

## 6. Metric Persistence & Session Storage

In addition to stdout printing, metrics are saved directly inside each chat session's persistent history (`backend/storage/sessions/{session_id}.json`):

```json
{
  "role": "assistant",
  "text": "Cross-attention allows the text query to attend to visual tokens...",
  "citations": [
    {"source": "attention_paper.pdf", "page": 4, "snippet": "..."}
  ],
  "usedLlm": true,
  "provider": "groq",
  "model": "llama-3.3-70b-versatile",
  "metrics": {
    "provider": "groq",
    "model": "llama-3.3-70b-versatile",
    "retrieval_ms": 142.6,
    "generation_ms": 728.3,
    "total_latency_ms": 870.9,
    "ttft_ms": 185.0,
    "prompt_tokens": 1140,
    "completion_tokens": 284,
    "tokens_per_second": 390.0,
    "faithfulness_score": 0.95,
    "supported_claims": 4,
    "total_claims": 4,
    "used_llm": true
  }
}
```
This enables post-hoc analysis, session auditing, and comparative review across different sessions and providers without losing experimental provenance.

---

## 7. Running the Terminal Evaluation Suite

The offline evaluation suite under `evaluation/` evaluates retrieval, generation, citation precision, and system performance without altering any production code.

### Prerequisites
Run within the Python environment:
```bash
# Windows
.\.venv\Scripts\python.exe evaluation/run_eval.py --self-test

# Linux / Mac
python evaluation/run_eval.py --self-test
```

### CLI Command Options

#### 1. Self-Test Mode (Plumbing Verification)
Runs synthetic validation across all 12 pipeline stages:
```bash
python evaluation/run_eval.py --self-test
```

#### 2. Evaluate Local Ollama
Evaluates local generation against a target evaluation dataset:
```bash
python evaluation/run_eval.py --provider ollama --all
```

#### 3. Evaluate Cloud Groq
Evaluates Groq cloud generation (requires `GROQ_API_KEY` set in environment or encrypted keystore):
```bash
python evaluation/run_eval.py --provider groq --all
```

#### 4. Run Side-by-Side Comparison
Executes both providers over identical retrieved contexts and outputs comparison tables and charts:
```bash
python evaluation/run_eval.py --provider both --all
```

---

## 8. Ollama vs. Groq Comparative Experiments

When running `--provider both`, the experiment runner executes `evaluation/experiments/provider_experiments.py`:

1. **Deterministic Retrieval:** Retrieves contexts once per benchmark question.
2. **Dual Generation:** Feeds the exact same context to Ollama (`qwen3:4b`) and Groq (`llama-3.3-70b-versatile`).
3. **Comparative Metrics Matrix:**
   - Answer Correctness (Mean)
   - Answer Relevance (Mean)
   - Semantic Faithfulness (Mean)
   - Token F1 (Mean)
   - Citation Presence Rate
   - Claim Citation Accuracy
   - Source Citation Precision
   - Total Tokens Used
   - Speed & Latency Percentiles (P50, P95)
4. **Generated Artifacts** (stored under `reports/evaluation/<timestamp>/`):
   - `provider_comparison.csv` — CSV metric comparison table
   - `provider_comparison.json` — Raw JSON metrics and evaluation outputs
   - `provider_comparison.png` — Grouped bar chart comparing Ollama vs. Groq

---

## 9. Troubleshooting & Verification

### Issue: Groq Provider shows "API key invalid"
- Verify that your Groq API key starts with `gsk_` and has no trailing spaces.
- Test connection directly:
  ```bash
  curl -X GET "https://api.groq.com/openai/v1/models" -H "Authorization: Bearer <YOUR_GROQ_KEY>"
  ```

### Issue: Ollama Provider shows "Ollama offline"
- Ensure Ollama daemon is running:
  ```bash
  ollama list
  ```
- Pull the required model if not already present:
  ```bash
  ollama pull qwen3:4b
  ```

### Issue: Terminal Scorecard Not Displaying
- Ensure your backend terminal has standard output unbuffered:
  ```powershell
  $env:PYTHONIOENCODING="utf-8"
  ```
- The scorecard is printed immediately upon query completion (both `/api/query` and `/api/query/stream`).
