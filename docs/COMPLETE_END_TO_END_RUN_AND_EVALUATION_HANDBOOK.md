# Complete End-to-End Run and Evaluation Handbook

This is the primary operating guide for the current repository. It describes the source-controlled application as it exists on 2026-10-01. Commands are classified as:

- **VERIFIED**: executed successfully in this workspace.
- **IMPLEMENTED, NOT VERIFIED**: supported by the source code, but not executed here.
- **BLOCKED**: requires a service, credential, document corpus, or user action unavailable here.

Repository root used below:

```text
C:\Users\Govind\Downloads\files\minor-main
```

The application is a local-first, single-process FastAPI + React application. It stores users and chat sessions as JSON files, vectors in ChromaDB, lexical retrieval data in SQLite FTS5, and uploaded files under the configured data directory.

## 1. Prerequisites and environment setup

### 1.1 Open the repository

**PowerShell, working directory: any directory. Status: VERIFIED path.**

```powershell
Set-Location C:\Users\Govind\Downloads\files\minor-main
Get-Location
```

Expected location ends in `minor-main`.

Git metadata is not present in the supplied workspace. The following is still safe to run and reports that condition rather than changing anything:

```powershell
git status --short --branch
```

### 1.2 Check installed tools

**PowerShell, repository root. Status: IMPLEMENTED, NOT VERIFIED as a handbook block.**

```powershell
python --version
python -m pip --version
node --version
npm --version
ollama --version
docker compose version
```

Python 3.10+ and Node.js 18+ are the documented minimums. Docker and Ollama are optional only if using the source stack with local services already installed; Ollama is required for a live local-generation test.

### 1.3 Activate the existing Python environment

The repository already contains `.venv`. Reuse it rather than creating a second environment.

**PowerShell, repository root. Status: IMPLEMENTED, NOT VERIFIED in this handbook session.**

```powershell
if (-not (Test-Path .\.venv\Scripts\Activate.ps1)) {
    python -m venv .venv
}
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
& .\.venv\Scripts\Activate.ps1
python --version
```

### 1.4 Install backend dependencies

`backend/requirements.txt` pins the web, vector, embedding, OCR, audio, document, provider, and utility dependencies. PyTorch is intentionally installed separately so the correct CPU/CUDA build can be selected.

**PowerShell, repository root. Status: IMPLEMENTED, NOT VERIFIED here because installation is environment-dependent.**

CPU-safe installation:

```powershell
python -m pip install --upgrade pip
python -m pip install torch torchvision
python -m pip install -r .\backend\requirements.txt
```

For the CUDA wheel documented by the repository, use the project-supported PyTorch index instead of the CPU command:

```powershell
python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
python -m pip install -r .\backend\requirements.txt
```

Do not run both variants in the same environment without checking the resulting installation.

### 1.5 Install frontend dependencies

**PowerShell, `frontend/`. Status: IMPLEMENTED, NOT VERIFIED as installation; build is VERIFIED.**

```powershell
Set-Location C:\Users\Govind\Downloads\files\minor-main\frontend
if (Test-Path .\package-lock.json) {
    npm ci
} else {
    npm install
}
Set-Location ..
```

The frontend has `dev`, `build`, and `preview` scripts. There is no configured frontend test or lint script in `frontend/package.json`.

### 1.6 Configure environment variables

The backend reads environment variables in `backend/config.py`. `.env.example` documents the principal local model settings, but the application does not expose a separate configuration-validation CLI.

For a source run, the important local defaults are:

```powershell
$env:OLLAMA_HOST = "http://localhost:11434"
$env:LLM_MODEL = "qwen3:4b"
$env:OLLAMA_NUM_CTX = "4096"
$env:OLLAMA_NUM_PREDICT = "512"
$env:OLLAMA_THINK = "0"
$env:OLLAMA_STREAM = "1"
$env:ALLOWED_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
```

Use `RAG_DATA_HOME` to place mutable data outside the source tree:

```powershell
$env:RAG_DATA_HOME = "C:\Users\$env:USERNAME\AppData\Local\MultimodalRag-dev"
```

This changes the locations of `data/`, `storage/`, Chroma, sessions, users, and encrypted provider-key files. Never put secrets in this handbook or commit them.

Validate the effective configuration without printing credentials:

