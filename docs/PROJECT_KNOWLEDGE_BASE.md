# Multimodal RAG Project Knowledge Base

Audit date: 2026-10-05  
Repository audited: `minor-main`  
Primary source of truth: current source code and runtime configuration.

## How To Read This Document

Project-specific statements are labelled as follows:

- **VERIFIED FROM CODE**: directly observed in source.
- **VERIFIED FROM CONFIG**: observed in environment/configuration files.
- **VERIFIED FROM DEPENDENCY VERSION**: observed in dependency manifests.
- **VERIFIED FROM TEST RESULT**: observed by running the command listed.
- **VERIFIED FROM GENERATED REPORT**: observed in a generated evaluation report.
- **PARTIALLY IMPLEMENTED**: code exists, but behavior is incomplete, approximate, or fragile.
- **NOT IMPLEMENTED**: not present in the current implementation.
- **REQUIRES VERIFICATION**: the repository does not prove the claim.
- **GENERAL TECHNICAL KNOWLEDGE**: explanatory material, not a claim about this project.

## 1. Executive Summary

This project is a Python FastAPI and React application for querying uploaded documents and media with retrieval-augmented generation. It accepts PDFs, DOC/DOCX files, images, and audio. Text is indexed in both Chroma dense search and SQLite FTS5 lexical search. Images can be indexed with CLIP and represented by OCR/captions. Audio is transcribed with faster-whisper. Search results are fused with Reciprocal Rank Fusion and optionally reranked with a CrossEncoder. A provider router can use local Ollama (`qwen3:4b`) or cloud providers, including Groq (`openai/gpt-oss-120b`).

The system is genuinely multimodal at ingestion and retrieval boundaries, but it is not a single end-to-end multimodal neural model. Images become visual vectors plus OCR/caption text; audio becomes timestamped transcript text. The final answer is generated from retrieved textual context and citations.

## 2. Verified Project Shape

```text
minor-main/
  backend/                 FastAPI app, ingestion, retrieval, generation, auth
  frontend/                React/Vite user interface and Playwright tests
  evaluation/              datasets, metric implementations, runners, CLI
  tests/                   Python unit, security, and evaluation tests
  docs/                    project documentation and generated knowledge base
  deploy/ docker/ k8s/     deployment material; verify before publishing
  scripts/ security/       operational and security utilities
  reports/                 curated reports plus generated evaluation output
  assets/                  project media/assets; review for private content
  backups/                 local copies; do not publish
```

The audited folder is **not currently a Git repository**. There is therefore no local commit history, tracked-file list, or history scan to inspect. Initialize Git only after reviewing the commit lists below.

## 3. Commit Policy

### Should be committed

- Application source under `backend/` and `frontend/src/`.
- `backend/requirements.txt`, frontend `package.json` and lock files.
- `evaluation/` code and sanitized public datasets/configuration.
- `tests/`, `scripts/`, Docker/Kubernetes/deployment manifests after removing secrets.
- `.gitignore`, `.env.example`, README and curated documentation.
- Architecture diagrams and selected human-reviewed result summaries.

### Should not be committed

- `.venv/`, `frontend/node_modules/`, build output, caches, logs and test reports.
- `backend/data/` and `backend/storage/`, including Chroma, SQLite FTS5, sessions, users, audit logs and provider-key files.
- `evaluation/corpus/` in its current form: it contains local/private-looking documents and media. Publish a redacted sample corpus separately if reproducibility requires one.
- `backups/`, raw generated evaluation output and local upload folders.
- Downloaded model weights, Hugging Face caches, Ollama data and embedding caches.
- `.env` files, API keys, tokens, password stores, private keys and certificates.

The corrected ignore policy is in [`.gitignore`](../.gitignore).

## 4. Security Audit

No actual secret value is reproduced here. The following categories can contain secrets or personal data:

