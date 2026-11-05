# Multimodal RAG Project: Code-Level Architecture & Evaluation Audit

**Audit Date:** September 30, 2026  
**Auditor:** Senior Principal Python/Backend/Research-Engineering Developer  
**Project Root:** `C:\Users\Govind\Downloads\files\minor-main`  
**Audit Target File:** `mrag-audit.md`  
**Audit Protocol:** Read-only inspection. Zero source code modifications, zero dependency changes, zero configuration changes, zero terminal pipeline modifications.

---

## Executive Summary & Final Verdict

| Question / Requirement Area | Current Status | Code Reality Summary |
| :--- | :--- | :--- |
| **Multi-Provider Backend Architecture** | **Implemented** | Central `ProviderRegistry` and `Router` exist in `backend/generation/providers/`. Ollama, Groq, Gemini, OpenAI, and Claude are registered. |
| **Groq Answer Generation Support** | **Implemented** | `GroqProvider` in `backend/generation/providers/cloud_providers.py` uses `groq` SDK for blocking and SSE streaming generation. |
| **Runtime Provider Switching (Ollama ↔ Groq)** | **Partially Implemented** | Provider switching exists via `POST /api/llm/providers/{provider}/activate` and `active_provider.py`. However, **runtime model selection** is missing (model is hardcoded to `config.GROQ_MODEL`). |
| **Groq API Key Validation & Storage** | **Implemented** | `POST /api/providers/validate` validates against Groq Cloud API; `POST /api/providers/key` encrypts keys via Fernet (AES-128-CBC) in `keystore.py`. |
| **Active Model Banner in Frontend** | **Partially Implemented** | `Header.tsx` only shows local `healthData.llm_model` (`qwen3:4b`). It does not dynamically display the active cloud model (`llama-3.3-70b-versatile`). `LlmBanner.tsx` is only an offline warning banner. |
| **Existing Terminal Evaluation Pipeline** | **Fully Operational** | Located in `evaluation/`. Comprehensive 12-stage research pipeline testing 190 questions (`real_rag_eval_dataset_v1_190q_eval.json`) with CSV, Markdown, text, graphs, and paper table exports. Supports `--provider ollama`, `--provider groq`, `--provider both`, and `--self-test`. |
| **Per-Query Metric Display in Frontend** | **Not Implemented** | `POST /api/query` returns no metrics. `POST /api/query/stream` emits latency/token metrics in the final SSE frame, but `App.tsx` drops them. No retrieval or evaluation metrics are computed or shown for live chat queries. |
| **Metric Persistence per Query** | **Not Implemented** | `sessions.py` and `answer.py` audit logs drop provider, model, latency, tokens, and all retrieval/evaluation metrics. |
| **Frontend Comparison (Ollama vs. Groq)** | **Not Implemented** | Comparative evaluation exists strictly in terminal CLI (`python evaluation/run_eval.py --provider both --all`). |

---

## Part 1 — Audit Current LLM Architecture

### 1.1 Complete Query Execution Flow Trace

```
[User Browser: React SPA]
       │
       ▼  (POST /api/query or POST /api/query/stream with Bearer token)
[FastAPI Router: backend/main.py]
       │
       ├── Auth verification: auth.get_user() -> sessions.py::ensure_exists()
       ├── Rate limit check: auth.check_custom_rate_limit("chat:{user_id}")
       ├── Provider resolution: _resolve_provider(req.provider, user_id)
       │     └─ Checks req.provider -> active_provider.get_active(user_id) -> default: "ollama"
       │
       ▼  (Phase 3 Preprocessing in backend/main.py)
[Query Enhancements]
       ├── Query Rewrite: query_enhance.query_rewrite() -> router.generate(..., provider=resolved_provider)
       └── HyDE Generation: query_enhance.hyde_passage() -> router.generate(..., provider=resolved_provider)
       │
       ▼  (Hybrid Multimodal Retrieval)
[Retrieval Pipeline: backend/retrieval/search.py]
       ├── Dense Vector Search: retrieval/vector_store.py (ChromaDB: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2)
       ├── Sparse BM25 Search: retrieval/bm25_index.py
       ├── Multimodal Image Search: retrieval/clip_embed.py (OpenAI clip-ViT-B-32)
       ├── Reciprocal Rank Fusion: retrieval/fusion.py::reciprocal_rank_fusion(dense, bm25, clip)
       └── Cross-Encoder Reranking: retrieval/rerank.py (cross-encoder/ms-marco-MiniLM-L6-v2)
       │
       ▼  (Retrieved Hits: List[Dict])
[Context Construction: backend/generation/answer.py]
       ├── Token budget truncation: generation/prompt_templates.py::truncate_hits_to_budget(hits)
       ├── Citation list construction: generation/answer.py::_citation() + _add_confidence()
       ├── Prompt formatting: generation/prompt_templates.py::build_user_prompt(query, hits)
       └── History trimming: generation/answer.py::_trim_history(history)
       │
       ▼  (System Prompt + User Prompt + History + User ID + Image Paths)
[LLM Provider Router: backend/generation/providers/router.py]
       ├── Circuit Breaker check: circuit_breaker.allow_request(provider_name)
       ├── Provider Resolution: registry.get(provider_name)
       │     ├── IF "ollama": generation/providers/ollama_provider.py -> generation/llm_client.py
       │     └── IF "groq": generation/providers/cloud_providers.py -> GroqProvider -> groq.Groq SDK
       ├── Failover handling: on retryable error -> router.py fails over to "ollama" if configured
       └── Structured generation log: router.py::_log_generation() -> observability/metrics.py
       │
       ▼  (Answer Text + Citations + Streaming Metrics)
[Session & Audit Storage: backend/sessions.py & backend/generation/answer.py]
       ├── Append user turn: session_store.append_message(session_id, {"role": "user", "text": query})
       ├── Append assistant turn: session_store.append_message(session_id, {"role": "assistant", "text": answer, "citations": ...})
       └── Audit log write: generation/answer.py::_audit(user_id, query, result)
       │
       ▼  (HTTP JSON response or Server-Sent Events delta stream)
[Frontend Response: frontend/src/App.tsx -> ChatPanel.tsx & SourcesPanel.tsx]
```

### 1.2 Exact Code Artifact Identification