```powershell
python -c "from backend import config; print({'LLM_MODEL': config.LLM_MODEL, 'OLLAMA_HOST': config.OLLAMA_HOST, 'OLLAMA_NUM_CTX': config.LLM_NUM_CTX, 'OLLAMA_NUM_PREDICT': config.OLLAMA_NUM_PREDICT, 'DEFAULT_PROVIDER': config.DEFAULT_PROVIDER, 'DATA_HOME': str(config.DATA_HOME), 'ALLOWED_ORIGINS': config.ALLOWED_ORIGINS})"
```

### 1.7 Optional Docker stack

`docker-compose.yml` defines Ollama, backend, and frontend. It publishes backend port 8000 and frontend port 8080; Ollama remains internal to the Compose network.

**PowerShell, repository root. Status: IMPLEMENTED, NOT VERIFIED; Docker was not run in this audit.**

```powershell
docker compose up -d --build
docker compose exec ollama ollama pull qwen3:4b
docker compose ps
```

Expected services: `ollama`, `backend`, and `frontend` running. Open `http://localhost:8080`; backend health is `http://localhost:8000/api/health`. Stop without deleting named volumes:

```powershell
docker compose down
```

Do not use `docker compose down -v` unless you intentionally want to delete persisted models, storage, and uploaded data.

## 2. Validate the installation

### 2.1 Python compilation and full regression suite

**PowerShell, repository root. Status: VERIFIED.**

```powershell
python -m compileall -q backend evaluation tests
python -m pytest -q
```

Observed result: `51 passed`. This proves the checked-in Python tests and syntax compile; it does not prove live Groq, Docker, or real-corpus behavior.

### 2.2 Focused metric and provider tests

**PowerShell, repository root. Status: VERIFIED.**

```powershell
python -m pytest tests\unit\test_provider_router.py evaluation\metrics\test_retrieval_metrics.py -q
```

Observed result: `20 passed`. These tests use fake providers for routing and deterministic hand-calculated metric cases.

### 2.3 Backend verification script

`backend/verify_backend.py` checks encrypted key round trips, provider registry contents, router default, and answer-function signatures. It stubs external provider modules but imports the real project modules.

**PowerShell, repository root. Status: IMPLEMENTED, NOT VERIFIED in this handbook session.**

```powershell
python -m backend.verify_backend
```

Expected output ends with `All checks passed.` after backend requirements are installed. Running `python .\backend\verify_backend.py` from the repository root is not valid because the script imports the `backend` package while Python sets the script directory on `sys.path`. In this audit terminal, the package invocation reached the script but stopped at missing `cryptography`; activate the project `.venv` and install `backend\requirements.txt` first. A later failure usually means the selected interpreter has another missing dependency or the provider/answer interfaces drifted.

### 2.4 Frontend build

**PowerShell, `frontend/`. Status: VERIFIED.**

```powershell
Set-Location C:\Users\Govind\Downloads\files\minor-main\frontend
npm run build
Set-Location ..
```

Observed result: TypeScript compilation and Vite production build passed. There are no `test` or `lint` scripts in `package.json`; `npm run build` is the available frontend static check.

### 2.5 Evaluation CLI help

**PowerShell, repository root. Status: VERIFIED.**

```powershell
python .\evaluation\run_eval.py --help
```

Supported options are `--provider ollama|groq|both`, `--all`, the experiment groups `retrieval`, `generation`, `citation`, `performance`, `ocr`, `audio`, `modality`, `ablation`, `--self-test`, `--dataset`, `--session-id`, `--base-url`, `--token`, and `--top-k`.

### 2.6 Evaluation self-test

**PowerShell, repository root. Status: VERIFIED.**

```powershell
python -m evaluation.runner.run_eval --self-test
```

Observed result: synthetic dataset validation, 10/10 synthetic query executions, retrieval, generation, citation, performance, modality, and ablation passed. OCR/audio were `NOT RUN`; provider comparison was skipped because the run uses one synthetic provider. Observed report directory: `reports/evaluation/selftest/selftest_2026-10-01_124644`.

This is plumbing verification only. It is not evidence of answer quality on your documents and does not contact Ollama or Groq.

### 2.7 Dataset validation

There are two related dataset loaders:

- `evaluation/datasets/schema.py` validates the lightweight JSON schema used by the legacy runner.
- `evaluation/schemas/dataset_schema.py` and `evaluation/utils/validation.py` validate the master runner's `QADatasetItem` schema.

There is no standalone `validate-dataset` CLI. Run the master validation directly:

**PowerShell, repository root. Status: IMPLEMENTED, NOT VERIFIED as a standalone command.**