| Location/category | Risk | Action |
|---|---|---|
| `backend/storage/provider_keys.json` | Encrypted provider keys | Never commit; rotate keys if ever exposed |
| `backend/storage/keys.secret` and `secret.key` | Encryption material | Never commit; remove from history if tracked |
| `backend/storage/users.json` and `revoked_tokens.json` | Identity/token data | Never commit |
| `backend/storage/audit.log`, sessions and `backend/data/` | Queries, uploads and audit data | Never commit |
| `.env` and provider environment variables | API keys and endpoints | Keep local; track only `.env.example` |
| `evaluation/corpus/`, `assets/`, backups | Personal documents/media | Sanitize or remove before public release |

The code references `GROQ_API_KEY` and other provider credentials, but references are not proof that a live key is present. Search was performed without printing secret values. Because this folder has no Git history, history removal is **REQUIRES VERIFICATION** after `git init` or after connecting the intended remote. If a secret was ever committed elsewhere, rotate it first and use a history-rewrite tool before publishing.

## 5. System Architecture

```text
User
  -> React/Vite frontend
  -> FastAPI /api/query, /api/ingest and media endpoints
  -> authentication/session and scope checks
  -> parser selected by file signature and extension
  -> text, OCR, caption and transcript records
  -> MiniLM text embeddings / CLIP image embeddings
  -> Chroma cosine collections + SQLite FTS5 lexical index
  -> dense search + BM25 search + optional CLIP image branch
  -> RRF fusion + citation-target deduplication
  -> optional ms-marco MiniLM CrossEncoder reranking
  -> context budget truncation and citation-labelled prompt
  -> Ollama or cloud provider router
  -> citation-filtered answer or grounded abstention
  -> React answer and sources panel
```

### Ingestion data flow

```text
file bytes -> signature validation -> parser
  PDF/DOCX -> pages/paragraphs/tables/embedded images
  image    -> OCR + BLIP caption + CLIP visual vector
  audio    -> faster-whisper segments -> timestamped transcript chunks
text records -> semantic chunks (220 words, 40 overlap fallback)
             -> 384D normalized text vector -> Chroma rag_text + FTS5
image records -> 512D normalized CLIP vector -> Chroma rag_image
```

### Query and generation flow

```text
query -> MiniLM vector and FTS5 query terms
      -> Chroma dense candidates + SQLite BM25 candidates
      -> optional CLIP text-to-image candidates
      -> RRF score = sum(1 / (60 + rank))
      -> deduplicate by citation target
      -> optional CrossEncoder(query, passage)
      -> top results -> 2500-token word-proxy context budget
      -> strict grounded prompt -> selected LLM provider
      -> [n] citations restricted to returned sources
```

### Frontend/backend flow

The React API client stores a bearer token in local storage, sends JSON or multipart requests to the FastAPI backend, and clears the token on HTTP 401. Streaming uses a raw fetch/SSE path. Source previews and media use authenticated requests. The principal user-facing flows are login/register, session creation, upload/ingest, query, provider selection, source viewing, and image/audio query.

## 6. Supported Modalities

| Modality | Current implementation | Evidence/status |
|---|---|---|
| PDF | PyMuPDF page extraction, low-text OCR fallback, tables and embedded images | **VERIFIED FROM CODE**; table path is fragile |
| DOC/DOCX | python-docx paragraphs, tables and embedded images | **VERIFIED FROM CODE** |
| Images | PaddleOCR with Tesseract fallback, BLIP caption, CLIP visual vector | **VERIFIED FROM CODE** |
| Audio | faster-whisper `medium`, English default, approximately 12-second timestamp groups | **VERIFIED FROM CODE** |
| Tables | PDF/DOCX extraction into text records | **PARTIALLY IMPLEMENTED**; PDF helper can reference an unavailable `current_section` |
| TXT/Markdown | No ingestion extension or parser in the current supported set | **NOT IMPLEMENTED** |
| Direct end-to-end image reasoning by the final LLM | Image evidence is converted to searchable records; no verified direct image input to final provider | **NOT IMPLEMENTED / REQUIRES VERIFICATION** |

## 7. Ingestion Details