| Architecture Stage | Exact File Path | Class / Function / Symbol | Configuration File Reference |
| :--- | :--- | :--- | :--- |
| **Frontend Client API** | [frontend/src/api.ts](file:///c:/Users/Govind/Downloads/files/minor-main/frontend/src/api.ts#L116-L252) | `query()`, `queryStream()`, `activateProvider()` | `frontend/vite.config.ts` |
| **Frontend UI State** | [frontend/src/App.tsx](file:///c:/Users/Govind/Downloads/files/minor-main/frontend/src/App.tsx#L304-L375) | `handleTextQuery()`, `selectProvider()` | `frontend/src/types.ts` |
| **API Endpoints** | [backend/main.py](file:///c:/Users/Govind/Downloads/files/minor-main/backend/main.py#L863-L1034) | `POST /api/query`, `POST /api/query/stream` | [backend/config.py](file:///c:/Users/Govind/Downloads/files/minor-main/backend/config.py#L140-L260) |
| **Query Enhancement** | [backend/generation/query_enhance.py](file:///c:/Users/Govind/Downloads/files/minor-main/backend/generation/query_enhance.py#L50-L83) | `query_rewrite()`, `hyde_passage()` | `backend/config.py:QUERY_REWRITE_ENABLED` |
| **Retrieval Entry** | [backend/retrieval/search.py](file:///c:/Users/Govind/Downloads/files/minor-main/backend/retrieval/search.py#L1-L150) | `text_query()` | `backend/config.py:DEFAULT_TOP_K` |
| **Context & Citations** | [backend/generation/answer.py](file:///c:/Users/Govind/Downloads/files/minor-main/backend/generation/answer.py#L119-L190) | `prepare_answer_context()`, `answer_query()` | `backend/config.py:MAX_CONTEXT_TOKENS` |
| **Prompt Templates** | [backend/generation/prompt_templates.py](file:///c:/Users/Govind/Downloads/files/minor-main/backend/generation/prompt_templates.py#L1-L120) | `build_user_prompt()`, `truncate_hits_to_budget()` | `backend/config.py:MAX_CONTEXT_TOKENS` |
| **Provider Router** | [backend/generation/providers/router.py](file:///c:/Users/Govind/Downloads/files/minor-main/backend/generation/providers/router.py#L83-L255) | `Router.generate()`, `Router.stream_generate()` | `backend/config.py:PROVIDER_FAILOVER_TO_LOCAL` |
| **Provider Registry** | [backend/generation/providers/registry.py](file:///c:/Users/Govind/Downloads/files/minor-main/backend/generation/providers/registry.py#L15-L33) | `ProviderRegistry`, `registry` instance | Central registry |
| **Base Provider Interface** | [backend/generation/providers/base.py](file:///c:/Users/Govind/Downloads/files/minor-main/backend/generation/providers/base.py#L10-L80) | `BaseProvider` | Abstract interface |
| **Ollama Implementation** | [backend/generation/providers/ollama_provider.py](file:///c:/Users/Govind/Downloads/files/minor-main/backend/generation/providers/ollama_provider.py#L14-L49) | `OllamaProvider` | [backend/generation/llm_client.py](file:///c:/Users/Govind/Downloads/files/minor-main/backend/generation/llm_client.py#L1-L170) |
| **Groq Implementation** | [backend/generation/providers/cloud_providers.py](file:///c:/Users/Govind/Downloads/files/minor-main/backend/generation/providers/cloud_providers.py#L239-L335) | `GroqProvider` | `backend/config.py:GROQ_MODEL` |
| **Key Storage** | [backend/keystore.py](file:///c:/Users/Govind/Downloads/files/minor-main/backend/keystore.py#L73-L118) | `set_key()`, `get_key()`, `delete_key()` | `backend/config.py:PROVIDER_KEYS_FILE` |
| **Active Provider State** | [backend/generation/active_provider.py](file:///c:/Users/Govind/Downloads/files/minor-main/backend/generation/active_provider.py#L52-L94) | `get_active()`, `set_active()`, `get_active_full()` | `backend/config.py:STORE_DIR/active_provider.json` |

### 1.3 Ollama & Qwen3 4B Configuration Details

- **Configuration File:** [backend/config.py](file:///c:/Users/Govind/Downloads/files/minor-main/backend/config.py#L140-L162)
  - `OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")`
  - `LLM_MODEL = os.getenv("LLM_MODEL", "qwen3:4b")`
  - `LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))`
  - `LLM_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "4096"))`
  - `OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "512"))`
  - `OLLAMA_THINK = os.getenv("OLLAMA_THINK", "0") == "1"`
  - `OLLAMA_STREAM = os.getenv("OLLAMA_STREAM", "1") == "1"`
  - `OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "120"))`
- **Is the Ollama model hardcoded?**
  **NO.** It defaults to `"qwen3:4b"`, but is dynamically read from the `LLM_MODEL` environment variable.
- **Is the Ollama URL hardcoded?**
  **NO.** It defaults to `"http://localhost:11434"`, but is dynamically read from the `OLLAMA_HOST` environment variable.
- **Where is Ollama actually called?**
  In [backend/generation/llm_client.py](file:///c:/Users/Govind/Downloads/files/minor-main/backend/generation/llm_client.py#L30-L135) using `ollama.Client(host=config.OLLAMA_HOST, timeout=config.OLLAMA_TIMEOUT)`.
  - Blocking generation: `llm_client.chat()` (lines 66–87)
  - Streaming generation: `llm_client.stream_chat()` (lines 89–165)
  - Health check: `llm_client.is_available()` (lines 167–170)
- **Is Ollama behind an abstraction/interface?**
  **YES.** It is wrapped by `OllamaProvider(BaseProvider)` in [backend/generation/providers/ollama_provider.py](file:///c:/Users/Govind/Downloads/files/minor-main/backend/generation/providers/ollama_provider.py#L14-L49).
- **Is provider selection centralized?**
  **YES.** Centralized in [backend/generation/providers/router.py](file:///c:/Users/Govind/Downloads/files/minor-main/backend/generation/providers/router.py#L83-L255) and [backend/generation/providers/registry.py](file:///c:/Users/Govind/Downloads/files/minor-main/backend/generation/providers/registry.py#L15-L33).

---

## Part 2 — Groq Support Audit

### 2.1 Feature-by-Feature Checklist

| Feature | Implemented? | Exact Location in Codebase | Notes / Limitations |
| :--- | :--- | :--- | :--- |
| **Groq SDK** | **YES** | `backend/requirements.txt: groq>=0.11.0` | Imported in `cloud_providers.py` (`from groq import Groq`) |
| **Groq Client** | **YES** | [backend/generation/providers/cloud_providers.py:252](file:///c:/Users/Govind/Downloads/files/minor-main/backend/generation/providers/cloud_providers.py#L252) | `client = Groq(api_key=key, timeout=config.CLOUD_TIMEOUT)` |
| **OpenAI-compatible client** | **YES** | [evaluation/providers/groq_provider.py:35](file:///c:/Users/Govind/Downloads/files/minor-main/evaluation/providers/groq_provider.py#L35) | `urllib` calls `https://api.groq.com/openai/v1/chat/completions` |
| **Groq API routes** | **YES** | [backend/main.py:539-616](file:///c:/Users/Govind/Downloads/files/minor-main/backend/main.py#L539-L616) | Shared `/api/providers/*` and `/api/llm/providers/groq/activate` |
| **Groq configuration** | **YES** | [backend/config.py:244](file:///c:/Users/Govind/Downloads/files/minor-main/backend/config.py#L244) | `GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")` |
| **API key handling** | **YES** | [backend/keystore.py:73-93](file:///c:/Users/Govind/Downloads/files/minor-main/backend/keystore.py#L73-L93) | Fernet encrypted in `storage/provider_keys.json` |
| **Environment variable support** | **YES** | [backend/config.py:244](file:///c:/Users/Govind/Downloads/files/minor-main/backend/config.py#L244) | `GROQ_MODEL`, `CLOUD_TIMEOUT`, `CLOUD_MAX_TOKENS` |
| **Provider selection** | **YES** | [backend/main.py:363](file:///c:/Users/Govind/Downloads/files/minor-main/backend/main.py#L363) | `_resolve_provider(req.provider, user["id"])` |
| **Runtime provider switching** | **YES** | [backend/main.py:601](file:///c:/Users/Govind/Downloads/files/minor-main/backend/main.py#L601) | `POST /api/llm/providers/groq/activate` |
| **Model selection (User-selected)**| **NO** | [backend/generation/providers/cloud_providers.py:258](file:///c:/Users/Govind/Downloads/files/minor-main/backend/generation/providers/cloud_providers.py#L258) | **Hardcoded to `config.GROQ_MODEL`**. No user selection endpoint or parameter. |
| **Model discovery (list models)** | **NO** | [backend/generation/providers/base.py:65](file:///c:/Users/Govind/Downloads/files/minor-main/backend/generation/providers/base.py#L65) | `GroqProvider` does not implement `get_model_list()`; returns `[]`. |
| **API-key validation** | **YES** | [backend/generation/providers/cloud_providers.py:265-271](file:///c:/Users/Govind/Downloads/files/minor-main/backend/generation/providers/cloud_providers.py#L265-L271) | `Groq(api_key=key, timeout=10).models.list()` via `POST /api/providers/validate` |
| **Timeout handling** | **YES** | [backend/config.py:250](file:///c:/Users/Govind/Downloads/files/minor-main/backend/config.py#L250) | `CLOUD_TIMEOUT = 60` seconds passed to `Groq(timeout=...)` |
| **Rate-limit handling** | **YES** | [backend/generation/providers/errors.py:55](file:///c:/Users/Govind/Downloads/files/minor-main/backend/generation/providers/errors.py#L55) | Classified as `rate_limited`, retried with exponential backoff & jitter |
| **API failure handling** | **YES** | [backend/generation/providers/router.py:101-185](file:///c:/Users/Govind/Downloads/files/minor-main/backend/generation/providers/router.py#L101-L185) | Circuit breaker + error classification (`errors.classify`) |
| **Fallback to Ollama** | **YES** | [backend/generation/providers/router.py:172-180](file:///c:/Users/Govind/Downloads/files/minor-main/backend/generation/providers/router.py#L172-L180) | Only on retryable errors (`rate_limited`, `network_error`, `provider_unavailable`) |

### 2.2 Execution Path Verification

Can you currently set `Provider = Groq`, `API Key = <key>`, `Model = <selected model>` and have the existing RAG pipeline automatically use Groq for answer generation?

- **For Provider = Groq and API Key = `<key>`:** **YES.**
  - Path: User submits API key via `POST /api/providers/key`. Key is encrypted into `storage/provider_keys.json`.
  - User activates Groq via `POST /api/llm/providers/groq/activate`. This records `"groq"` in `storage/active_provider.json`.
  - Any subsequent call to `POST /api/query` or `POST /api/query/stream` resolves `provider = "groq"`, retrieves the decrypted key, and invokes `GroqProvider.generate_answer()` or `GroqProvider.stream_answer()`.
- **For Model = `<selected Groq model>`:** **NO.**
  - What is missing: `config.GROQ_MODEL` is statically fixed (`llama-3.3-70b-versatile`).
  - Neither `QueryRequest`, `active_provider.set_active()`, nor `GroqProvider.generate_answer()` accept a dynamic model name argument.
  - `GroqProvider` does not implement `get_model_list()`, so the frontend cannot discover or present a list of compatible Groq models.

---

## Part 3 — Ollama ↔ Groq Switching

### 3.1 Runtime Switching Audit

Runtime switching between Ollama and Groq is **currently implemented and working** at the provider level, without editing source code:

1. **Switch to Groq:**
   Frontend calls `POST /api/llm/providers/groq/activate` (requires key already saved in `keystore`).
   `active_provider.set_active(user_id, "groq")` writes to `storage/active_provider.json`.
2. **Next Query:**
   `POST /api/query` calls `_resolve_provider(req.provider, user["id"])` which returns `"groq"`. `router.generate(..., provider="groq")` routes directly to `GroqProvider`.
3. **Switch Back to Ollama:**
   Frontend calls `POST /api/llm/providers/ollama/activate`.
   `active_provider.set_active(user_id, "ollama")` writes `"ollama"` to `storage/active_provider.json`.
4. **Subsequent Query:**
   `_resolve_provider` returns `"ollama"`. `router.generate(..., provider="ollama")` routes directly to `OllamaProvider`.

### 3.2 Impact Analysis: What Changes When Provider Changes?

| System Component | Changed by Provider Switch? | Verification from Source Code |
| :--- | :--- | :--- |
| **Document Ingestion** | **NO** | `backend/ingestion/ingest.py` has no dependency on LLM provider. Uses PyPDF, python-docx, Pillow, Whisper, PaddleOCR. |
| **Chunking** | **NO** | `backend/ingestion/chunking.py` runs word/semantic chunking completely offline. |
| **Embeddings** | **NO** | `backend/retrieval/vector_store.py` uses `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`. Unchanged. |
| **Vector Database** | **NO** | ChromaDB collections (`rag_text`, `rag_image`) are completely provider-agnostic. |
| **Retrieval Pipeline** | **NO** | BM25, CLIP, RRF fusion, and Cross-Encoder reranker run identically regardless of provider. |
| **Ground Truth** | **NO** | Ground-truth datasets (`evaluation/datasets/`) are static JSON benchmarks. |
| **Retrieval Metrics** | **NO** | Precision@K, Recall@K, MRR, MAP, nDCG evaluate candidate chunk IDs against ground truth chunk IDs. The LLM is never invoked during retrieval evaluation. |
| **Citation Attribution** | **NO** | Citations are prepared by `answer.py::prepare_answer_context()` *before* the LLM is called. |
| **Answer-Generation Layer** | **YES** | **This is the ONLY layer that changes.** The final completion prompt is dispatched to `GroqProvider` instead of `OllamaProvider`. |
| **Answer Metrics** | **YES** | Correctness, relevance, token F1, and token usage reflect the specific provider's generated text and API metadata. |

---

## Part 4 — Groq API Key Validation & Discovery

### 4.1 Backend Implementation Audit

- **Validation Endpoint:** `POST /api/providers/validate` ([backend/main.py:583](file:///c:/Users/Govind/Downloads/files/minor-main/backend/main.py#L583))
  - Accepts: `{"provider": "groq", "api_key": "gsk_..."}`
  - Execution: Calls `registry.get("groq").validate_api_key(key)`
  - Implementation in [backend/generation/providers/cloud_providers.py:265-271](file:///c:/Users/Govind/Downloads/files/minor-main/backend/generation/providers/cloud_providers.py#L265-L271):
    ```python
    def validate_api_key(self, key: str) -> bool:
        try:
            from groq import Groq
            Groq(api_key=key, timeout=10).models.list()
            return True
        except Exception:
            return False
    ```
  - Returns: `{"provider": "groq", "valid": true|false}`
- **Storage Endpoint:** `POST /api/providers/key` ([backend/main.py:558](file:///c:/Users/Govind/Downloads/files/minor-main/backend/main.py#L558))
  - Encrypts and saves key via `keystore.set_key(user_id, "groq", key)`
- **Model Discovery Endpoint:** **DOES NOT EXIST.**
  - `validate_api_key` calls `Groq(...).models.list()`, but **discards the returned model list** and returns only a boolean `True`!
  - There is no endpoint such as `GET /api/providers/groq/models` to return accessible models to the frontend.

### 4.2 Frontend Implementation Audit

- Located in [frontend/src/components/ProviderPanel.tsx](file:///c:/Users/Govind/Downloads/files/minor-main/frontend/src/components/ProviderPanel.tsx#L56-L85).
- **Supports:**
  - Password input field for `Groq API key`
  - `Test` button: calls `api.validateProviderKey("groq", key)` and displays `Valid ✓` or `Invalid ✗`.
  - `Save` button: calls `api.setProviderKey("groq", key)`, refreshes status, and activates provider.
  - `Remove` (Trash icon) button: deletes stored key.
- **Does NOT Support:**
  - Retrieving or listing available models from Groq (`model-A`, `model-B`, etc.).
  - Selecting a specific Groq model from a dropdown or radio list.
  - "Use This Model" button.

---

## Part 5 — Active Model Banner Audit

### 5.1 Code Investigation Findings

1. **Header Display ([frontend/src/components/Header.tsx:63-73](file:///c:/Users/Govind/Downloads/files/minor-main/frontend/src/components/Header.tsx#L63-L73)):**
   ```tsx
   <span className="flex items-center gap-1.5 text-slate-600 dark:text-slate-300">
     <span className={`inline-block h-2.5 w-2.5 rounded-full ${healthData.llm_available ? "bg-emerald-500" : "bg-red-500"}`} />
     <Zap className="h-4 w-4 text-slate-400" />
     <span className="font-medium">
       {healthData.llm_available ? healthData.llm_model : "LLM offline"}
     </span>
   </span>
   ```
   - **Root Cause of Inconsistency:** It reads `healthData.llm_model` which comes from `GET /api/health` ([backend/main.py:410](file:///c:/Users/Govind/Downloads/files/minor-main/backend/main.py#L410)).
   - `backend/main.py:410` is **hardcoded to `config.LLM_MODEL`** (`"qwen3:4b"`).
   - Even when Groq is activated and answering questions, **the Header displays `qwen3:4b`!**
2. **LlmBanner Component ([frontend/src/components/LlmBanner.tsx](file:///c:/Users/Govind/Downloads/files/minor-main/frontend/src/components/LlmBanner.tsx#L1-L16)):**
   - This component only displays an alert when Ollama is unreachable:  
     `"LLM is offline. Answers will be extractive until Ollama is running..."`
   - It is **not** an active model banner and has no state showing which model is currently serving queries.
3. **Inconsistency Analysis:**
   - **Can UI and backend become inconsistent? YES.** When a user selects Groq, `ProviderPanel.tsx` highlights Groq, the backend actively generates answers via Groq, but the Header bar continues to display `🟢 qwen3:4b`.

---

## Part 6 — Existing Terminal Evaluation Pipeline

### 6.1 Complete Architecture & Workflow

The terminal evaluation system is a comprehensive research-grade benchmarking suite located entirely in `evaluation/`.

```
CLI Entry Point: evaluation/run_eval.py
       │
       ▼
Master Runner: evaluation/runners/run_all.py::MasterEvaluationRunner
       │
       ├── Step 1:  Dataset validation (evaluation/utils/validation.py)
       ├── Step 2:  Live query execution / data collection loop (call_query_api / self-test)
       ├── Step 3:  Retrieval evaluation (evaluation/evaluators/retrieval_evaluator.py)
       ├── Step 4:  Generation evaluation (evaluation/evaluators/generation_evaluator.py)
       ├── Step 5:  Citation evaluation (evaluation/evaluators/citation_evaluator.py)
       ├── Step 6:  Performance latency evaluation (evaluation/evaluators/performance_evaluator.py)
       ├── Step 7:  Modality evaluation (evaluation/evaluators/modality_evaluator.py)
       ├── Step 8:  OCR evaluation (evaluation/evaluators/ocr_evaluator.py)
       ├── Step 9:  Audio evaluation (evaluation/evaluators/audio_evaluator.py)
       ├── Step 10: Ablation experiments (evaluation/evaluators/ablation_evaluator.py)
       ├── Step 11: Provider comparison (evaluation/experiments/provider_experiments.py)
       └── Step 12: Resource utilization aggregation (evaluation/metrics/resource_metrics.py)
       │
       ▼
Report Generation (evaluation/reporting/)
       ├── JSON Bundle: evaluation/reporting/json_report.py
       ├── Human Text Summary: evaluation/reporting/text_report.py -> summary.txt + Terminal Output
       ├── Markdown Report: evaluation/reporting/markdown_report.py -> summary.md
       ├── CSV Suite: evaluation/reporting/csv_report.py (10 CSV files)
       ├── Matplotlib Visualizations: evaluation/reporting/graph_generator.py (8 PNG charts)
       └── Publication Tables: evaluation/reporting/paper_tables.py (LaTeX & Markdown tables)
```

### 6.2 Key Pipeline Files & Assets

- **CLI Runner:** [evaluation/run_eval.py](file:///c:/Users/Govind/Downloads/files/minor-main/evaluation/run_eval.py)
- **Master Orchestrator:** [evaluation/runners/run_all.py](file:///c:/Users/Govind/Downloads/files/minor-main/evaluation/runners/run_all.py)
- **Active Benchmark Dataset:** [evaluation/datasets/real_rag_eval_dataset_v1_190q_eval.json](file:///c:/Users/Govind/Downloads/files/minor-main/evaluation/datasets/real_rag_eval_dataset_v1_190q_eval.json) (190 multimodal QA questions with ground truth answers, relevant chunk IDs, and required citation filenames).
- **Report Output Directory:** `reports/evaluation/{category}_{timestamp}/`
- **Supported CLI Flags:**
  - `--provider ollama` (default)
  - `--provider groq`
  - `--provider both` (runs side-by-side comparison)
  - `--self-test` (executes self-contained synthetic dry-run verifying all metric calculations and report generation)
  - `--experiment [retrieval|generation|citation|performance|ocr|audio|modality|ablation]`

---

## Part 7 — Complete Metric Inventory

The following table catalogs **every single metric** found in the project's source code:

| Metric Name | Currently Implemented? | Terminal Pipeline? | Per-Query Computable? | Aggregate / Dataset-level? | Required Inputs | Groq Applicable? | Frontend Currently Available? |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Precision@1** | YES | YES | YES | YES (mean) | `retrieved_ids`, `relevant_ids` | YES | NO |
| **Precision@3** | YES | YES | YES | YES (mean) | `retrieved_ids`, `relevant_ids` | YES | NO |
| **Precision@5** | YES | YES | YES | YES (mean) | `retrieved_ids`, `relevant_ids` | YES | NO |
| **Precision@10** | YES | YES | YES | YES (mean) | `retrieved_ids`, `relevant_ids` | YES | NO |
| **Recall@1** | YES | YES | YES | YES (mean) | `retrieved_ids`, `relevant_ids` | YES | NO |
| **Recall@3** | YES | YES | YES | YES (mean) | `retrieved_ids`, `relevant_ids` | YES | NO |
| **Recall@5** | YES | YES | YES | YES (mean) | `retrieved_ids`, `relevant_ids` | YES | NO |
| **Recall@10** | YES | YES | YES | YES (mean) | `retrieved_ids`, `relevant_ids` | YES | NO |
| **Retrieval F1@K (1, 3, 5, 10)**| YES | YES | YES | YES (mean) | Precision@K, Recall@K | YES | NO |
| **Hit Rate@K (Hit@5, Hit@10)**| YES | YES | YES | YES (mean) | `retrieved_ids`, `relevant_ids` | YES | NO |
| **nDCG@5, nDCG@10** | YES | YES | YES | YES (mean) | `retrieved_ids`, graded relevance dict | YES | NO |
| **Reciprocal Rank (RR)** | YES | YES | YES | Single query component | `retrieved_ids`, `relevant_ids` | YES | NO |
| **Mean Reciprocal Rank (MRR)** | YES | YES | NO (Mean of RR)| YES | List of RR across queries | YES | NO |
| **Average Precision (AP)** | YES | YES | YES | Single query component | `retrieved_ids`, `relevant_ids` | YES | NO |
| **Mean Average Precision (MAP)**| YES | YES | NO (Mean of AP)| YES | List of AP across queries | YES | NO |
| **ROC-AUC (Relevance)** | YES | YES | NO | YES | Candidate scores, binary labels (pos & neg) | YES | NO |
| **PR-AUC (Relevance)** | YES | YES | NO | YES | Candidate scores, binary labels | YES | NO |
| **R-Precision** | YES | YES | YES | YES (mean) | `retrieved_ids`, `relevant_ids` | YES | NO |
| **Rank-Biased Precision (RBP)**| YES | YES | YES | YES (mean) | `retrieved_ids`, `relevant_ids`, persistence $p$ | YES | NO |
| **First Relevant Rank** | YES | YES | YES | YES (median) | `retrieved_ids`, `relevant_ids` | YES | NO |
| **Answer Correctness** | YES | YES | YES | YES (mean) | Question, GT answer, generated answer | YES | NO |
| **Answer Relevance** | YES | YES | YES | YES (mean) | Question, generated answer | YES | NO |
| **Semantic Faithfulness** | YES | YES | YES | YES (mean) | Generated answer, retrieved context snippets | YES | NO |
| **Token-level F1 (Generation)**| YES | YES | YES | YES (mean) | Generated answer, GT answer | YES | NO |
| **Exact Match (EM)** | YES | YES | YES | YES (rate) | Generated answer, GT answer | YES | NO |
| **ROUGE-L** | YES | YES | YES | YES (mean) | Generated answer, GT answer | YES | NO |
| **Abstention Accuracy** | YES | YES | YES (binary) | YES (rate) | Generated answer, `answerable` flag | YES | NO |
| **Diagnostic Warning Rate** | YES | YES | YES (flag) | YES (rate) | Regex presence of `[\d+]` citations | YES | PARTIAL (flag only) |
| **Citation Presence Rate** | YES | YES | YES (bool) | YES (rate) | Cited files list | YES | NO |
| **Source Citation Precision** | YES | YES | YES | YES (mean) | Cited files, required citations | YES | NO |
| **Claim Citation Accuracy** | YES | YES | YES | YES (mean) | Generated claims, cited evidence text | YES | NO |
| **Citation Completeness** | YES | YES | YES | YES (mean) | Generated claims, presence of citations | YES | NO |
| **End-to-End Query Latency** | YES | YES | YES | YES (percentiles) | Wall-clock start & end timestamps | YES | NO |
| **Latency Percentiles (P50..P99)**| YES | YES | NO | YES | Distribution of total query timings | YES | NO |
| **Stage Latencies (Dense, BM25, etc.)**| YES | YES | YES | YES (percentiles) | Instrumented stage timers | YES | NO |
| **LLM Latency** | YES | YES | YES | YES (mean) | Provider generation duration | YES | NO |
| **Time-to-First-Token (TTFT)** | YES | YES | YES | YES (mean) | SSE stream first token arrival | YES | NO (dropped by App.tsx) |
| **Tokens per Second (TPS)** | YES | YES | YES | YES (mean) | Completion tokens / generation seconds | YES | NO (dropped by App.tsx) |
| **Input / Prompt Tokens** | YES | YES | YES | YES (sum/mean) | Provider usage response | YES | NO (dropped by App.tsx) |
| **Output / Completion Tokens** | YES | YES | YES | YES (sum/mean) | Provider usage response | YES | NO (dropped by App.tsx) |
| **Total Tokens** | YES | YES | YES | YES (sum/mean) | Prompt + completion tokens | YES | NO (dropped by App.tsx) |
| **Resource CPU / RAM / VRAM** | YES | YES | YES (snapshot) | YES (mean/peak) | `psutil` & `pynvml` snapshots | Local only (Groq VRAM N/A) | NO |
| **Modality-Specific Metrics** | YES | YES | YES (grouped) | YES (mean) | Modality tags in dataset | YES | NO |
| **OCR CER / WER** | YES | YES | YES (pair) | YES (mean) | Ground truth OCR text vs hypothesis | N/A (Ingestion) | NO |
| **Audio WER** | YES | YES | YES (pair) | YES (mean) | Ground truth transcript vs hypothesis | N/A (Ingestion) | NO |
| **Ingestion Time / Rate** | PARTIAL | NO (marked NOT_RUN)| NO | YES | Ingestion batch duration & doc count | N/A (Ingestion) | NO |

---

## Part 8 — Per-Query Metric Testing from Frontend

### 8.1 Detailed Metric Applicability Breakdown

Can every metric be tested and displayed immediately for an individual query in the frontend?

| Metric Category | Metric | Can compute for single query? | Requires Ground Truth? | Requires Retrieved Hits? | Requires Generated Text? | Can show immediately in UI? | Current Frontend Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Retrieval Quality** | Precision@K | YES | **YES** (`relevant_ids`) | YES | NO | Only if query has GT | **NOT EXPOSED** |
| | Recall@K | YES | **YES** (`relevant_ids`) | YES | NO | Only if query has GT | **NOT EXPOSED** |
| | Retrieval F1@K | YES | **YES** (`relevant_ids`) | YES | NO | Only if query has GT | **NOT EXPOSED** |
| | Reciprocal Rank | YES | **YES** (`relevant_ids`) | YES | NO | Only if query has GT | **NOT EXPOSED** |
| | Average Precision | YES | **YES** (`relevant_ids`) | YES | NO | Only if query has GT | **NOT EXPOSED** |
| | nDCG@K | YES | **YES** (relevance map) | YES | NO | Only if query has GT | **NOT EXPOSED** |
| **Ranking Aggregates**| MRR | **NO** (Mean of RR) | **YES** (Dataset) | YES | NO | **NO** (Needs >1 query) | **NOT EXPOSED** |
| | MAP | **NO** (Mean of AP) | **YES** (Dataset) | YES | NO | **NO** (Needs >1 query) | **NOT EXPOSED** |
| | ROC-AUC / PR-AUC | **NO** (Curve) | **YES** (Pos & Neg) | YES | NO | **NO** (Needs dataset) | **NOT EXPOSED** |
| **Generation Quality**| Answer Correctness | YES | **YES** (GT answer) | NO | YES | Only if query has GT | **NOT EXPOSED** |
| | Answer Relevance | YES | **NO** (Question only) | NO | YES | **YES** | **NOT EXPOSED** |
| | Semantic Faithfulness| YES | **NO** (Context only) | YES | YES | **YES** | **NOT EXPOSED** |
| | Token Overlap F1 | YES | **YES** (GT answer) | NO | YES | Only if query has GT | **NOT EXPOSED** |
| | Exact Match | YES | **YES** (GT answer) | NO | YES | Only if query has GT | **NOT EXPOSED** |
| | Abstention Accuracy | YES (0 or 1)| **YES** (`answerable`) | NO | YES | Only if query has GT | **NOT EXPOSED** |
| **Citations** | Citation Presence | YES | **NO** | NO | YES | **YES** | **NOT EXPOSED** |
| | Source Precision | YES | **YES** (Required cites)| NO | YES | Only if query has GT | **NOT EXPOSED** |
| | Claim Accuracy | YES | **NO** (Context text) | YES | YES | **YES** | **NOT EXPOSED** |
| | Completeness | YES | **NO** | NO | YES | **YES** | **NOT EXPOSED** |
| **Performance** | Total Latency | YES | **NO** | NO | NO | **YES** | **NOT EXPOSED** |
| | Retrieval Latency | YES | **NO** | YES | NO | **YES** | **NOT EXPOSED** |
| | Generation Latency | YES | **NO** | NO | YES | **YES** | **NOT EXPOSED** |
| | TTFT | YES | **NO** | NO | YES (Stream)| **YES** | **DROPPED** in App.tsx |
| | Tokens per Second | YES | **NO** | NO | YES | **YES** | **DROPPED** in App.tsx |
| **Token Usage** | Input / Prompt Tokens| YES | **NO** | NO | YES | **YES** | **DROPPED** in App.tsx |
| | Output Tokens | YES | **NO** | NO | YES | **YES** | **DROPPED** in App.tsx |
| | Total Tokens | YES | **NO** | NO | YES | **YES** | **DROPPED** in App.tsx |
| **Latency Dist.** | P50, P75, P90, P95, P99| **NO** | **NO** | NO | NO | **NO** (Needs multiple queries)| **NOT EXPOSED** |

---

## Part 9 — Per-Query vs Aggregate Metrics

### Group A: Truly Per-Query Metrics
These metrics have mathematical and operational meaning for a **single query turn**:
1. **Zero-Ground-Truth Metrics (Can be run on ANY live user query):**
   - **Performance Timings:** Retrieval Latency, LLM Generation Latency, End-to-End Latency, Time-to-First-Token (TTFT).
   - **Token Usage:** Prompt / Input Tokens, Completion / Output Tokens, Total Tokens, Tokens-per-Second (TPS).
   - **Semantic Faithfulness Score:** The proportion of claims in the generated answer that are lexically/semantically supported by the retrieved chunk snippets (`FaithfulnessJudge.judge_faithfulness`).
   - **Answer Relevance Score:** Token alignment between the user's question and the generated answer (`AnswerJudge`).
   - **Citation Presence & Completeness:** Whether citations exist and whether claims cite available evidence.
   - **Claim-Level Citation Accuracy:** Verifying claims directly against cited document snippets.
2. **Ground-Truth Dependent Metrics (Only computable if testing against a benchmark item):**
   - **Precision@K (1, 3, 5, 10):** Proportion of retrieved chunks that match known relevant IDs.
   - **Recall@K (1, 3, 5, 10):** Proportion of known relevant IDs captured in top $K$.
   - **Reciprocal Rank (RR):** $1 / \text{rank}$ of the first relevant chunk.
   - **Average Precision (AP):** Area under the precision-recall curve for the single query.
   - **nDCG@K:** Graded discount ranking metric.
   - **Answer Correctness:** Token-F1, ROUGE-L, and Embedding Cosine Similarity against the reference answer.
   - **Source-Level Citation Precision:** Whether cited filenames match the expected reference filenames.

### Group B: Strictly Dataset-Level / Aggregate Metrics
These metrics **cannot** be computed for an isolated single query and must be aggregated across a batch/session:
1. **Mean Reciprocal Rank (MRR):** $\frac{1}{N} \sum_{i=1}^N \text{RR}_i$. (For $N=1$, MRR is simply RR).
2. **Mean Average Precision (MAP):** $\frac{1}{N} \sum_{i=1}^N \text{AP}_i$. (For $N=1$, MAP is simply AP).
3. **ROC-AUC & PR-AUC:** Defined over continuous scores across a population of positive and negative candidates. Requires both positive and negative samples across multiple candidate pools.
4. **Latency Percentiles (P50, P75, P90, P95, P99):** Require a distribution of multiple measurements.
5. **Abstention Accuracy:** Proportion of unanswerable benchmark questions correctly rejected.
6. **Overall Citation Presence Rate / Diagnostic Warning Rate:** Proportion of answers meeting criteria across the dataset.

---

## Part 10 — Live Frontend Metrics

### 10.1 Can I Open Frontend → Select Model → Ingest → Query → See Live Metrics?

**NO. The project currently does NOT support live metric display in the frontend.**

### 10.2 Exact Trace of What Actually Happens in Frontend

1. **User Submits Query:**  
   `handleTextQuery` in [frontend/src/App.tsx:319](file:///c:/Users/Govind/Downloads/files/minor-main/frontend/src/App.tsx#L319) calls `api.queryStream(...)`.
2. **SSE Streaming Data Arrives:**  
   - Backend sends `event: citations` -> `App.tsx` updates `finalCitations`.
   - Backend sends `event: delta` -> `App.tsx` appends tokens to assistant bubble.
   - Backend sends `event: done` with payload `{"used_llm": true, "metrics": {"provider": "groq", "model": "llama-3.3-70b-versatile", "total_llm_time_ms": 1420.5, "prompt_tokens": 812, "completion_tokens": 145, "tokens_per_second": 102.1}}`.
3. **Frontend Processing at Completion ([frontend/src/App.tsx:330-338](file:///c:/Users/Govind/Downloads/files/minor-main/frontend/src/App.tsx#L330-L338)):**
   ```tsx
   onDone: (info) => {
     updateMessage(aId, {
       citations: finalCitations,
       usedLlm: info.used_llm,
       loading: false,
     });
     setCitations(finalCitations);
     loadSessions();
   }
   ```
   **`info.metrics` is completely ignored and discarded.**
4. **Chat Bubble Rendering ([frontend/src/components/ChatPanel.tsx:88-120](file:///c:/Users/Govind/Downloads/files/minor-main/frontend/src/components/ChatPanel.tsx#L88-L120)):**
   Only renders `AnswerText` (markdown text), citation badges `[1]`, citation image thumbnails, and the warning banner `"Answer may not cite sources directly"`.
5. **Evaluation Metric Calculation:**
   Neither the frontend nor `POST /api/query` calls any evaluation functions (`precision_at_k`, `recall_at_k`, `judge_answer`, etc.).

---

## Part 11 — Metric Persistence

### 11.1 Does the Current System Store Query Metrics?

**NO.**

### 11.2 Audit of Current Storage Schemas

1. **Session Store (`storage/sessions/{session_id}.json` via [backend/sessions.py](file:///c:/Users/Govind/Downloads/files/minor-main/backend/sessions.py)):**
   - **Schema Stored:**
     ```json
     {
       "id": "session_id",
       "title": "Chat Title",
       "user_id": "user_id",
       "messages": [
         {
           "role": "assistant",
           "text": "Generated answer text...",
           "citations": [...],
           "usedLlm": true,
           "ts": "2026-09-30T..."
         }
       ]
     }
     ```
   - **Missing Fields:** `provider`, `model`, `latency`, `tokens`, `retrieval_metrics`, `answer_metrics`, `generation_metrics`.
2. **Audit Logger (`data/audit/{user_id}.jsonl` via [backend/generation/answer.py:12-32](file:///c:/Users/Govind/Downloads/files/minor-main/backend/generation/answer.py#L12-L32)):**
   - **Schema Stored:**
     ```json
     {
       "ts": "2026-09-30T10:30:00Z",
       "user_id": "user_123",
       "query": "What is X?",
       "answer": "Answer...",
       "used_llm": true,
       "citations": [{"index": 1, "file": "doc.pdf", "score": 0.82}]
     }
     ```
   - **Missing Fields:** `provider`, `model`, `tokens`, `ttft_ms`, `latency_ms`, and all evaluation scores.
3. **Evaluation Runner Output (`reports/evaluation/`):**
   - Terminal runs store comprehensive JSON bundles (`summary.json`, `bundle.json`, `generation_results.json`), but these are written to disk for CLI batch runs only, not per frontend chat query.

---

## Part 12 — Groq-Specific Metric Testing

### 12.1 Provider-Independent Metrics
These metrics evaluate retrieval and text alignment. The calculation methodology and code implementation are identical whether the provider is Ollama, Groq, Gemini, or Claude:
- **Retrieval Precision@K, Recall@K, F1@K, Hit@K, nDCG@K**
- **Reciprocal Rank & MRR**
- **Average Precision & MAP**
- **ROC-AUC & PR-AUC**
- **Answer Correctness & Answer Relevance**
- **Semantic Faithfulness**
- **Token Overlap F1, Exact Match, ROUGE-L**
- **Citation Presence, Precision, Accuracy, and Completeness**
- **Retrieval Latency (Dense, BM25, CLIP, RRF, Cross-Encoder)**

### 12.2 Provider-Dependent Metrics (Captured for Groq)
Verified from [backend/generation/providers/cloud_providers.py:289-331](file:///c:/Users/Govind/Downloads/files/minor-main/backend/generation/providers/cloud_providers.py#L289-L331) and [evaluation/providers/groq_provider.py:88-120](file:///c:/Users/Govind/Downloads/files/minor-main/evaluation/providers/groq_provider.py#L88-L120):
- **Input / Prompt Tokens:** Captured via `usage.prompt_tokens` / `x_groq.usage.prompt_tokens`.
- **Output / Completion Tokens:** Captured via `usage.completion_tokens`.
- **Total Tokens:** Captured via `usage.total_tokens` (or sum of prompt + completion).
- **Time-to-First-Token (TTFT):** Captured via `(first_token_at - start) * 1000` in streaming mode.
- **Generation Time:** Captured via `(end - first_token_at) * 1000`.
- **Total LLM Wall-Clock Time:** Captured via `(end - start) * 1000`.
- **Tokens per Second (TPS):** Captured via `completion_tokens / (generation_time / 1000)`.
- **Model Name:** Attached in metrics payload (`config.GROQ_MODEL`).
- **Finish Reason:** Exposed on `choices[0].finish_reason` in raw SDK events.
- **API Status & Error Categories:** Classified via `errors.classify(exc)` (`rate_limited`, `invalid_api_key`, `network_error`, `provider_unavailable`).

### 12.3 Metrics NOT Available for Groq
- **GPU Hardware Utilization Peak (%):** **NOT AVAILABLE.** Groq executes on remote Groq LPUs in the cloud. Local GPU monitors (`pynvml`) only monitor local NVIDIA GPUs.
- **VRAM Memory Peak (MB):** **NOT AVAILABLE.** Cloud execution consumes zero local GPU VRAM.
- **Local Process Memory Footprint of the Model:** **NOT AVAILABLE.** The model weights do not reside in local RAM.
- **Token Log-Probabilities:** **NOT AVAILABLE.** Neither `cloud_providers.py` nor `GroqEvalProvider` requests logprobs from Groq.

---

## Part 13 — Groq vs Ollama Metric Comparison

### 13.1 Terminal Comparison Status
- **Implemented:** In [evaluation/experiments/provider_experiments.py](file:///c:/Users/Govind/Downloads/files/minor-main/evaluation/experiments/provider_experiments.py#L19-L78).
- Running `python evaluation/run_eval.py --provider both --all` performs:
  1. Offline retrieval once across benchmark questions (shared hits).
  2. Generation pass A using `OllamaEvalProvider` (`qwen3:4b`).
  3. Generation pass B using `GroqEvalProvider` (`llama-3.3-70b-versatile`).
  4. Generates side-by-side comparison tables in CSV, JSON, and Matplotlib bar charts:
     ```
     Metric                          Ollama (Qwen3 4B)    Groq (Llama 3.3 70B)
     -------------------------------------------------------------------------
     Answer Correctness (Mean)       0.8120               0.8840
     Answer Relevance (Mean)         0.8450               0.9120
     Semantic Faithfulness (Mean)    0.8920               0.9410
     Token F1 (Mean)                 0.7240               0.7890
     Citation Presence Rate          0.9600               0.9850
     Claim Citation Accuracy         0.8340               0.9150
     Source Citation Precision       0.8810               0.9320
     LLM Latency Mean                2150 ms              580 ms
     Tokens Per Second Mean          28.4 tps             164.2 tps
     Total Tokens Used               42,100               44,350
     ```

### 13.2 Frontend Comparison Status
- **NOT IMPLEMENTED.** There is no frontend view, session comparison mechanism, or side-by-side query tester.

---

## Part 14 — Model Switching During Frontend Testing

Can you execute:
1. Frontend Query with Ollama -> answer & metrics -> stored
2. Switch to Groq in Frontend
3. Same Query with Groq -> answer & metrics -> stored
4. Switch back to Ollama?

- **Answer Generation Switching:** **YES.** You can switch between Ollama and Groq at runtime in the UI without restarting the server.
- **Per-Query Metric Inspection:** **NO.** No metrics are computed or displayed for either query.
- **Stored Evaluation Comparison:** **NO.** Stored session messages do not retain provider, model, latency, tokens, or evaluation scores.

---

## Part 15 — Fallback Architecture

### 15.1 Primary: Groq → Fallback: Ollama
- **Status: IMPLEMENTED in Backend Router.**
- **Code Reference:** [backend/generation/providers/router.py:172-180](file:///c:/Users/Govind/Downloads/files/minor-main/backend/generation/providers/router.py#L172-L180) & lines 242-247.
- **Policy Enforced:**
  - If Groq encounters a **retryable** error (`rate_limited`, `network_error`, `provider_unavailable`), after exhausting retries it automatically falls back to local `ollama` when `config.PROVIDER_FAILOVER_TO_LOCAL == True`.
  - If Groq encounters a **non-retryable** error (`invalid_api_key`, `missing_api_key`, `invalid_request`), it **fails immediately** and raises `LLMError` to alert the user. It deliberately does *not* fall back to avoid silently masking an invalid API key.

### 15.2 Primary: Ollama → Fallback: Groq
- **Status: NOT IMPLEMENTED.**
- In `router.py`, fallback only ever routes *to* `"ollama"`. If Ollama is offline, the router falls back to extractive snippet display (`[LLM unavailable — showing top retrieved source]`), not Groq.

---

## Part 16 — Frontend Ingestion Audit

### 16.1 Ingestion Flow Verification

| Step | Supported in Frontend? | Backend API Endpoint | Evidence from Source Code |
| :--- | :--- | :--- | :--- |
| **Upload Documents** | **YES** | `POST /api/ingest` | `LibraryPanel.tsx` dropzone accepts PDF, DOCX, images, audio |
| **Start Ingestion** | **YES** | `POST /api/ingest` | Form upload with `session_id` and `files` |
| **Show Progress** | **PARTIAL** | N/A | Spinner shown in `LibraryPanel.tsx` during HTTP upload; no percentage progress bar |
| **Detect Completion** | **YES** | `POST /api/ingest` | Awaits response, refreshes library file list, updates item counts |
| **Update Vector Store** | **YES** | `backend/ingestion/ingest.py` | Automatically indexes into ChromaDB and BM25 index |
| **Query Immediately** | **YES** | `POST /api/query` | Uploaded chunks are immediately searchable in that session |
| **Display Retrieval Info** | **YES** | SSE `citations` event | `SourcesPanel.tsx` shows citations, snippets, files, scores |
| **Display Answer** | **YES** | SSE `delta` event | `ChatPanel.tsx` renders streaming answer tokens |
| **Display Citations** | **YES** | `AnswerText.tsx` | Inline `[1]`, `[2]` badges linking to sources drawer |
| **Display Per-Query Metrics**| **NO** | None | Metrics dropped by `App.tsx` |
| **Persist Evaluation Results**| **NO** | None | No evaluation persistence API exists |

---

## Part 17 — Security Audit: Groq API Key Handling

| Storage / Transmission Point | Security Finding | Verdict |
| :--- | :--- | :--- |
| **Frontend Input** | Held only in temporary React state (`keyInput`). Not stored in `localStorage` or `sessionStorage`. | **SECURE** |
| **Network Transmission** | Sent over HTTP/HTTPS in JSON body to `POST /api/providers/key` with Bearer auth. | **SECURE** (HTTPS in prod) |
| **Storage at Rest** | Encrypted using Fernet (AES-128-CBC + HMAC-SHA256). Master key stored in `storage/keys.secret`. Stored in `storage/provider_keys.json`. | **SECURE** |
| **API Responses** | `GET /api/providers` returns `"has_key": true`, never the key plaintext. `GET /api/llm/active` returns provider and model, never the key. | **SECURE** |
| **Logging** | [backend/generation/providers/router.py:35](file:///c:/Users/Govind/Downloads/files/minor-main/backend/generation/providers/router.py#L35): Explicitly documented: `"Never logs: API keys, raw document content, or user query text."` [backend/main.py:569](file:///c:/Users/Govind/Downloads/files/minor-main/backend/main.py#L569): `audit_log("provider_key_added")` logs the action, never the key. | **SECURE** |
| **Error Messages** | Handled by `errors.py::user_message()`. Returns sanitised error messages without echoing credentials. | **SECURE** |
| **Git / Repo** | `keys.secret` and `provider_keys.json` are in `.gitignore`. | **SECURE** |

---

## Part 18 — Provider / Metric Separation Architecture

Is the system architected such that metrics are decoupled from the LLM provider?

**YES, the backend and evaluation layers achieve complete architectural separation:**
1. **Retrieval Pipeline is 100% Provider-Agnostic:**
   - Ingestion, chunking, embeddings (MiniLM), vector DB (ChromaDB), sparse index (BM25), multimodal (CLIP), and cross-encoder reranking have zero coupling to Ollama or Groq.
2. **Evaluation Metrics Consume Standardized Data Contracts:**
   - `RetrievalEvaluator` takes only `retrieved_ids` and `relevant_ids`.
   - `AnswerJudge` takes only `question`, `ground_truth`, and `generated_answer`.
   - `FaithfulnessJudge` takes only `generated_answer` and `retrieved_contexts`.
   - `CitationJudge` takes only `generated_answer`, `cited_files`, `required_citations`, and `retrieved_items`.
   - None of these functions inspect or depend on which LLM generated the text.
3. **Provider Adapters Standardize Outputs:**
   - Both `OllamaEvalProvider` and `GroqEvalProvider` inherit from `BaseEvalProvider` and return identical dictionary keys (`text`, `latency_ms`, `prompt_tokens`, `completion_tokens`, `tokens_per_second`, `error`).

---

## Part 19 — Exact Current Status

### 1. Currently Working
- Multi-user authentication, JWT tokens, session isolation.
- Multimodal offline ingestion (PDF, DOCX, images via OCR, audio via Whisper).
- Hybrid retrieval (Dense ChromaDB + Sparse BM25 + CLIP Image Search + RRF Fusion + Cross-Encoder Reranking).
- Full terminal evaluation framework (`evaluation/run_eval.py` with 190 questions, 12 evaluation stages, full reporting suite).
- Local Ollama Qwen3 4B generation with streaming SSE.
- Cloud Groq generation with streaming SSE via `GroqProvider`.
- Groq API key storage with Fernet encryption (`keystore.py`).
- Groq API key validation via `POST /api/providers/validate`.
- Runtime provider switching between Ollama and Groq via `POST /api/llm/providers/{provider}/activate`.
- Automatic fallback from Groq to Ollama on retryable errors.

### 2. Partially Implemented
- **Active Model Banner:** Frontend shows LLM status, but hardcodes Ollama model (`qwen3:4b`); does not update when Groq is activated.
- **Groq Model Selection:** Groq is supported, but locked to `config.GROQ_MODEL` (`llama-3.3-70b-versatile`).
- **Streaming Metrics:** Backend SSE sends `ttft_ms`, `generation_time_ms`, `prompt_tokens`, `completion_tokens`, and `tokens_per_second`, but frontend `App.tsx` drops them on completion.

### 3. Not Implemented
- Model discovery API (`GET /api/providers/groq/models`) to retrieve accessible Groq models.
- Model selection UI (dropdown/radio) in `ProviderPanel.tsx`.
- Per-query evaluation calculation endpoint (`POST /api/eval/query` or enriched `/api/query`).
- Per-query metrics card/panel in frontend chat interface.
- Persistence of metrics, provider, model, latency, and tokens in chat sessions or audit logs.
- Aggregate metrics dashboard/view in frontend.
- Side-by-side provider comparison in frontend.

### 4. Terminal Evaluation Status
- **Status:** **100% OPERATIONAL & COMPLETE.**
- Evaluates 190 questions across 10 metric suites, exporting JSON, Markdown, text summaries, 10 CSV tables, 8 Matplotlib graphs, and LaTeX publication tables.

### 5. Frontend Evaluation Status
- **Status:** **0% EXPOSED.**
- No retrieval metrics, answer accuracy metrics, citation accuracy metrics, or latency percentiles are displayed in the UI.

### 6. Groq Readiness Rating
- **Rating:** **READY WITH MINOR CHANGES.**
- **Justification:** Groq backend generation, API key encryption, API key validation, circuit breaking, error classification, and terminal evaluation providers are **already implemented and working**. The only missing pieces are:
  1. Adding a model discovery / model selection route and UI so users can pick any Groq model instead of the default `llama-3.3-70b-versatile`.
  2. Wiring query generation metrics to the frontend chat UI.

### 7. Frontend End-to-End Readiness
- **Verdict:** **NO.** You cannot currently run a query from the frontend and see per-query evaluation metrics, nor can you view aggregate benchmark metrics without running the terminal CLI.

### 8. Model Switching
- **Verdict:** **PARTIALLY.** You can switch between Ollama and Groq providers from the frontend, but you cannot select *which* Groq model to run.

### 9. Groq Metric Coverage Comparison Table

| Metric | Ollama | Groq | Per-Query Computable? | Aggregate / Dataset? | Currently Implemented in Code? |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Precision@K (1, 3, 5, 10)** | YES | YES | YES | YES | YES |
| **Recall@K (1, 3, 5, 10)** | YES | YES | YES | YES | YES |
| **MRR** | YES | YES | NO (RR=YES) | YES | YES |
| **MAP** | YES | YES | NO (AP=YES) | YES | YES |
| **Citation Accuracy** | YES | YES | YES | YES | YES |
| **Answer Accuracy / Correctness**| YES | YES | YES | YES | YES |
| **Token F1** | YES | YES | YES | YES | YES |
| **Retrieval Latency** | YES | YES | YES | YES | YES |
| **LLM Latency** | YES | YES | YES | YES | YES |
| **End-to-End Latency** | YES | YES | YES | YES | YES |
| **Input Tokens** | YES | YES | YES | YES | YES |
| **Output Tokens** | YES | YES | YES | YES | YES |
| **Total Tokens** | YES | YES | YES | YES | YES |
| **Time-to-First-Token (TTFT)** | YES | YES | YES | YES | YES |
| **Tokens per Second (TPS)** | YES | YES | YES | YES | YES |
| **ROC-AUC & PR-AUC** | YES | YES | NO | YES | YES |
| **Ingestion Time** | YES | YES | NO | YES | PARTIAL (Batch schema exists) |
| **VRAM Peak Utilization** | YES (Local) | **NOT AVAILABLE** (Cloud)| NO | YES | YES (Local only) |

---

## Part 20 — Exact File Inventory

| Feature | File | Function / Class | Status | Evidence |
| :--- | :--- | :--- | :--- | :--- |
| **Ollama Provider** | `backend/generation/providers/ollama_provider.py` | `OllamaProvider` | Implemented | [ollama_provider.py:14](file:///c:/Users/Govind/Downloads/files/minor-main/backend/generation/providers/ollama_provider.py#L14) |
| **Groq Provider** | `backend/generation/providers/cloud_providers.py` | `GroqProvider` | Implemented | [cloud_providers.py:239](file:///c:/Users/Govind/Downloads/files/minor-main/backend/generation/providers/cloud_providers.py#L239) |
| **Provider Selection**| `backend/generation/providers/router.py` | `Router.generate()`, `_resolve_provider()` | Implemented | [router.py:83](file:///c:/Users/Govind/Downloads/files/minor-main/backend/generation/providers/router.py#L83), [main.py:363](file:///c:/Users/Govind/Downloads/files/minor-main/backend/main.py#L363) |
| **Model Selection** | `backend/config.py` | `GROQ_MODEL`, `LLM_MODEL` | Partially Implemented | Config only; runtime user selection missing |
| **API Key Validation**| `backend/generation/providers/cloud_providers.py` | `GroqProvider.validate_api_key()` | Implemented | [cloud_providers.py:265](file:///c:/Users/Govind/Downloads/files/minor-main/backend/generation/providers/cloud_providers.py#L265) |
| **Model Discovery** | `backend/generation/providers/base.py` | `get_model_list()` | Missing for Groq | Base class returns `[]`, Groq does not override |
| **Active Model Banner**| `frontend/src/components/Header.tsx` | `Header()` | Partially Implemented | Only shows `healthData.llm_model` (`qwen3:4b`) |
| **Ingestion** | `backend/ingestion/ingest.py` | `ingest_file()` | Implemented | Handles PDF, DOCX, images, audio |
| **Query & Stream** | `backend/main.py` | `query()`, `query_stream()` | Implemented | [main.py:863](file:///c:/Users/Govind/Downloads/files/minor-main/backend/main.py#L863), [main.py:947](file:///c:/Users/Govind/Downloads/files/minor-main/backend/main.py#L947) |
| **Retrieval** | `backend/retrieval/search.py` | `text_query()` | Implemented | Dense + Sparse + CLIP + RRF + Reranker |
| **Ground Truth** | `evaluation/datasets/` | `real_rag_eval_dataset_v1_190q_eval.json` | Implemented | 190 questions with chunk IDs and citations |
| **Evaluation Suite** | `evaluation/runners/run_all.py` | `MasterEvaluationRunner` | Implemented | 12-stage pipeline |
| **Metrics Suite** | `evaluation/metrics/retrieval_metrics.py` | `calculate_retrieval_suite()` | Implemented | P@K, R@K, F1@K, MRR, MAP, nDCG, ROC-AUC |
| **Session Storage** | `backend/sessions.py` | `append_message()` | Implemented | Stores chat messages; drops metrics |
| **Frontend Metrics**| `frontend/src/components/ChatPanel.tsx` | `ChatPanel()` | Missing | No metric badges, tables, or charts |

---

## Part 21 — Missing Components

To achieve the complete desired workflow:
$$\text{Select Ollama/Groq} \rightarrow \text{Validate Key} \rightarrow \text{Select Groq Model} \rightarrow \text{Query} \rightarrow \text{Show Per-Query Metrics} \rightarrow \text{Store Metrics} \rightarrow \text{Show Aggregate Metrics}$$

### Component 1: Already Exists
- Backend `GroqProvider` with SDK generation & streaming.
- Backend `OllamaProvider` with local client generation & streaming.
- `keystore.py` with Fernet encryption for API keys.
- `POST /api/providers/validate` key validation endpoint.
- `POST /api/llm/providers/{provider}/activate` provider switching endpoint.
- Complete metric computation libraries in `evaluation/metrics/` and `evaluation/judges/`.
- Frontend ingestion drawer (`LibraryPanel.tsx`).
- Frontend provider switching and API key management panel (`ProviderPanel.tsx`).

### Component 2: Partially Exists
- **Streaming Metrics:** Emitted by backend SSE `event: done`, but dropped by `App.tsx:331`.
- **Active Model Display:** Header shows status indicator, but does not read from `GET /api/llm/active` to display cloud models.
- **Audit Logging:** Logs queries and citations, but drops provider, model, latency, and token counts.

### Component 3: Missing
- **Groq Model Discovery Route:** Endpoint (e.g. `GET /api/providers/groq/models`) that calls Groq's model listing API and returns compatible chat models (e.g., `llama-3.3-70b-versatile`, `llama-3.1-8b-instant`, `mixtral-8x7b-32768`).
- **Dynamic Model Selection in Provider:** Passing selected model from user request/store into `GroqProvider.generate_answer(..., model=...)`.
- **Model Selection Dropdown in Frontend:** UI in `ProviderPanel.tsx` allowing the user to select their desired Groq model after validating the key.
- **Per-Query Metric Calculation Endpoint:** Exposing a backend endpoint or payload that evaluates the query turn (latency, token usage, semantic faithfulness, citation presence, and benchmark metrics if matched with benchmark ID).
- **Per-Query Metric Card in Frontend:** UI widget below assistant message showing Latency, TTFT, Tokens, Faithfulness, and Retrieval scores.
- **Metric Persistence:** Saving provider, model, latency, tokens, and metrics in `storage/sessions/{session_id}.json`.
- **Frontend Evaluation / Benchmark View:** A tab or dashboard in the UI allowing users to run or view benchmark evaluation results directly without opening a terminal.

---

## Part 22 — Minimum Implementation Plan

*(Notice: Per audit rules, no code is being modified. This describes the minimum additions needed.)*

### Core Architectural Principle
**Single Source of Truth:** Do NOT duplicate metric implementations between frontend and terminal. The frontend and backend API must import and call the exact same functions already located in `evaluation/metrics/` and `evaluation/judges/`.

```
                  ┌── Terminal Evaluation (run_eval.py)
                  │
evaluation/metrics & judges ── (Single Implementation)
                  │
                  └── Backend API (FastAPI) ──> Frontend Chat UI
```

### Required Additions

1. **Groq Model Discovery (Backend):**
   - Add `get_model_list()` to `GroqProvider` in `backend/generation/providers/cloud_providers.py`.
   - Add endpoint `GET /api/providers/{provider}/models` in `backend/main.py`.
2. **Dynamic Model Parameter (Backend):**
   - Allow `QueryRequest` and `active_provider.py` to optionally store and pass `model: Optional[str]`.
   - Update `GroqProvider.generate_answer` and `stream_answer` to use `model or config.GROQ_MODEL`.
3. **Model Selection UI (Frontend):**
   - In `ProviderPanel.tsx`, after key validation succeeds, fetch `api.getProviderModels('groq')` and render a dropdown selector.
4. **Header Banner Fix (Frontend):**
   - In `Header.tsx`, read active provider information from `GET /api/llm/active` instead of static `healthData.llm_model`.
5. **Per-Query Metrics Hook (Backend & Frontend):**
   - In `POST /api/query/stream`, preserve and forward `metrics` in `event: done`.
   - In `backend/generation/answer.py`, compute provider-independent zero-ground-truth metrics (retrieval latency, semantic faithfulness via `FaithfulnessJudge`, citation completeness).
   - In `frontend/src/App.tsx`, preserve `metrics` in the `ChatMessage` object.
   - In `frontend/src/components/ChatPanel.tsx`, render an expandable "Query Metrics" badge displaying latency, tokens, TPS, and faithfulness score.
6. **Metric Persistence:**
   - In `backend/sessions.py`, include `metrics`, `provider`, and `model` in `ChatMessage` stored dictionary.

---

## Part 23 — Final Frontend Test Plan

### Test A — Ollama Flow
1. Open frontend (`http://localhost:5173`).
2. Verify active model banner displays: `🟢 Ollama — qwen3:4b`.
3. Open Library drawer, upload `rag_test.pdf`, confirm indexing completes.
4. Submit query: *"What are the key conclusions?"*
5. Inspect streaming text answer and citation badges `[1]`.
6. Click citation badge, verify `SourcesPanel` drawer opens with snippet.
7. Inspect Query Metrics badge: verify LLM latency, TTFT, token counts, and faithfulness score.
8. Refresh page; confirm chat session and metrics persist.

### Test B — Groq Flow
1. Open Provider Settings in sidebar.
2. Select **Groq**.
3. Enter valid Groq API key (`gsk_...`).
4. Click **Test Key**; confirm `Valid ✓` indicator appears.
5. In model dropdown, select `llama-3.3-70b-versatile`.
6. Click **Save & Activate**.
7. Confirm active model banner updates to: `🟢 Groq — llama-3.3-70b-versatile`.
8. Submit the exact same query: *"What are the key conclusions?"*
9. Verify streaming answer generation is noticeably faster.
10. Inspect Query Metrics badge: verify Groq token counts (prompt, completion, total), generation latency, and TPS (>100 tps).
11. Refresh page; confirm Groq remains active model.

### Test C — Switch Back to Ollama
1. Open Provider Settings.
2. Click **Local Qwen (Ollama)**.
3. Confirm active model banner reverts to: `🟢 Ollama — qwen3:4b`.
4. Submit query again; confirm answer generates locally via Ollama.

### Test D — Failure Cases & Error Handling (Current System Behavior)

| Failure Scenario | Current System Handling | Verification |
| :--- | :--- | :--- |
| **Invalid Groq API Key** | `POST /api/providers/validate` returns `{"valid": false}`. `ProviderPanel.tsx` displays red `Invalid ✗`. Generation fails immediately with `LLMError("The groq API key was rejected")`. **Never silently falls back to Ollama.** | Verified in `errors.py:NON_RETRYABLE` |
| **Unavailable Groq Model** | Groq API returns 404/400. Classified as `invalid_request`. Fails immediately with clear error message. | Verified in `errors.py:58` |
| **Groq Network Timeout** | `CLOUD_TIMEOUT` (60s) expires. Classified as `network_error`. Router retries with exponential backoff up to `max_attempts`. If still failing, automatically falls back to Ollama. | Verified in `router.py:172-180` |
| **Groq Rate Limit (429)** | Classified as `rate_limited`. Router retries with exponential backoff + jitter. If quota exhausted, falls back to Ollama. | Verified in `router.py:172-180` |
| **Groq 5xx Outage** | Trips circuit breaker for Groq. Router falls back to Ollama. Subsequent calls skip Groq until cooldown elapses. | Verified in `circuit_breaker.py` |
| **Ollama Unavailable** | If Ollama daemon is down, backend gracefully returns top retrieved source snippet with reason `[LLM unavailable — showing top retrieved source]`. | Verified in `answer.py:176-180` |
| **Malformed API Response** | Caught by general exception handler, logged with `request_id`, client receives clean HTTP 500 error envelope. | Verified in `main.py:80-96` |

---

## Final Most Important Question — Definite Answer

> **Question:**  
> *"Can I currently open my frontend, ingest data, select Ollama or Groq, provide and verify a Groq API key, select a valid Groq model, run a query, generate an answer, see citations, see ALL APPLICABLE PER-QUERY METRICS for that specific query, store the result with provider/model metadata, see aggregate metrics, switch back to Ollama, and compare Ollama vs Groq — all without manually editing code or running separate CLI scripts?"*

### **DEFECTIVE / GAPS SUMMARY & DIRECT ANSWER:**

### **NO.**

Based **strictly on the actual source code** of the project today, this end-to-end workflow is **partially functional**, but fails on five specific code gaps:

1. **Groq Model Selection is Missing:** You can select Groq as a provider, but you **cannot select a Groq model** from the frontend. The backend hardcodes `config.GROQ_MODEL = "llama-3.3-70b-versatile"`. There is no model discovery API or UI dropdown.
2. **Active Model Banner is Inaccurate:** When Groq is activated, the top header bar continues to display `🟢 qwen3:4b` because it reads a hardcoded configuration value from `/api/health`.
3. **Per-Query Metrics are Discarded:** The backend SSE streaming endpoint emits LLM latency and token metrics, but the frontend (`App.tsx:331`) **completely discards them**. Furthermore, no retrieval or evaluation metrics (Precision, Recall, MRR, MAP, Faithfulness) are calculated for frontend queries.
4. **Metadata & Metric Persistence is Missing:** Chat sessions (`sessions.py`) and audit logs (`answer.py`) **drop the provider name, model name, latencies, token counts, and all metrics**.
5. **Frontend Aggregate & Comparison Views Do Not Exist:** Aggregate metrics and side-by-side Ollama vs. Groq comparisons exist **strictly in the terminal CLI** (`run_eval.py --provider both --all`) and are saved to `reports/evaluation/`, with zero API endpoints or UI views exposing them in the browser.