```powershell
python -c "from evaluation.utils.validation import validate_qa_dataset; ok, errors, stats = validate_qa_dataset('evaluation/datasets/rag_test_dataset.json'); print({'valid': ok, 'errors': errors, 'stats': stats}); raise SystemExit(0 if ok else 1)"
```

The full master runner also validates the dataset at the start of a real run. Result schemas are dataclasses in `evaluation/schemas/result_schema.py`; there is no standalone result-schema validator command. Reports are serialized through the reporting modules and should be inspected as JSON after a run.

## 3. Start the backend

### 3.1 Source backend

**PowerShell, repository root, activated `.venv`. Status: IMPLEMENTED, NOT VERIFIED here with a live server.**

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Required conditions:

- `.venv` active and backend dependencies installed.
- Port 8000 free.
- The first startup may load embedding/OCR/reranking models.
- Ollama is required for local LLM answers, but the server can start while Ollama is unavailable.

Open a second PowerShell terminal and verify:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health/live
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

The API documentation is `http://127.0.0.1:8000/docs`; dependency status is `http://127.0.0.1:8000/health/dependencies`; metrics are `http://127.0.0.1:8000/metrics`.

Stop the reload process with `Ctrl+C`. Do not kill the process while it is writing a large ingestion job unless the resulting partial job is handled and verified afterward.

### 3.2 Backend route groups

All `/api` routes require a bearer token except health/metrics routes where the source permits unauthenticated access.

| Purpose | Routes |
|---|---|
| Auth | `POST /api/auth/register`, `/login`, `/logout`; `GET /api/auth/me` |
| Sessions | `POST/GET /api/sessions`, `GET/PATCH/DELETE /api/sessions/{session_id}` |
| Ingestion | `POST /api/ingest`, `POST /api/ingest/async`, `GET /api/ingest/status/{job_id}` |
| Files | `GET /api/files`, `DELETE /api/files/{filename}` |
| Text query | `POST /api/query`, `POST /api/query/stream` |
| Image/audio | `POST /api/query/image`, `/api/query/audio`, `/api/transcribe` |
| Providers | `/api/providers`, `/api/providers/key`, `/api/providers/validate`, `/api/providers/{provider}/models` |
| Active model | `GET /api/llm/active`, `POST /api/llm/providers/{provider}/activate` |
| Sources/media | `GET /api/source/{doc_id}`, authenticated media routes |

## 4. Start the frontend

### 4.1 Vite development server

`frontend/vite.config.ts` sets port 5173 and proxies `/api` to `http://localhost:8000`. The frontend uses relative API URLs; no frontend API environment variable is required for the documented dev setup.

**PowerShell, `frontend/`, backend already running. Status: IMPLEMENTED, NOT VERIFIED live; production build is VERIFIED.**

```powershell
Set-Location C:\Users\Govind\Downloads\files\minor-main\frontend
npm run dev
```

Open `http://localhost:5173`. Log in or register. A backend connectivity failure appears as a frontend error saying the backend cannot be reached. Port conflicts can be handled with Vite's displayed alternate port, but then add that origin to `ALLOWED_ORIGINS` before cross-origin API calls.

### 4.2 Production frontend

The production build is `frontend/dist`. The backend can serve bundled static files when configured/frozen; Docker serves the frontend through nginx on port 8080. Do not assume `frontend/dist` is current after source changes; run `npm run build` first.

## 5. Prepare source documents and datasets

### 5.1 Three different data types

1. **Source documents**: PDFs, DOCX files, images, or audio files ingested into one authenticated chat session.
2. **Evaluation questions**: JSON records sent to `/api/query` by the evaluation runner.
3. **Ground truth**: expected answers, relevant chunk IDs, source/document identifiers, required citations, and modality annotations.

Existing stored reports and vector data are research artifacts. Do not overwrite them or clear Chroma merely to make a test pass.

### 5.2 Supported inputs and annotations

The implementation contains PDF/DOCX parsing, image processing/OCR/captioning, and audio transcription. Actual accepted content is still subject to upload signature checks, configured resource limits, and installed optional tools. Relevant config limits include 200 MB default upload/PDF limits, 500 PDF pages, 64 MP images, and four hours of audio.

Recommended local layout, outside committed secrets:

```text
evaluation-work/
  source_documents/
    text-and-tables.pdf
    report.docx
    diagram.png
    interview.wav
  datasets/
    pilot_v1.json
  notes/
    annotation-notes.md
```