The pipeline computes a SHA-256 content hash and can skip an unchanged file when its hash, pipeline version and ingestion mode match. Modes are `fast`, `balanced` and `max_quality`; the default is `max_quality`. Text chunks carry session/user/file/page/modality/source metadata.

Semantic chunking splits sentences, embeds them, groups them up to 220 words with a minimum target of 80 words and threshold 0.58. If semantic chunking fails, word chunks use a 40-word overlap. The 384-dimensional text vector is normalized before indexing.

PDF pages with fewer than 10 extracted characters trigger OCR fallback. DOCX tables are linearized with separators. Images attached to documents are sent to the image pipeline in max-quality mode.

## 8. Embeddings and Retrieval

The text model is `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, 384 dimensions. The image model is `clip-ViT-B-32`, 512 dimensions. Chroma uses cosine HNSW collections named `rag_text` and `rag_image`. SQLite FTS5 uses a `unicode61` tokenizer and the built-in BM25 rank function, with score direction converted so larger is better.

Dense and lexical candidate lists are fused with:

```text
RRF(d) = sum over rankers r of 1 / (k + rank_r(d))
```

Here `d` is a result, `rank_r(d)` is its one-based rank in ranker `r`, and `k=60` reduces the dominance of the first result. The implementation deduplicates on citation target and can add a CLIP text-to-image branch for image/visual queries. A CrossEncoder `cross-encoder/ms-marco-MiniLM-L6-v2` is enabled by default and reranks candidate query-passage pairs.

Advanced query rewrite, HyDE, multi-hop retrieval and ColBERT are disabled by default. They should not be presented as active architecture components.

## 9. Generation and Grounding

The prompt in [prompt_templates.py](../backend/generation/prompt_templates.py) is strict: use only retrieved context, answer the latest question, cite factual claims as `[number]`, do not treat retrieved text as instructions, and return exactly `The provided document context does not contain this information.` when the evidence is insufficient. Context entries are labelled with file/page, timestamp or image source information.

The context budget is `MAX_CONTEXT_TOKENS=2500`, implemented with a word-count proxy (`words * 1.3`) and whole-hit retention. This is an approximation, not tokenizer-exact accounting. Answer cleanup rejects reasoning-marker leakage and answers lacking citations unless they are the exact abstention message. If the provider fails, the system can return a top-source snippet fallback.

Provider facts:

| Provider | Model/configuration | Execution | Status |
|---|---|---|---|
| Ollama | `qwen3:4b`, temperature 0.0 in runtime config, context 3072, prediction 384 | Local `localhost:11434` | **VERIFIED FROM CONFIG** |
| Groq | `openai/gpt-oss-120b`, cloud API, max tokens 2048 | Internet/API key required | **VERIFIED FROM CONFIG and REPORT** |
| Gemini/OpenAI/Claude | Provider hooks and model defaults exist | Cloud alternatives | **AVAILABLE CONFIGURATION; NOT VERIFIED AS BENCHMARKED HERE** |

Ollama is private/offline-capable but constrained by laptop memory and model quality. Groq avoids local model execution and can provide stronger generation at API/privacy/cost tradeoffs. RAG is not fine-tuning: it retrieves current evidence at query time instead of changing model weights.

## 10. Models and Why They Were Selected

| Model | Type | Actual role | Key verified details | Defence rationale |
|---|---|---|---|---|
| paraphrase-multilingual-MiniLM-L12-v2 | text bi-encoder | chunk/query embeddings | 384D; normalized | Lightweight semantic retrieval with multilingual coverage |
| clip-ViT-B-32 | image-text embedding | image vectors and image-query branch | 512D; normalized | Shared image/text vector space for visual retrieval |
| Salesforce/blip-image-captioning-base | image captioner | converts images into searchable caption text | exact parameter count not verified | Adds a textual description when image vectors alone are insufficient |
| PaddleOCR | OCR engine | primary image and low-text PDF OCR | version 3.7.0 dependency | Better document OCR path; CPU configured in loader |
| Tesseract | OCR fallback | fallback when PaddleOCR fails | `pytesseract` 0.3.13 | Widely available fallback |
| faster-whisper `medium` | ASR | audio transcription | English default; float16 CUDA/int8 CPU | Local transcription with timestamps |
| ms-marco-MiniLM-L6-v2 | CrossEncoder | reranking | candidate batch 16 | More accurate pairwise relevance than embedding similarity alone |
| qwen3:4b | local LLM | Ollama answer generation | context/prediction settings above | Fits the local development hardware better than 70B/120B |
| openai/gpt-oss-120b | cloud LLM | Groq answer generation | report provider/model verified | Cloud inference provides a second quality/latency comparison |

Parameter count, hidden size, tokenizer internals, exact context window for downloaded provider binaries, and quantization format are **REQUIRES VERIFICATION** unless shown in the model runtime metadata. Do not invent these values during defence.

## 11. Beginner Model Vocabulary

**Parameters** are learned numeric weights. **Dimensions** are the number of coordinates in a representation. **An embedding** is a vector produced for text or an image. **Tokens** are tokenizer units, not characters or words exactly. **A context window** is the maximum token sequence a model can process for one request. A 384D sentence vector means the encoder maps the sentence to 384 numeric coordinates; each coordinate is not a human-readable feature, but the complete vector supports similarity comparisons.

AI is the broad field of machine behaviour; ML learns patterns from data; deep learning uses multilayer neural networks; NLP handles language; an LLM predicts token sequences; a Transformer uses attention to mix information across tokens. RAG retrieves external evidence and places it in the prompt before generation. Multimodal RAG does the same after extracting or aligning evidence from more than one input modality.

## 12. Core Similarity Mathematics

For vectors `a` and `b`, cosine similarity is:

```text
cos(a,b) = (a dot b) / (||a|| ||b||)
```

With normalized vectors, dot product equals cosine similarity. Euclidean distance is `sqrt(sum((a_i-b_i)^2))`; it measures geometric separation but is sensitive to scale. The project normalizes embedding vectors and configures Chroma for cosine distance.

Different wording can produce nearby vectors because the encoder learned contextual patterns, not exact word matching. Keyword search can miss "automobile" for a query about "car"; semantic retrieval may connect them.

## 13. Evaluation Methodology

The verified CLI is:

```text
python evaluation/run_eval.py --self-test
python evaluation/run_eval.py --provider ollama --all
python evaluation/run_eval.py --provider groq --all
```

Additional options include `--experiment retrieval|generation|citation|performance|ocr|audio|modality|ablation`, `--dataset`, `--session-id`, `--base-url`, `--token` and `--top-k`. The live runner loads `evaluation/datasets/rag_test_dataset.json`, calls `/api/query`, records retrieval/generation/citation/performance/resource data and writes reports under `reports/evaluation/`.

The self-test creates 10 synthetic QA items and simulates parts of the workflow. It proves that the evaluation plumbing and metric calculations execute; it does not prove real-world OCR/audio quality, generalization or production answer quality. OCR and audio are `NOT RUN` in the self-test.

The ablation runner is **PARTIALLY IMPLEMENTED**: several configurations are approximated by scaling or truncating existing results rather than rerunning the live system with one component disabled. Report such results as exploratory, not causal evidence.

## 14. Metrics and Formulas

| Metric | Formula/meaning | Interpretation |
|---|---|---|
| Precision@K | relevant results in top K / K | retrieved list purity |
| Recall@K | relevant results in top K / all relevant | coverage |
| F1@K | `2PR/(P+R)` | balance of precision and recall |
| Hit@K | 1 if at least one relevant result is in top K, else 0 | question-level success |
| MRR | average `1/rank(first relevant)` | rewards early first evidence |
| AP/MAP | mean of precision values at relevant ranks, then mean across questions | rewards all relevant ranks |
| DCG@K | implementation uses `sum(rel_i / log2(i+1))` | rank discount; binary relevance matches common gain form |
| nDCG@K | `DCG/IDCG` | normalized ranking quality |
| ROC-AUC | probability a relevant candidate scores above a non-relevant one | threshold-independent ranking separation |
| PR-AUC | precision-recall area | more informative when positives are rare |
| Exact match | normalized prediction equals reference | strict answer match |
| Token F1 | token overlap precision/recall harmonic mean | partial answer overlap |
| Citation presence | answer contains citation syntax | citation formatting check |
| Citation precision | cited sources that are relevant / cited sources | source selection quality |
| Claim accuracy | supported cited claims / evaluated claims | evidence support |
| P50/P95 | 50th/95th percentile latency | typical/tail latency; P95 exposes slow requests |

True positive means a relevant candidate was retrieved/predicted; false positive means irrelevant evidence was retrieved; false negative means relevant evidence was missed; true negative means a non-relevant candidate was correctly excluded. ROC-AUC and PR-AUC can differ strongly on imbalanced retrieval because ROC includes the large negative population while PR focuses on positive retrieval quality.

## 15. Verified Evaluation Results

### Real Ollama run

Source: `reports/evaluation/ollama/2026-10-02_114157/summary.md`, 250 questions, 0 errors, qwen3:4b.

| Metric | Value |
|---|---:|
| Precision@5 | 0.3319 |
| Recall@5 | 0.2950 |
| F1@5 | 0.2684 |
| Hit@5 | 0.8407 |
| MRR | 0.7145 |
| MAP | 0.2390 |
| nDCG@5 | 0.4588 |
| ROC-AUC / PR-AUC | 0.7310 / 0.5541 |
| Faithfulness mean | 0.6811 |
| Citation presence | 1.0000 |
| Total latency P50 / P95 | 25,287.75 / 38,258.91 ms |
| Peak VRAM | 3,844 MB |

### Real Groq run

Source: `reports/evaluation/groq/2026-10-02_162918/summary.json`, 250 questions, 0 errors, 226 evaluated retrieval queries, `openai/gpt-oss-120b`.

| Metric | Value |
|---|---:|
| Precision@5 | 0.3319 |
| Recall@5 | 0.2950 |
| F1@5 | 0.2684 |
| Hit@5 | 0.8407 |
| MRR | 0.7145 |
| MAP | 0.2390 |
| nDCG@5 | 0.4588 |
| ROC-AUC / PR-AUC | 0.7278 / 0.5412 |
| Answer correctness / relevance | 0.4596 / 0.4857 |
| Faithfulness / token F1 | 0.7409 / 0.2638 |
| Citation presence / source precision | 0.3200 / 0.8872 |
| Citation claim accuracy / completeness | 0.1498 / 0.4000 |

The identical retrieval values are expected because provider switching changes generation, not the retrieval index, when the same session and corpus are used. Generation and citation values must still be compared from the corresponding provider report. Do not describe these runs as a randomized scientific comparison: the dataset, corpus and system state are fixed and the provider call path can have external variability.

### Fresh self-test

The fresh run passed with 10 synthetic questions. It produced `Precision@5=0.5`, `Recall@5=0.5`, `MRR=1.0`, `nDCG@5=0.6131`, and total latency P50 61 ms/P95 77 ms. It also reported OCR and audio as not run. These figures are plumbing checks, not benchmark claims.

## 16. Testing

Verified commands and results:

| Command | Result | What it proves |
|---|---|---|
| `python -m pytest` | **82 passed** | Python tests currently pass |
| `python -m compileall backend evaluation tests scripts security` | **passed** | Python files compile |
| `npm.cmd run build` in `frontend/` | **passed** | TypeScript/Vite production build succeeds |
| `python evaluation/run_eval.py --self-test` | **passed** | Evaluation plumbing/self-test succeeds |

The repository contains unit/security/evaluation tests and frontend Playwright configuration. A successful frontend build is not an end-to-end browser test. Current evidence does not establish a production deployment test, full OCR benchmark, full audio benchmark or load test.

## 17. Backend API Surface

Important routes verified in `backend/main.py` include:

| Route family | Methods/purpose |
|---|---|
| `/api/health`, `/health/live`, `/health/ready`, `/health/dependencies` | health and dependency checks |
| `/api/auth/*` | register, login, logout, current user |
| `/api/sessions*` | create/list/read/update/delete sessions |
| `/api/ingest`, `/api/ingest/async`, `/api/ingest/status/{job_id}` | upload and ingestion |
| `/api/files*` | list/delete indexed files |
| `/api/query`, `/api/query/stream` | grounded query and streaming answer |
| `/api/query/image`, `/api/query/audio`, `/api/transcribe` | image/audio query operations |
| `/api/source/{doc_id}`, `/api/media/{session_id}/{filename}` | evidence/source retrieval |
| `/api/providers*`, `/api/llm/*` | provider keys, validation and activation |
| `/metrics` | service metrics |
| `/api/reset` | reset operation; protect in deployment |

Authentication is bearer-token based. CORS defaults to local origins and can be widened through configuration. Exact Pydantic request/response fields should be taken from the route models when writing an API contract; do not infer them from route names alone.

## 18. Storage

Chroma stores persistent dense vectors and metadata in the configured local Chroma directory. SQLite FTS5 stores searchable text and metadata in `backend/storage/lexical_index.sqlite3`. The filesystem stores uploads, extracted media and audit/session data. These stores are runtime state and can be rebuilt from source documents; they should not be committed.

## 19. Error Handling And Security

The code validates file signatures, limits upload sizes, supports authentication, rate limiting and CORS configuration, and treats retrieved context as untrusted data in the prompt. Provider failures can retry/fail over only for retryable failures. Missing evidence produces a grounded abstention message.

Remaining risks include malicious document parsing, prompt injection through retrieved text, token storage in browser local storage, accidental public upload of private corpus files, cloud-provider data disclosure, and a reset/admin surface that must be protected. File isolation, antivirus/sandboxed parsing, stronger browser token storage, audit review, secret rotation and explicit user consent for cloud providers are appropriate future hardening.

## 20. Hardware And Performance

The generated environment reports identify Windows 10, Python 3.11.9, an Intel CPU, NVIDIA RTX 3050 Laptop GPU, CUDA 12.1 and PyTorch CUDA availability. The real Ollama report reached 3,844 MB peak VRAM and 15.37 GB peak RAM. A 70B/120B model cannot normally fit wholly into 4 GB VRAM; quantization, CPU offload and memory bandwidth would make local inference slow and still memory-heavy. The 4B local model is a practical hardware choice, while the 120B cloud model is an external comparison point.

Exact parameter counts, quantization file type and measured model-load time are **REQUIRES VERIFICATION** from the provider/model runtime. Do not claim that the cloud model runs on the laptop GPU.

## 21. Dependency And Version Matrix

| Component | Version/fact |
|---|---|
| Python | 3.11.9, verified runtime |
| FastAPI | 0.115.6 |
| Uvicorn | 0.34.0 |
| PyMuPDF | 1.25.1 |
| python-docx | 1.1.2 |
| sentence-transformers | 3.3.1 |
| transformers | 4.47.1 |
| Pillow | 11.0.0 |
| PaddleOCR | 3.7.0 |
| faster-whisper | 1.1.0 |
| pytesseract | 0.3.13 |
| ChromaDB | unpinned in requirements; installed runtime version requires verification |
| React / React DOM | 18.3.1 |
| Vite | 5.4.11 |
| TypeScript | 5.6.3 |
| Tailwind CSS | 3.4.15 |
| Playwright | 1.63.0 in frontend manifest |
| Ollama local model | qwen3:4b |
| Groq model | openai/gpt-oss-120b |
| CUDA | 12.1 reported by evaluation environment |

The `.env.example` Groq model value differs from the current code/evaluation value and should be aligned before release. This is a reproducibility issue, not evidence that both models were tested in the same run.

## 22. Reproducibility Checklist

1. Clone the repository after initializing/publishing Git.
2. Create a Python 3.11 virtual environment and install `backend/requirements.txt`.
3. Install frontend dependencies with the tracked frontend lock file.
4. Copy `.env.example` to `.env`; provide secrets only locally.
5. Start Ollama and make `qwen3:4b` available if using local generation.
6. Start the FastAPI backend and the Vite frontend using the project scripts/README.
7. Create a session, upload supported files, wait for ingestion, then query.
8. Run `python evaluation/run_eval.py --self-test` first.
9. Run live evaluation only with a running backend, prepared corpus, and authorized provider credentials.
10. Never use the current private corpus as a public GitHub dataset without redaction.

Because the repository contains multiple historical READMEs and deployment variants, exact production start commands are **REQUIRES VERIFICATION** against the chosen deployment target. The evaluation CLI commands above are verified from its argument parser.

## 23. Troubleshooting

| Problem | Likely cause | Verification/action |
|---|---|---|
| backend will not start | missing dependency or `.env` setting | run the health endpoint and inspect startup logs |
| Ollama failure | service/model unavailable | check `localhost:11434` and `qwen3:4b` |
| Groq failure | missing/expired `GROQ_API_KEY` or provider outage | validate key locally; never print it |
| slow local queries | CrossEncoder, OCR, CPU fallback or GPU memory pressure | inspect stage latency and VRAM report |
| poor PDF answers | scanned PDF, OCR quality, chunking or retrieval miss | check extracted source records and citations |
| missing table evidence | PDF table helper is fragile | inspect parser logs; treat table support as partial |
| frontend 401 | expired token | log in again; API client clears stale token |
| build policy error on Windows | PowerShell blocks `npm.ps1` | use the repository's approved npm command path, such as `npm.cmd` |
| evaluation has no live answers | backend not running or no corpus/session | use self-test, then verify base URL/session/corpus |

## 24. Limitations And Future Scope

Current limitations are OCR/audio benchmark coverage, private/local corpus dependence, table extraction fragility, word-proxy token budgeting, no verified TXT/Markdown ingestion, optional advanced retrieval disabled by default, model/runtime version drift, high local latency, and ablations that are partly simulated. RAG reduces unsupported answers but cannot eliminate hallucination. Citation presence is not the same as claim correctness.

Future work should prioritize a sanitized public benchmark, true component-toggle ablations, real OCR/audio evaluation, table parser tests, exact tokenizer budgeting, calibrated confidence, streaming UX, stronger cross-modal evidence handling, secret/key management, and deployment/load testing.

## 25. Scorecard

| Area | Assessment | Reason |
|---|---|---|
| Architecture | Good | Clear modular ingestion/retrieval/generation split |
| Retrieval | Good | Dense + FTS5 + RRF + optional reranking are implemented |
| Multimodality | Good | PDF/DOCX/image/audio paths exist; cross-modal reasoning is limited |
| Generation | Good | Strict grounding/citation prompt and provider switching |
| Evaluation | Needs Improvement | Real reports exist, but ablation/self-test interpretation needs care |
| Testing | Good | 82 Python tests, compileall and frontend build pass |
| Security | Needs Improvement | Stronger public-corpus and secret-history process required |
| Reproducibility | Needs Improvement | local state, unpinned Chroma and config mismatch |
| Performance | Needs Improvement | Ollama P95 is about 38 seconds in the recorded run |
| Scalability | Needs Improvement | local Chroma/SQLite/filesystem state and single-node assumptions |
| Documentation | Good after this package | source-grounded, with explicit gaps |

## 26. Verified Facts Matrix

### Verified

FastAPI/React structure; supported PDF/DOC/DOCX/image/audio extensions; MiniLM 384D text embeddings; CLIP 512D image embeddings; Chroma and SQLite FTS5; BM25; RRF with `k=60`; CrossEncoder reranking enabled by default; prompt grounding/abstention rule; Ollama qwen3:4b; Groq openai/gpt-oss-120b; 82 pytest passes; compileall pass; frontend production build pass; self-test pass; real Ollama and Groq 250-question reports with 0 errors.

### Partially verified

Exact provider model runtime metadata; Chroma installed version; deployment commands; public reproducibility of the corpus; table extraction reliability; true causal ablations; exact cloud generation comparison; detailed API schemas without reading every Pydantic model.

### Not implemented or future

TXT/Markdown ingestion; default-on query rewrite, HyDE, multi-hop or ColBERT; a verified end-to-end multimodal LLM input path; complete real OCR/audio benchmark in self-test; fine-tuning; training a project-specific model; a claim that RAG eliminates hallucination.

## 27. Rapid Defence Sheet

**30 seconds:** This is a multimodal RAG system that ingests PDF, DOCX, images and audio, indexes semantic and lexical evidence, fuses and reranks results, then generates cited answers with local Ollama or cloud Groq.

**One minute:** Files are validated and parsed. Text, OCR, captions and transcripts become metadata-rich chunks. MiniLM and CLIP create normalized vectors; Chroma handles dense search and SQLite FTS5 handles BM25. RRF merges candidates, a CrossEncoder reranks them, and a strict prompt constrains the LLM to cite or abstain.

**Three minutes:** Explain ingestion, dual retrieval, RRF, reranking, context budget, provider router, citation mapping, evaluation, limitations and why local/cloud modes exist. State actual numbers only from the report tables in this document.

**Most important distinctions:** RAG is not fine-tuning; embeddings are not encryption; a vector database stores vectors/metadata, not the LLM; higher recall can reduce precision; citation presence does not prove citation correctness; synthetic self-tests do not prove real-world accuracy.

## 28. Presentation Script Outline

1. **Title:** Multimodal Retrieval-Augmented Generation for grounded document QA.
2. **Problem:** keyword search misses paraphrases and media evidence.
3. **Motivation:** retrieve evidence at query time and reduce unsupported generation.
4. **Objectives:** ingest multiple modalities, retrieve relevant evidence, cite answers, compare providers.
5. **Existing system:** text-only search or manual document inspection is limited.
6. **Proposed system:** parser, OCR/ASR/captioning, embeddings, FTS5, Chroma, RRF, reranking and LLM.
7. **Architecture:** walk left to right through the system diagram.
8. **Multimodal pipeline:** explain how images/audio become searchable evidence.
9. **Retrieval:** dense MiniLM, FTS5 BM25, optional CLIP branch, RRF and CrossEncoder.
10. **Generation:** 2500-token context budget, numbered citations and abstention.
11. **Evaluation:** 250-question live reports plus 10-question synthetic self-test.
12. **Results:** quote the verified Ollama/Groq tables, including latency and limitations.
13. **Comparison:** Ollama is local/private but slower and smaller; Groq is cloud and uses a larger model.
14. **Limitations:** table path, private corpus, latency, partial ablations, no TXT/Markdown.
15. **Future:** real ablations, public benchmark, better multimodal reasoning and deployment hardening.
16. **Conclusion:** the project demonstrates a modular grounded RAG workflow and reports its evidence honestly.

## 29. Common Defence Mistakes

| Do not say | Say instead |
|---|---|
| “RAG is fine-tuning.” | RAG retrieves evidence at query time; fine-tuning changes weights. |
| “Embeddings are encrypted text.” | Embeddings are learned numeric representations used for similarity. |
| “The vector DB stores the model.” | It stores vectors and metadata; model weights live elsewhere. |
| “RAG removes hallucination.” | Grounding reduces unsupported answers but cannot guarantee truth. |
| “Higher accuracy always means better.” | Retrieval quality, answer quality, citations, latency and cost must be balanced. |
| “The LLM knows our documents.” | The LLM receives selected retrieved context in the prompt. |
| “We tested every model mentioned.” | Separate models actually tested from configured or discussed alternatives. |
| “The self-test proves production quality.” | It proves the evaluation plumbing; real benchmark reports are separate. |

## 30. Final Consistency Check

Architecture matches the current retrieval and generation code. Model names match runtime configuration except for the noted `.env.example` Groq-model mismatch. Metrics and reported values are taken from current evaluation code/reports. Test claims match current executed results. `.gitignore` now excludes local runtime state, private evaluation corpus, generated reports, caches and frontend output. Unsupported claims are explicitly marked.