Placing files in a folder is not sufficient. Files must be uploaded through the authenticated frontend or `/api/ingest` endpoint so parsing, chunking, embeddings, Chroma persistence, and FTS5 indexing execute.

### 5.3 Master evaluation dataset format

The master runner accepts a JSON array of `QADatasetItem` objects:

```json
[
  {
    "id": "q-001",
    "question_id": "q-001",
    "question": "What is the stated retention period?",
    "answer": "The documented retention period is ...",
    "answerable": true,
    "difficulty": "basic",
    "category": "factual",
    "modality": "text",
    "source_file": "policy.pdf",
    "source_locator": "page 4",
    "relevant_chunk_ids": ["chunk-id-from-retrieval"],
    "required_citations": ["policy.pdf"],
    "ground_truth_status": "confident"
  }
]
```

The legacy loader accepts `question_id`, `question`, and `category`, with optional `relevant_chunk_ids`, `relevant_document_ids`, `required_citations`, and `expected_answer`. Use the master schema above for the `evaluation/run_eval.py` workflow because its runner uses `answer`, `answerable`, `modality`, `source_file`, and `id`.

Rules:

- Keep `question_id` unique and stable across Ollama/Groq runs.
- Obtain relevant chunk IDs from the actual target session's retrieval response.
- Keep source filenames and citation strings consistent with returned metadata.
- Mark unanswerable items with `answerable: false`; do not invent an answer.
- Keep OCR transcripts and audio transcripts human-verified when measuring CER/WER.
- Use an isolated session per corpus version and record the dataset hash/report metadata.

## 6. Ingest documents

### 6.1 Register and create a session through the API

**PowerShell, second terminal with backend running. Status: IMPLEMENTED, NOT VERIFIED live.**

```powershell
$base = 'http://127.0.0.1:8000'
$email = 'rag-test@example.com'
$password = 'Use-a-local-test-password-123!'
$registration = Invoke-RestMethod "$base/api/auth/register" -Method Post -ContentType 'application/json' -Body (@{email=$email; password=$password} | ConvertTo-Json)
$token = $registration.token
$headers = @{ Authorization = "Bearer $token" }
$session = Invoke-RestMethod "$base/api/sessions" -Method Post -Headers $headers -ContentType 'application/json' -Body (@{title='Pilot evaluation'} | ConvertTo-Json)
$sessionId = $session.id
$sessionId
```

If the email already exists, call `/api/auth/login` with the same JSON shape instead. Keep `$token` in memory only; do not write it to a file or commit it.

### 6.2 Synchronous multipart ingestion

**PowerShell, repository root or any directory; backend running. Status: IMPLEMENTED, NOT VERIFIED live.**

```powershell
curl.exe -X POST "$base/api/ingest" `
  -H "Authorization: Bearer $token" `
  -F "session_id=$sessionId" `
  -F "mode=max_quality" `
  -F "files=@C:\path\to\evaluation-work\source_documents\text-and-tables.pdf" `
  -F "files=@C:\path\to\evaluation-work\source_documents\report.docx"
```

Valid modes are `fast`, `balanced`, and `max_quality`. The response has `status`, `ingested`, and `files`. Inspect `ingested[*].error`, `chunks`, and `skipped_duplicate`. A request can return HTTP success while an individual file has an error entry, so inspect every item.

### 6.3 Asynchronous ingestion

**PowerShell, backend running. Status: IMPLEMENTED, NOT VERIFIED live.**

```powershell
$async = curl.exe -s -X POST "$base/api/ingest/async" `
  -H "Authorization: Bearer $token" `
  -F "session_id=$sessionId" `
  -F "mode=max_quality" `
  -F "files=@C:\path\to\evaluation-work\source_documents\text-and-tables.pdf" | ConvertFrom-Json
$jobId = $async.job_id
Invoke-RestMethod "$base/api/ingest/status/$jobId" -Headers $headers
```

Poll until the returned job status is complete or failed. The job endpoint enforces the owning user. Verify afterward:

```powershell
Invoke-RestMethod "$base/api/files?session_id=$sessionId" -Headers $headers
Invoke-RestMethod "$base/api/sessions/$sessionId" -Headers $headers
```

Re-ingestion is intended to recognize unchanged content, but verify the returned `skipped_duplicate`/chunk information before relying on it. Do not delete `backend/storage`, `backend/data`, or a configured `RAG_DATA_HOME` during an experiment unless you intentionally discard that corpus.

## 7. Verify retrieval before generation evaluation

Use a question whose answer is visibly present in an ingested document.

**PowerShell, backend running and `$token`, `$sessionId` set. Status: IMPLEMENTED, NOT VERIFIED live.**

```powershell
$queryBody = @{
    session_id = $sessionId
    query = 'What is the stated retention period?'
    top_k = 5
    modality = 'all'
    files = $null
    provider = 'ollama'
} | ConvertTo-Json
$retrievalCheck = Invoke-RestMethod "$base/api/query" -Method Post -Headers $headers -ContentType 'application/json' -Body $queryBody
$retrievalCheck.retrieved | Select-Object id, file, page, score, rerank_score
$retrievalCheck.citations
$retrievalCheck.metrics
```

Record the returned `retrieved[].id` values in the dataset annotations. The response also contains `answer`, `citations`, `used_llm`, and stored operational metrics. If `retrieved` is empty, diagnose ingestion/session/modality/file filters first; do not interpret it as a generation failure. If retrieval is populated but the answer fails, diagnose provider/model availability and prompt generation separately.

For a streaming smoke test, the frontend uses `POST /api/query/stream` with the same JSON body and bearer token, receiving SSE events named `citations`, `delta`, and `done`. A raw PowerShell SSE client is not part of the repository; use the frontend or a browser/API client.

## 8. Run the Ollama evaluation

### 8.1 Verify Ollama and the configured model

**PowerShell, any directory. Status: BLOCKED here; commands match the documented Ollama workflow.**

```powershell
ollama --version
Invoke-RestMethod http://localhost:11434/api/tags
ollama list
```

Read the effective model without guessing:

```powershell
python -c "from backend import config; print(config.LLM_MODEL)"
```

The current default is `qwen3:4b`. Pull exactly the configured model if it is absent:

```powershell
ollama pull qwen3:4b
```

Run a minimal generation smoke test only after confirming the model identifier:

```powershell
ollama run qwen3:4b "Reply with exactly: ollama-smoke-ok"
```

Do not replace this model with another model and label the result as the configured Ollama experiment.

### 8.2 Run the real Ollama evaluation

Prerequisites: backend running, target session populated with the same source corpus, valid dataset JSON, bearer token, and Ollama model available.

**PowerShell, repository root. Status: IMPLEMENTED, NOT VERIFIED live.**

```powershell
python .\evaluation\run_eval.py `
  --provider ollama `
  --all `
  --dataset .\evaluation\datasets\pilot_v1.json `
  --session-id $sessionId `
  --base-url $base `
  --token $token `
  --top-k 5
```

The terminal identifies provider/model, validates the dataset, executes queries, reports failures, and writes reports. `--experiment retrieval`, `generation`, `citation`, `performance`, `ocr`, `audio`, `modality`, or `ablation` runs one group. `--self-test` is synthetic and must not be reported as a real Ollama evaluation.

Saved-result regeneration is available without provider calls:

```powershell
python -m evaluation.regenerate_report --input reports\evaluation\<provider>\<run-id> --output reports\verification\regenerated
```

This copies raw results and regenerates JSON/Markdown from saved summary data. Metrics whose evidence is absent remain unavailable.

## 9. Run the Groq evaluation

Groq keys are managed through the authenticated backend keystore or the frontend Provider Panel. They are not read from a documented `GROQ_API_KEY` environment variable by the application generation path.

### 9.1 Secure key workflow through the API

Use the frontend Provider Panel when possible: add the key, validate it, load models, select a returned model, and explicitly activate it. The UI never needs to display the stored key again.

For an API-only workflow, enter the key into a `SecureString` and convert it only in memory for the request; do not echo it or write it to disk:

```powershell
$secureKey = Read-Host 'Groq API key' -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
try { $groqKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
Invoke-RestMethod "$base/api/providers/key" -Method Post -Headers $headers -ContentType 'application/json' -Body (@{provider='groq'; api_key=$groqKey} | ConvertTo-Json)
```

Clear the in-memory variable after use:

```powershell
$groqKey = $null
```

The key-save route stores it encrypted. The key-validation route is separate and does not activate Groq:

```powershell
Invoke-RestMethod "$base/api/providers/validate" -Method Post -Headers $headers -ContentType 'application/json' -Body (@{provider='groq'; api_key=$groqKey} | ConvertTo-Json)
Invoke-RestMethod "$base/api/providers/groq/models" -Headers $headers
```

The model list is fetched from Groq when a stored key is available. It is not proof that every listed model is usable for generation.

### 9.2 Explicit activation and real routing

Select an actual model returned by `/api/providers/groq/models`; do not copy a model name from this document. Then activate it:

```powershell
$groqModel = '<model-id-returned-by-the-api>'
Invoke-RestMethod "$base/api/llm/providers/groq/activate" -Method Post -Headers $headers -ContentType 'application/json' -Body (@{model=$groqModel} | ConvertTo-Json)
Invoke-RestMethod "$base/api/llm/active" -Headers $headers
```

Run the retrieval smoke query again with `provider='groq'` or omit the provider after activation. Confirm the response/session assistant message contains the actual provider and model. A changed UI banner without this metadata is not sufficient evidence.

### 9.3 Groq evaluation

**PowerShell, repository root. Status: BLOCKED until a valid key, model access, network, backend, and annotated session exist.**

```powershell
python .\evaluation\run_eval.py `
  --provider groq `
  --all `
  --dataset .\evaluation\datasets\pilot_v1.json `
  --session-id $sessionId `
  --base-url $base `
  --token $token `
  --top-k 5
```

An invalid key or unsupported model must remain a failed sample/provider run. It must not be silently converted into an Ollama success. Rate limits and network failures should be preserved in failure output.

## 10. Compare Ollama and Groq

The master CLI accepts `--provider both` and calls the provider-comparison experiment after its query/evaluation flow:

```powershell
python .\evaluation\run_eval.py `
  --provider both `
  --all `
  --dataset .\evaluation\datasets\pilot_v1.json `
  --session-id $sessionId `
  --base-url $base `
  --token $token `
  --top-k 5
```

**Status: IMPLEMENTED, NOT VERIFIED live.**

Before using the result scientifically, verify:

- identical stable question IDs and dataset hash;
- the same ingested corpus and retrieval settings;
- the same retrieved contexts in `questions_with_retrieval` when isolating generation;
- actual Ollama and Groq model identifiers;
- failures and unavailable metrics remain explicit;
- prompt/configuration differences are recorded.

The code reuses the collected retrieval items for provider generation in `run_provider_comparison`, but provider comparison is not a live result until both provider calls succeed. The master runner's `--provider both` report has a comparison directory under the run output; inspect its JSON/CSV/PNG rather than relying on terminal summaries alone.

## 11. Test the frontend provider switch

1. Start the backend and frontend in separate terminals.
2. Register or log in at `http://localhost:5173`.
3. Open the provider panel.
4. Add a Groq key and validate it.
5. Load models from the backend, choose a returned model, and explicitly activate it.
6. Confirm `GET /api/llm/active` returns `provider: groq` and the selected model.
7. Send a new question.
8. Inspect the answer/session metadata and backend logs for actual Groq routing.
9. Activate Ollama again and repeat the question.
10. Confirm the new answer says/records Ollama and `qwen3:4b` or the current configured local model.

The corresponding API verification commands are:

```powershell
Invoke-RestMethod "$base/api/llm/active" -Headers $headers
Invoke-RestMethod "$base/api/sessions/$sessionId" -Headers $headers | Select-Object -ExpandProperty messages
```

Test invalid credentials by using the validation control or `/api/providers/validate`; do not replace the active provider until validation and explicit activation succeed. The backend requires a stored key before cloud activation, so a failed activation should leave the previous active state intact.

## 12. Chat-session metrics and evaluation

Every normal text query persists user and assistant messages in the session JSON. The assistant record includes `provider`, `model`, `citations`, `usedLlm`, and metrics such as retrieval/generation/total latency and available token fields. `/api/query/stream` also persists the record after streaming. Image/audio query records currently persist answer/citation information but do not attach the same complete query-evaluation metrics object.

Inspect the stored session through the authenticated API:

```powershell
$sessionRecord = Invoke-RestMethod "$base/api/sessions/$sessionId" -Headers $headers
$sessionRecord.messages | Select-Object role, provider, model, metrics, citations
```

### Operational mode

Available directly from stored normal text-query records:


### Quality mode

Requires joining stored queries to a dataset with stable question IDs or a manual annotation file containing reference answers, relevant chunk/document IDs, and required citations. Then rerun the applicable evaluator over stored records or use the offline runner against the same session. The repository does **not** currently provide a dedicated `evaluate-session` CLI or a session-report generator. Do not claim that a normal chat transcript has answer-quality scores automatically.
The read-only session report CLI is `python -m evaluation.session_report --sessions-dir backend\storage\sessions --output reports\verification\session-report.json`. It reports operational metrics and scores answer/citation fields only when annotations match. Retrieval quality remains `NOT RUN` unless retrieved chunk IDs are persisted.
## 13. Metric reference

| Metric | Definition / required input | Current implementation and validation |
|---|---|---|
| Precision@K | Relevant retrieved items in top K divided by returned top-K items; relevant IDs required | `evaluation/metrics/retrieval_metrics.py`; deterministic tests |
| Recall@K | Relevant top-K items divided by all relevant IDs; relevant IDs required | Same; deterministic tests |
| MRR | Mean reciprocal rank of first relevant result | Same; deterministic tests |
| MAP | Mean average precision over ranked relevant hits | Same; deterministic tests |
| nDCG@K | Discounted ranked gain normalized by ideal gain; graded/binary relevance | Same; deterministic tests |
| Retrieval F1/Hit@K | Harmonic P/R and any-hit indicator | Same; deterministic tests |
| ROC-AUC/PR-AUC | Binary relevance labels plus continuous candidate scores, both classes required | `compute_roc_pr_auc`; not valid for arbitrary answer text |
| Exact match/token F1 | Normalized reference answer or token multiset overlap | `generation_metrics.py`; wrappers retained for compatibility |
| Answer relevance/correctness | Evaluator/judge inputs and reference answers | `generation_evaluator.py`; unavailable without valid references/judge inputs |
| Faithfulness | Claims supported by retrieved evidence or judge output | `faithfulness_metrics.py`/judge; citation presence alone is not semantic proof |
| Citation precision/completeness | Required and actually cited source identifiers | `citation_metrics.py`; required citations needed |
| Retrieval/generation/total latency | Timed operational stages | Query metrics and performance evaluator |
| Resource metrics | CPU/RAM/GPU samples where available | Resource instrumentation; GPU may be `NOT RUN` |
| OCR CER/WER | OCR output versus human-verified transcription | OCR benchmark files required; currently `NOT RUN` without them |
| Audio WER | Transcript versus human-verified reference by condition | Audio benchmark files required; currently `NOT RUN` without them |
| Modality metrics | Retrieval metrics grouped by modality | Modality evaluator |
| Ablation | Configured ablation experiment definitions | Master runner; some variants are synthetic/scaled representations |

Run deterministic metric tests:

```powershell
python -m pytest evaluation\metrics\test_retrieval_metrics.py -q
```

## 14. Full evaluation dataset campaign

### Pilot corpus

Prepare one isolated corpus containing:

- one text-heavy PDF with paragraphs/headings;
- one PDF containing a table;
- one DOCX with headings and a table;
- one image or scanned page if OCR/image retrieval is required;
- one audio file plus human transcript only if audio is required.

Create questions covering direct facts, paraphrases, multi-document synthesis, table lookup, unanswerable questions, irrelevant candidates, citation checks, and supported image/audio cases. Annotate every answerable item with `answer`, `source_file`, `relevant_chunk_ids`, and `required_citations` where applicable.

### Research corpus checklist

- [ ] Source files have stable names and a recorded version/hash.
- [ ] All files are supported by the actual ingestion pipeline.
- [ ] Dataset question IDs are unique and stable.
- [ ] Relevant chunk IDs come from the target ingested session.
- [ ] Reference answers are human-reviewed.
- [ ] Citation annotations identify the source filenames returned by the API.
- [ ] OCR transcriptions are human verified.
- [ ] Audio transcripts, language, duration, and condition are recorded.
- [ ] Missing annotations are represented as unavailable, not zero.
- [ ] Ollama and Groq use the same eligible question set.

One document collection can drive many metrics, but it cannot create ground truth automatically. Exact match, answer relevance, faithfulness, citation completeness, ROC/PR-AUC, OCR, and audio metrics each require their own valid inputs.

## 15. Full automated test suite

**PowerShell, repository root. Status: VERIFIED for local Python/build/browser commands; live-provider and real-corpus commands remain conditional.**

```powershell
python -m compileall -q backend evaluation tests
python -m pytest -q
python -m pytest tests\unit\test_provider_router.py evaluation\metrics\test_retrieval_metrics.py -q
Set-Location .\frontend
npm run build
Set-Location ..
python .\evaluation\run_eval.py --help
python -m evaluation.runner.run_eval --self-test
```

Observed: 51 Python tests passed; frontend build passed; Playwright E2E passed 2/2; self-test passed its synthetic stages. There is no frontend lint/test script beyond the configured Playwright suite.

The one-command local verifier is:

```powershell
python scripts\verify_project.py
```

It runs compilation, backend verification, Python tests, frontend build, Playwright E2E, and evaluation self-test, writing `reports/verification/latest.json`. Add `--live-ollama`, `--live-groq-user-id <id>`, `--session-id <id>`, or `--regenerate <run-dir>` only when those prerequisites are intentionally available.

## 16. Reports and result locations

The master runner writes under:

```text
reports/evaluation/<provider>/<run_id>/
reports/evaluation/comparison/<run_id>/
```

The run directory contains JSON bundles, text/Markdown summaries, CSV suites, `graphs/`, and `paper_tables/` according to the reporting modules. The legacy runner uses timestamped directories under `reports/evaluation/` with summary and figure outputs. Inspect the actual `report_dir` printed at the end of every run.

Saved-result regeneration writes a new output directory and never overwrites the source run. Verified artifact: `reports/verification/regenerated-selftest/`.

## 17. Troubleshooting

| Symptom | Check and action |
|---|---|
| `ModuleNotFoundError` | Activate `.venv`; run `python -m pip install -r backend\requirements.txt`; confirm `python -c "import fastapi"`. |
| Backend import/start failure | Run `python -m compileall -q backend`; start from repository root with `python -m uvicorn backend.main:app ...`. |
| Port 8000/5173/8080 is busy | Stop the old process or use the documented Docker/frontend configuration consistently; update `ALLOWED_ORIGINS` if the frontend origin changes. |
| Frontend cannot reach backend | Confirm `/health/live` on port 8000 and that Vite is proxying `/api`; do not change API URLs to Ollama. |
| Login fails | Check password length and account existence; use `/api/auth/register` once, then `/api/auth/login`; never log the password. |
| Ollama unavailable | Run `ollama --version`, `Invoke-RestMethod http://localhost:11434/api/tags`, start Ollama, and pull the configured model. |
| Model missing | Read `backend.config.LLM_MODEL`; pull that exact identifier; do not silently substitute another model. |
| Groq invalid/unsupported | Validate the stored key, list models, choose a returned model, then explicitly activate it; model listing alone is insufficient. |
| Empty retrieval | Check ingestion response, `/api/files?session_id=...`, session ID, modality/file filters, and source IDs before diagnosing generation. |
| Ingestion error | Inspect each `ingested` item; check file signature, size/page/audio limits, optional OCR/audio dependencies, and model download availability. |
| Duplicate/stale vectors | Use a new isolated session; inspect `skipped_duplicate`; do not clear existing Chroma/storage without a deliberate backup and experiment decision. |
| Dataset validation failure | Run the direct validation command in Phase 2; check required fields, `answerable`, reference answer, modality, and stable IDs. |
| Missing quality metric | Add the required reference answer, relevant IDs, citation labels, binary labels/scores, or human annotation; missing data is not a zero. |
| Partial evaluation | Preserve the run directory and failure entries; fix the provider/session/data issue and rerun with a distinct run/session identifier. |
| Docker failure | Run `docker compose config`, `docker compose ps`, and `docker compose logs backend ollama`; do not remove volumes unless data deletion is intended. |

## 18. Final operating sequence

1. Activate `.venv` and verify configuration.
2. Start Ollama and confirm the exact configured model, or start the Docker Compose stack.
3. Start `backend.main:app` on port 8000.
4. Verify `/health/live`, `/api/health`, and `/docs`.
5. Start Vite on port 5173, or open Docker frontend on port 8080.
6. Register/login and create an isolated session.
7. Ingest source documents and verify `/api/files`.
8. Run a known-answer retrieval/query smoke test and record returned chunk IDs.
9. Create and validate the annotated dataset.
10. Run Ollama evaluation and archive its report directory.
11. Configure, validate, and explicitly activate Groq only when credentials are available.
12. Run Groq evaluation and archive its separate report directory.
13. Run `--provider both` only after confirming comparable samples and configurations.
14. Inspect session messages for actual provider/model and operational metrics.
15. Record unavailable metrics, failures, environment metadata, and dataset version in the research report.
