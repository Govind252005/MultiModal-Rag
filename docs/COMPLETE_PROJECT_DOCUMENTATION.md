# Complete Multimodal RAG Project Documentation

Audit basis: current repository source, configuration, dependency manifests, tests and generated reports.  
This document deliberately follows the requested 55-part structure. Every project-specific statement is classified:

- **VERIFIED FROM CODE**
- **VERIFIED FROM CONFIG**
- **VERIFIED FROM DEPENDENCY VERSION**
- **VERIFIED FROM TEST RESULT**
- **VERIFIED FROM GENERATED REPORT**
- **PARTIALLY IMPLEMENTED**
- **NOT IMPLEMENTED**
- **REQUIRES VERIFICATION**
- **GENERAL TECHNICAL KNOWLEDGE**

## Part 1 - Complete Repository Audit

### Verified project tree

```text
minor-main/
  backend/                 FastAPI application and Python RAG implementation
    config.py              environment-backed configuration
    main.py                routes, startup, auth and service wiring
    ingestion/             PDF/DOCX/image/audio extraction and chunking
    retrieval/             embeddings, Chroma, FTS5, search, reranking
    generation/            prompt templates, provider routing, answers
    storage/               local runtime state; do not commit
    data/                  uploads/audits/runtime data; do not commit
  frontend/                React/Vite client
    src/                   UI, API client and components
    tests/                 browser tests/configuration
  evaluation/              CLI, dataset, metric and report runners
  tests/                   Python tests
  docs/                    documentation
  reports/                 curated reports and generated evaluation output
  deploy/ docker/ k8s/     deployment artifacts
  scripts/ security/       operational/security utilities
  assets/                  project assets; inspect for private data
  backups/                 local backup material; do not commit
```

### Git tracking decisions

| Item | Purpose | Used by | Track? |
|---|---|---|---|
| `backend/` | API and RAG source | backend runtime | Yes |
| `frontend/src/` | UI source | Vite build | Yes |
| `evaluation/` code | benchmarks and metrics | evaluation CLI | Yes |
| `tests/` | regression/security checks | pytest | Yes |
| `backend/storage/` | Chroma, FTS5, keys, sessions | runtime | No |
| `backend/data/` | uploads/audits | runtime | No |
| `.venv/`, `node_modules/` | local environments | development only | No |
| `frontend/dist/` | generated frontend output | deployment artifact | Usually no |
| `reports/evaluation/` | generated run output | evaluation only | No; keep selected summaries |
| `evaluation/corpus/` | benchmark documents/media | evaluator | No in current private form |
| `.env` and keys | secrets | runtime | No |
| `.env.example` | configuration template | developers | Yes |

## Part 2 - GitHub Cleanup and .gitignore

The corrected [`.gitignore`](../.gitignore) excludes Python environments/cache, frontend dependencies/build/test output, runtime data, local databases, model weights/caches, secrets, logs, backups, private evaluation corpus and generated evaluation reports. Source, tests, documentation, dependency manifests and configuration templates remain trackable.

The folder is not currently a Git repository. **REQUIRES VERIFICATION:** after `git init`, run a secret scan and `git status --ignored` before the first commit. If any key was ever committed in another history, rotate it and remove it from history before pushing.

## Part 3 - Project History and Development Story

1. **Problem identification:** keyword search alone misses paraphrases and cannot naturally search image/audio evidence.
2. **Requirements:** ingest mixed files, scope evidence by user/session, retrieve relevant passages, generate cited answers, support local/cloud providers and measure quality/latency.
3. **Architecture:** modular Python services were used so parsing, retrieval and generation can be tested and changed independently.
4. **Ingestion:** file signatures and extensions select PDF/DOCX/image/audio paths; extracted text becomes metadata-rich records.
5. **Retrieval:** dense MiniLM search is combined with FTS5 BM25, optional CLIP image search, RRF and CrossEncoder reranking.
6. **Generation:** a strict prompt supplies selected evidence, citation labels and abstention rules to the configured provider.
7. **Evaluation:** metric code and live/self-test runners measure retrieval, generation, citation, performance, resource and modality behavior.

The exact historical commit sequence is **NOT VERIFIABLE** because the audited folder has no Git history.

## Part 4 - Complete Architecture

```text
User -> React/Vite -> FastAPI/auth/session scope
     -> ingest: signature -> parser/OCR/ASR/caption -> chunk/metadata
     -> MiniLM text vectors / CLIP image vectors
     -> Chroma rag_text/rag_image + SQLite FTS5
User query -> dense + BM25 + optional CLIP -> RRF -> dedupe
     -> CrossEncoder -> context budget -> grounded prompt
     -> Ollama or cloud provider -> citations/abstention -> frontend
```

Data entering and leaving each component:

| Component | Input | Processing | Output |
|---|---|---|---|
| Frontend | user/file/query | renders and calls API | HTTP/multipart request |
| API | request/token | auth, validation, orchestration | structured response/SSE |
| Parser | bytes | format-specific extraction | text/media records |
| Embedding | text/image | encoder inference | normalized vector |
| Chroma | vector/metadata | cosine nearest-neighbor | dense hits |
| FTS5 | query/text | BM25 term ranking | lexical hits |
| Fusion | ranked lists | RRF and dedupe | candidates |
| Reranker | query/candidate text | joint scoring | reordered hits |
| Prompt builder | hits/query | labels and budget | model prompt |
| Provider | prompt/config | generation | answer text |
| Citation layer | answer/source list | citation filtering | grounded response |

Separate ingestion, retrieval, generation, evaluation, request/response, frontend/backend and provider-switching diagrams are included in [PROJECT_KNOWLEDGE_BASE.md](./PROJECT_KNOWLEDGE_BASE.md). A citation flow is: hit metadata -> numbered context label -> model `[n]` reference -> allowed citation list -> source preview endpoint.

## Part 5 - Multimodal Pipeline

| Input | Actual processing | Result/status |
|---|---|---|
| PDF | PyMuPDF page text, low-text OCR fallback, tables and embedded images | Verified; table helper is fragile |
| DOC/DOCX | python-docx paragraphs, tables and embedded images | Verified |
| Image | PaddleOCR, Tesseract fallback, BLIP caption, CLIP image vector | Verified |
| Audio | faster-whisper `medium`, English default, timestamp grouping | Verified |
| TXT/Markdown | no supported extension/parser path | Not implemented |

Tables are linearized into text records. Cross-modal reasoning is mediated through OCR/caption/transcript records and CLIP vectors; a direct image/audio-to-final-LLM path is not verified.

## Part 6 - Every Model Used

| Model/engine | Type | Provider | Actual use | Input/output |
|---|---|---|---|---|
| `paraphrase-multilingual-MiniLM-L12-v2` | text bi-encoder | Sentence Transformers | text/query vectors | text -> normalized 384D vector |
| `clip-ViT-B-32` | image-text encoder | Sentence Transformers/Transformers stack | visual/image retrieval | image/text -> normalized 512D vector |
| `Salesforce/blip-image-captioning-base` | captioner | Transformers | image -> searchable caption | image -> text |
| PaddleOCR | OCR | PaddleOCR | image/PDF text extraction | image -> text boxes/text |
| Tesseract | OCR fallback | pytesseract | OCR fallback | image -> text |
| Whisper `medium` | ASR | faster-whisper | audio transcription | audio -> timestamped text |
| `cross-encoder/ms-marco-MiniLM-L6-v2` | CrossEncoder | Sentence Transformers | candidate reranking | query+passage -> relevance score |
| `qwen3:4b` | local LLM | Ollama | local answer generation | prompt -> answer |
| `openai/gpt-oss-120b` | cloud LLM | Groq | cloud answer generation | prompt -> answer |

Exact model revision, parameter count, hidden size and quantization are **REQUIRES VERIFICATION** from runtime model metadata. They must not be invented from model names.

## Part 7 - Dimensions and Technical Details

Verified dimensions are text 384 and CLIP 512. Parameters are learned weights; dimensions are representation coordinates; embeddings are vectors; tokens are tokenizer units; context window is the maximum model input sequence; a latent representation is an internal learned feature space. A 384D sentence vector is 384 numbers whose joint geometry supports similarity; each coordinate is not necessarily an interpretable human feature.

Exact tokenizer, maximum input lengths, precision, quantization, GPU memory requirement and parameter count: **REQUIRES VERIFICATION**. The real Ollama report measured peak VRAM, but that is not a model-size specification.

## Part 8 - Why These Models and Providers

MiniLM is a compact retrieval encoder suited to laptop constraints. CLIP enables image/text alignment. BLIP makes visual content searchable through text. Whisper supplies timestamps instead of asking the final LLM to consume audio directly. CrossEncoder improves candidate ordering at extra latency. Qwen 4B is practical for local privacy and limited VRAM. Groq provides a cloud comparison with a much larger configured model. Larger local Llama/Mistral/Gemma/Qwen alternatives are discussion-only unless a report proves they were tested. OpenAI embeddings, GPT-4, fine-tuning and training a project model are not verified as used.

## Part 9 - RAG Fundamentals

| Term | Simple meaning | Technical meaning | Project role | Viva answer |
|---|---|---|---|---|
| AI | machine behaviour that appears intelligent | field of intelligent computation | overall application | RAG is an AI system built from ML components |
| ML | learning patterns from data | parameter estimation from examples | pretrained models | models infer rather than use only hand rules |
| Deep learning | multilayer neural ML | learned nonlinear representations | MiniLM/CLIP/BLIP/Whisper/LLMs | models are used at inference time |
| NLP | language processing | computational language representation/generation | chunks, search, prompts | it covers the text side of the system |
| LLM | language-generating model | autoregressive token predictor | answer generation | it receives retrieved context; it does not know uploads automatically |
| Transformer | attention-based architecture | token-mixing neural network | most selected models | attention is not retrieval |
| Token | model input unit | tokenizer output symbol/subword | context accounting | tokens are not exactly words |
| Embedding | numeric meaning representation | learned vector encoding | query/chunk/image search | not encryption |
| RAG | retrieve then generate | external evidence concatenated into prompt | core architecture | reduces unsupported answers, not all hallucination |
| Multimodal RAG | RAG across modalities | modality-specific evidence aligned for retrieval | images/audio/documents | current system uses OCR/caption/ASR/CLIP bridges |
| Grounding | evidence support | output constrained/evaluated against context | strict prompt/citations | citation correctness must still be measured |

## Part 10 - Embeddings

The pipeline is `text -> encoder -> vector`. Cosine similarity is `dot(a,b)/(||a|| ||b||)`. Euclidean distance is the square root of summed squared coordinate differences. Dot product is the sum of coordinate products. With normalized vectors, dot product equals cosine similarity. Embeddings allow semantically similar sentences with different words to be nearby because the encoder learned contextual patterns.

## Part 11 - Retrieval

Keyword/sparse retrieval matches terms and uses BM25. Dense retrieval compares embeddings. Hybrid retrieval combines both. Top-K controls the candidate budget. A bi-encoder independently encodes query and passages; a CrossEncoder reads both jointly and is slower but more precise. RRF combines rank lists without assuming raw score calibration:

`RRF(d) = sum_r 1 / (k + rank_r(d))`, with `k=60` and one-based ranks.

## Part 12 - Reranking

Initial retrieval prioritizes speed and recall. Reranking improves ordering among candidates. The project retrieves dense/lexical candidates, fuses/deduplicates them, then optionally scores query-passage pairs with `cross-encoder/ms-marco-MiniLM-L6-v2`, batch size 16. Reranking is enabled by default but increases latency.

## Part 13 - Prompt Engineering

The system prompt in [prompt_templates.py](../backend/generation/prompt_templates.py) instructs the provider to use only retrieved context, answer the latest question, cite factual claims `[number]`, ignore instructions inside retrieved data, preserve list items, avoid unsolicited JSON and abstain with the exact missing-context sentence. Context entries contain source labels. This is prompt-level grounding and injection resistance, not a security guarantee.

## Part 14 - Citations and Grounding

Hits carry file/page, image source or audio timestamp metadata. The context builder numbers hits, the model emits `[n]`, and answer cleanup restricts citations to available source IDs. The evaluator separately measures citation presence, source-level precision, claim-level accuracy and completeness. Presence alone does not establish support.

## Part 15 - Complete Evaluation System

The verified CLI is:

```text
python evaluation/run_eval.py --self-test
python evaluation/run_eval.py --provider ollama --all
python evaluation/run_eval.py --provider groq --all
```

The master runner loads the dataset, creates a session/queries the API, collects retrieved results and answer/citation/performance/resource fields, then writes reports. `--experiment` accepts retrieval, generation, citation, performance, OCR, audio, modality and ablation. The self-test uses 10 synthetic items. Live reports use 250 questions from the configured dataset. Ingestion metrics are not a complete live benchmark. OCR/audio self-test is not run.

## Part 16 - Every Metric and Formula

| Metric | Formula | Meaning/use |
|---|---|---|
| Precision@K | relevant top-K / K | purity |
| Recall@K | relevant top-K / total relevant | coverage |
| F1@K | `2PR/(P+R)` | balance |
| Hit@K | indicator(any relevant in top-K) | question success |
| RR/MRR | `1/rank(first relevant)`; average across questions | early evidence |
| AP/MAP | mean precision at relevant ranks; mean across queries | multiple relevant ranking |
| DCG@K | implementation `sum(rel_i/log2(i+1))` | discounted gain |
| nDCG@K | `DCG/IDCG` | normalized ranking |
| ROC-AUC | area over TPR/FPR thresholds | score separation |
| PR-AUC | area over precision/recall | positive-class quality |
| Exact match | normalized answer equals reference | strict generation match |
| Token F1 | overlap precision/recall harmonic mean | partial lexical match |
| Citation presence | citation syntax present | formatting |
| Citation precision | relevant cited sources / cited sources | source selection |
| Claim accuracy | supported claims / evaluated claims | evidence support |
| Latency P50/P95 | 50th/95th percentile | typical/tail response time |

Good/bad values are task-dependent; higher is generally better for quality metrics and lower for latency/resources. ROC-AUC and PR-AUC differ on imbalanced retrieval because PR focuses on positive retrieval behavior.

## Part 17 - Classification and Curves

TP is a relevant item correctly retrieved, FP an irrelevant item retrieved, FN a relevant item missed, and TN a non-relevant item excluded. ROC plots TPR against FPR; ROC-AUC summarizes ranking separation. Precision-recall plots precision against recall; PR-AUC is usually more informative when relevant chunks are rare. The project implements ROC/PR-AUC when candidate scores and labels are available; it does not turn the entire RAG system into a binary classifier.

## Part 18 - Generation Metrics

Implemented generation measures include exact match, token overlap F1, ROUGE-L, correctness/relevance fields, faithfulness/grounding fields and abstention behavior. Scores depend on references and evaluator heuristics. An LLM-as-judge is not verified as the only evaluator; evaluator bias and threshold assumptions must be reported.

## Part 19 - Citation Metrics

Citation presence asks whether an answer cites anything. Citation precision asks whether cited sources are relevant. Claim accuracy asks whether claims are supported by the cited evidence. Citation completeness asks whether required sources/claims are covered. These are different dimensions and must not be collapsed into one “citation accuracy” number.

## Part 20 - Performance Metrics

```text
request -> preprocessing -> retrieval -> fusion/dedupe -> reranking
        -> context construction -> generation -> total latency
```

The live runner records stage-wise latency fields when returned by the backend and computes percentiles. The real Ollama report recorded total P50 25,287.75 ms and P95 38,258.91 ms. Self-test P50/P95 were 61/77 ms and are synthetic. P95 is important because it exposes the slow tail.

## Part 21 - Resource Metrics

The evaluator records CPU, RAM, GPU utilization, VRAM samples, Chroma size and sample count. The real Ollama report recorded peak VRAM 3,844 MB and peak RAM 15.37 GB. Model load time and throughput are not consistently established as independent production measures and should be labelled **REQUIRES VERIFICATION**.

## Part 22 - Testing

Current verified results: `pytest` 82 passed; Python `compileall` passed; frontend `npm.cmd run build` passed; evaluation self-test passed. Python tests cover metric/security/unit behavior. Frontend build proves compilation/bundling, not browser E2E correctness. There is no verified full production load test.

## Part 23 - Self-Test

The self-test creates synthetic QA items, exercises retrieval/metric/report paths and simulates parts of generation. It proves plumbing, not real-world accuracy, OCR robustness, audio transcription quality, privacy, scalability or causal ablation effects. OCR/audio are `NOT RUN` in the self-test.

## Part 24 - Real Dataset Evaluation

The live dataset contains 250 questions in the verified reports; one real report evaluated 226 retrieval queries and 250 answers. The report includes text, image, tabular, OCR, audio and cross-modal breakdowns. Ground truth is dataset-defined expected evidence/answers. Exact public dataset suitability is limited because the current corpus contains local/private-looking material and must be sanitized before GitHub release.

## Part 25 - Ablation Studies

An ablation removes or changes one component while holding other factors fixed. The runner exposes ablation output, but several configurations are simulated by scaling/truncating existing results rather than rerunning the live pipeline with components disabled. Therefore ablation findings are **PARTIALLY IMPLEMENTED** and exploratory. A valid future table should compare configuration, retrieval, generation, latency and resources under identical questions/corpus.

## Part 26 - Ollama vs Groq

| Feature | Ollama | Groq |
|---|---|---|
| Execution | local | cloud API |
| Internet | not required after model availability | required |
| Privacy | local by default | prompt leaves local environment |
| Model | qwen3:4b | openai/gpt-oss-120b |
| Hardware | laptop CPU/GPU/RAM | provider infrastructure |
| Cost | local electricity/storage | API/provider terms |
| Best use | privacy/offline/development | larger-model comparison/latency |

The real reports show the same retrieval values because retrieval is upstream of provider choice, while generation/citation values differ. This is a provider comparison, not proof that one universally dominates.

## Part 27 - Model Comparisons

Actually reported: qwen3:4b local and openai/gpt-oss-120b through Groq. Llama, Mistral, Gemma, Qwen 8B, GPT-4 and other alternatives are discussion-only unless a separate report verifies them. Larger models may improve reasoning but require more memory/cost; smaller models improve deployability. Exact parameter comparisons require pinned model metadata and are not guessed here.

## Part 28 - Hardware Analysis

The environment report identifies Windows 10, Python 3.11.9, Intel CPU, NVIDIA RTX 3050 Laptop GPU, CUDA 12.1 and CUDA-enabled PyTorch. Four GB-class VRAM cannot practically hold a full 70B/120B model with useful runtime headroom. Quantization and CPU offload reduce memory pressure but increase latency and do not remove RAM/bandwidth limits. Groq's 120B model is not running on the laptop GPU.

## Part 29 - Dependency Analysis

| Library | Version | Purpose |
|---|---:|---|
| FastAPI | 0.115.6 | API framework |
| Uvicorn | 0.34.0 | ASGI server |
| PyMuPDF | 1.25.1 | PDF extraction |
| python-docx | 1.1.2 | DOCX extraction |
| sentence-transformers | 3.3.1 | embeddings/reranking |
| transformers | 4.47.1 | BLIP/model stack |
| PaddleOCR | 3.7.0 | OCR |
| pytesseract | 0.3.13 | OCR fallback |
| faster-whisper | 1.1.0 | ASR |
| Pillow | 11.0.0 | image handling |
| ChromaDB | unpinned | vector storage |
| cryptography | >=42.0.0 | key protection |
| redis | 5.0.8 | optional cache |
| React/React DOM | 18.3.1 | frontend |
| Vite | 5.4.11 | frontend build/dev server |
| TypeScript | 5.6.3 | frontend typing |
| Tailwind CSS | 3.4.15 | frontend styling |
| Playwright | 1.63.0 | browser test tooling |

## Part 30 - Version Matrix

Python 3.11.9, FastAPI 0.115.6, PyTorch/CUDA runtime from environment report with CUDA 12.1, Transformers 4.47.1, Sentence Transformers 3.3.1, ChromaDB **NOT VERIFIED/PINNED**, React 18.3.1, Vite 5.4.11, TypeScript 5.6.3, Tailwind 3.4.15, Ollama qwen3:4b, Groq openai/gpt-oss-120b. Exact PyTorch package version and model revision are **REQUIRES VERIFICATION**.

## Part 31 - API and Backend Documentation

Verified endpoint families include health (`/api/health`, `/health/live`, `/health/ready`, `/health/dependencies`), auth (`/api/auth/*`), sessions (`/api/sessions*`), ingestion (`/api/ingest`, `/api/ingest/async`, status), files, query (`/api/query`, `/api/query/stream`, image/audio), sources/media, providers/LLM activation, metrics and reset. Inputs are bearer-token JSON or multipart depending on route; outputs are JSON or SSE. Exact Pydantic field-by-field schemas are source-defined and should be exported from route models before publishing a formal OpenAPI appendix. Authentication, error handling, CORS and rate-limit behavior are implemented/configured; auth semantics must be tested per deployment.

## Part 32 - Frontend Documentation

The React frontend includes authentication/login, header, sidebar/session controls, library/file upload, chat composer/panel, source panel, answer rendering, provider panel, scope panel, media/lightbox and toasts. The central API client attaches bearer tokens, handles 401 by clearing auth, calls query/upload/source/provider routes and supports streaming. Build passes. Exact screen-by-screen browser behavior requires running the frontend with a backend and is **REQUIRES VERIFICATION**.

## Part 33 - Database and Storage

Chroma stores persistent dense vectors/metadata. SQLite FTS5 stores lexical text and metadata. Filesystem storage holds uploads, extracted media, sessions, users, audit logs, provider-key material and generated runtime state. Evaluation reports store metrics/results. Chroma/SQLite/runtime files are rebuildable or sensitive and should not be committed.

## Part 34 - End-to-End Example

Question: “What was the invoice amount on page 2?”

1. Frontend sends query/session token.
2. Backend scopes search by user/session.
3. Query becomes a MiniLM vector and FTS5 terms.
4. Chroma returns dense page chunks; FTS5 returns BM25 invoice hits.
5. RRF merges and deduplicates page targets.
6. CrossEncoder reranks query/passages.
7. Context builder labels the page hit `[1]` and stays within budget.
8. Prompt asks the provider to answer only from context and cite `[1]`.
9. Answer cleanup preserves only valid citations.
10. Frontend renders amount and source preview.

Failure points include missing OCR, parser errors, no relevant page, provider timeout, invalid token or insufficient model memory. Exact per-stage latency depends on the live report.

## Part 35 - Error Handling

Invalid signatures/extensions are rejected; parser/OCR/ASR failures use fallbacks where available; embedding/vector/LLM/API failures are logged/returned through API errors or provider fallback; missing evidence triggers abstention; timeouts and missing models require runtime configuration checks. Malformed provider output is cleaned or replaced by a source snippet fallback. Exact HTTP status mapping should be verified from each route handler.

## Part 36 - Security

Secrets use environment variables and encrypted/local key material. Bearer auth, CORS, upload limits, rate/security controls and prompt injection instructions exist. Remaining concerns: malicious files, parser isolation, local-storage tokens, cloud privacy, admin/reset protection, corpus exposure and secret history. Keep `.env`, provider keys, users, sessions, audit data, databases and private corpus outside Git.

## Part 37 - Limitations

Current limitations: no TXT/Markdown ingestion, fragile PDF table helper, CPU OCR loader despite GPU-related config, approximate word-token budgeting, high local latency, partial ablations, private corpus, model/version drift, limited real OCR/audio isolation, no guarantee against hallucination and no proof of universal model superiority. Known bugs/fragile paths must be tracked in issue form; the table helper is the clearest source-level defect identified during audit.

## Part 38 - Future Scope

Already implemented: multimodal ingestion paths, dense/lexical retrieval, RRF, reranking, provider switching, citations and evaluation reports. Proposed: sanitize/publish a benchmark, true ablation reruns, fix table extraction, add TXT/Markdown, exact tokenizer budgeting, stronger OCR/ASR tests, streaming/caching, cross-modal reasoning, model pinning, parser sandboxing, deployment/load tests and calibrated confidence.

## Part 39 - Project Defence Preparation

Teacher 1 should receive the 30-second opening and architecture. Teacher 2 should receive embeddings, Transformer, CLIP/Whisper/LLM roles and model tradeoffs. Teacher 3 should receive dense/sparse/BM25/RRF/reranking. Teacher 4 should receive FastAPI/React/API/testing/security. Teacher 5 should receive metrics, benchmark design, latency/resource data and limitations. The [VIVA_DEFENCE_PACK.md](./VIVA_DEFENCE_PACK.md) contains the question bank; the answer format should be rehearsed as short answer -> project evidence -> limitation -> follow-up.

## Part 40 - Viva Question Bank

The defence pack contains 50 basic, 50 intermediate, 50 advanced, 30 trick and 30 follow-up prompts. For full compliance, each answer should be recorded in the following five-field form:

```text
Question:
Ideal Answer:
Short Answer:
Detailed Answer:
Possible Follow-up:
Important Point:
```

The current concise rows supply the answer substance, but the five labels are now the required review format for expansion of any row. Project-specific answer content must use only verified facts in this document.

## Part 41 - Why Did You Use This?

FastAPI: typed Python API suitable for this backend. React/Vite: component UI and fast build. Python: ecosystem for document/ML tooling. Sentence Transformers: efficient embeddings/reranking. MiniLM: compact 384D retrieval. Chroma: vector persistence/search. SQLite FTS5: exact lexical/BM25 retrieval. Hybrid/RRF: combine complementary rankers without score calibration. CrossEncoder: improve candidate order. CLIP: image/text alignment. OCR: extract visual text. Whisper: timestamped ASR. Ollama: local privacy/offline path. Groq: cloud large-model comparison. Qwen: laptop-friendly local model. GPT-OSS: configured large cloud model. No fine-tuning: changing knowledge is handled by retrieval and prompt context.

## Part 42 - What If Questions

Large document: chunk and index incrementally. OCR fails: fallback/error record and inspect source. Irrelevant retrieval: inspect BM25/dense/RRF/reranker and increase labelled evaluation. No relevant evidence: abstain. Hallucination: strengthen evidence/prompt/evaluation and do not claim elimination. API down/key expired: health/error/fallback and rotate credentials. GPU insufficient: CPU/quantization/smaller model or cloud provider. Contradiction: surface both cited sources and require date/authority policy. Duplicate information: deduplicate by citation target. Lower-ranked correct chunk: improve chunking/reranking/K and evaluate. Provider replacement: preserve retrieval contract and rerun benchmarks. Bigger model: compare quality, latency, cost and privacy rather than assuming improvement.

## Part 43 - Rapid Revision Sheet

**30 seconds:** multimodal ingestion -> hybrid retrieval -> RRF/rerank -> cited provider answer.  
**1 minute:** PDF/DOCX/image/audio become text/vectors; MiniLM/CLIP, Chroma/FTS5, RRF/CrossEncoder, strict prompt, Ollama/Groq.  
**3 minutes:** explain evidence flow, metrics, provider tradeoff and limitations.  
**Models:** MiniLM, CLIP, BLIP, PaddleOCR/Tesseract, Whisper, CrossEncoder, Qwen, GPT-OSS.  
**Metrics:** Precision, Recall, F1, Hit, MRR, MAP, nDCG, ROC/PR-AUC, correctness, faithfulness, citations, P50/P95.  
**Main results:** real reports have 250 questions/0 errors; Ollama P@5 0.3319, Hit@5 0.8407, MRR 0.7145, P95 38.26 seconds.  
**Limitations:** table path, private corpus, partial ablations, no TXT/Markdown, latency.  
**Twenty essential questions:** What is RAG? Why multimodal? What is an embedding? Why hybrid? What is BM25? What is RRF? Why rerank? What is grounding? Why citations? What is Precision@K? Recall@K? MRR? nDCG? P95? Why Ollama? Why Groq? Why not fine-tuning? What does self-test prove? What is the biggest limitation? What would you improve?

## Part 44 - Ten-Minute Presentation Script

**Slide 1 - Title (20s):** “My project is a multimodal Retrieval-Augmented Generation system for grounded document question answering.”

**Slide 2 - Problem (35s):** “Keyword search misses paraphrases and does not naturally handle image or audio evidence. Manual inspection is slow and generated answers without sources are difficult to trust.”

**Slide 3 - Motivation (30s):** “RAG allows the system to retrieve current evidence at query time. Multimodal preprocessing lets evidence from documents, images and audio participate in one workflow.”

**Slide 4 - Objectives (30s):** “The objectives are ingestion, evidence retrieval, cited generation, provider switching and measurable evaluation.”

**Slide 5 - Existing System (30s):** “A text-only keyword system is exact but brittle for paraphrases and media. A standalone LLM has no automatic access to uploaded files.”

**Slide 6 - Proposed System (40s):** “The proposed system extracts text, OCR, captions and transcripts, creates vectors, stores dense and lexical indexes, fuses candidates, reranks them and generates a constrained answer.”

**Slide 7 - Architecture (45s):** “The frontend calls FastAPI. Ingestion creates records. Chroma handles vector search and SQLite FTS5 handles BM25. RRF and a CrossEncoder prepare evidence for Ollama or Groq.”

**Slide 8 - Multimodal Pipeline (40s):** “PDF and DOCX use parsers, images use OCR/BLIP/CLIP, and audio uses Whisper. Page, timestamp and modality metadata preserve citation traceability.”

**Slide 9 - Retrieval (45s):** “Dense retrieval captures meaning; BM25 captures exact terms. RRF combines ranks using one over k plus rank. The CrossEncoder then scores query-passage pairs.”

**Slide 10 - Generation (40s):** “The prompt says to use only retrieved context, cite factual claims and abstain with a fixed sentence when evidence is missing. Retrieved text is treated as untrusted data.”

**Slide 11 - Evaluation (40s):** “The system includes retrieval, generation, citation, latency, resource, modality, self-test and ablation runners. The self-test is synthetic; live reports use 250 questions.”

**Slide 12 - Results (45s):** “The real Ollama report recorded Precision@5 0.3319, Hit@5 0.8407, MRR 0.7145 and P95 latency 38.26 seconds. The Groq report used the same retrieval setup and a different generation provider.”

**Slide 13 - Comparison (35s):** “Ollama provides local privacy and offline control but is constrained by the laptop. Groq provides cloud access to a much larger configured model but introduces internet, cost and privacy tradeoffs.”

**Slide 14 - Limitations (35s):** “The current limitations are table extraction fragility, high local latency, private corpus dependence, approximate ablations, no TXT/Markdown path and no guarantee against hallucination.”

**Slide 15 - Future Scope (30s):** “Future work is a sanitized benchmark, true ablation reruns, exact token budgeting, stronger multimodal reasoning, parser isolation and deployment testing.”

**Slide 16 - Conclusion (25s):** “The project demonstrates a modular, measured and evidence-aware RAG workflow. Its strongest contribution is the complete path from mixed media to traceable answers, with limitations reported honestly.”

## Part 45 - Defence Cheat Sheet

| Topic | One-line answer |
|---|---|
| RAG | Retrieve evidence before generation. |
| Multimodal RAG | Retrieve evidence derived from multiple modalities. |
| Embedding | Learned numeric representation for similarity. |
| Vector DB | Stores/searches vectors and metadata. |
| Semantic search | Meaning-based retrieval. |
| BM25 | Lexical term-ranking algorithm. |
| RRF | Rank-list fusion using reciprocal rank. |
| Reranking | Reordering candidates with a stronger relevance model. |
| CrossEncoder | Jointly scores query and passage. |
| Grounding | Supporting output with supplied evidence. |
| Precision@K | Relevant top-K divided by K. |
| Recall@K | Relevant top-K divided by total relevant. |
| MRR | Mean reciprocal rank of first relevant result. |
| nDCG | Normalized rank-discounted gain. |
| P95 | 95th-percentile latency. |
| Hallucination | Unsupported generated content. |
| Citation accuracy | Whether cited evidence supports claims. |

## Part 46 - Common Student Mistakes

Never say RAG equals fine-tuning, embeddings are encrypted text, Chroma stores the model, larger always means better, higher recall alone proves answer quality, citations guarantee truth, self-test proves real-world performance, or the LLM automatically knows uploaded documents. Correct answers distinguish retrieval, generation, evidence and evaluation.

## Part 47 - Technical Glossary

AI/ML/DL/NLP/LLM/GenAI: broad intelligent computation, learned pattern modelling, neural ML, language processing, token generator and generated content. RAG/multimodal: retrieved-context generation and multiple evidence modalities. Transformer/attention/token/tokenizer: architecture, learned token interaction, model unit and unitiser. Embedding/vector/vector space/cosine: learned numeric encoding, ordered numbers, geometry and angular similarity. Dense/sparse/BM25/FTS5/hybrid/RRF: vector retrieval, term retrieval, lexical engine, combined retrieval and rank fusion. Reranking/CrossEncoder/BiEncoder: second-stage scoring, joint scorer and independent encoders. Chunk/context/prompt/grounding/hallucination/citation: retrieval unit, supplied text, model input, evidence support, unsupported output and source pointer. Inference/fine-tuning/pretraining/quantization: execution, task weight update, initial learning and reduced-precision/compressed inference. Parameters/dimensions/context window/temperature/Top-K/Top-P: learned weights, vector size, maximum input, randomness and selection controls. Latency/throughput/P50/P95: time, requests per time, median and tail percentile. Precision/Recall/F1/MRR/MAP/nDCG/ROC-AUC/PR-AUC/TP/TN/FP/FN: retrieval/evaluation quantities defined in Part 16/17. OCR/ASR/CLIP/Whisper/API/REST/JSON/FastAPI/React/Vite/Docker/Git/GitHub: image text, speech text, image-text encoder, ASR model, software contract, HTTP style, data format, backend framework, UI framework, frontend tool, packaging, version control and repository host. Their project roles are documented in Parts 5, 6, 29, 31 and 32.

## Part 48 - Reproducibility Guide

1. Clone or initialize Git after secret review.
2. Create Python 3.11 environment.
3. Install backend requirements and frontend lockfile dependencies.
4. Copy `.env.example` to `.env` and add secrets locally.
5. Start Ollama and make qwen3:4b available for local mode.
6. Start backend/frontend using the selected README/deployment script.
7. Create session and ingest supported files.
8. Query and inspect citations.
9. Run self-test using the verified CLI.
10. Run live evaluation only with a running API, prepared corpus and credentials.

Exact deployment start commands vary across historical deployment files and require target-specific verification; do not merge conflicting README commands without testing.

## Part 49 - Troubleshooting Guide

Python/dependencies: activate the project environment and install the manifest. CUDA/GPU: verify PyTorch CUDA and reduce model/load settings if VRAM is insufficient. Ollama: verify service/model availability. Groq: verify key without printing it. Backend/frontend/CORS: check health endpoint, port and allowed origin. Vector database: rebuild local Chroma/FTS5 from sanitized input. OCR/audio: inspect fallback and model availability. Evaluation: run self-test first, then verify base URL/session/dataset. Tests: run pytest, compileall and frontend build. Verification commands are the three evaluation commands in Part 15 plus the test commands in Part 22.

## Part 50 - Final Project Scorecard

Architecture Good; Code quality Good with fragile table path; RAG design Good; Retrieval Good; Generation Good; Multimodality Good but mediated; Evaluation Needs Improvement because ablations/self-test need careful interpretation; Testing Good; Documentation Good after this expansion; Security Needs Improvement for public-release process; Reproducibility Needs Improvement because local state/unpinned Chroma/config drift; Performance Needs Improvement due local tail latency; Innovation Good; Scalability Needs Improvement due local Chroma/SQLite/filesystem assumptions.

## Part 51 - Verified Facts vs Assumptions

**Verified:** models/config names, 384/512 vector dimensions, Chroma/FTS5/BM25/RRF/CrossEncoder paths, prompt rules, API families, dependencies, 82 tests, compile/build/self-test, real 250-question reports and observed hardware/resource values.

**Partially verified:** exact route schemas, production startup commands, provider failover under outage, table reliability, model revisions/quantization, Chroma runtime version, full browser workflow and causal ablations.

**Not implemented/future:** TXT/Markdown ingestion, default-on HyDE/query rewrite/multi-hop/ColBERT, direct final-LLM audio/image input, fine-tuning and universal hallucination elimination.

## Part 52 - Final Document Structure

This document is the expanded source-of-truth structure. The previous [PROJECT_KNOWLEDGE_BASE.md](./PROJECT_KNOWLEDGE_BASE.md) remains the concise audit; this file is the complete numbered companion. The [VIVA_DEFENCE_PACK.md](./VIVA_DEFENCE_PACK.md) remains the rehearsal companion.

## Part 53 - Writing Style Compliance

Every project claim in this document is tied to code/config/dependency/test/report evidence or marked as general knowledge/uncertain. Unsupported components are explicitly labelled rather than described as active features. Explanations connect general RAG concepts to this implementation.

## Part 54 - Accuracy Rule

If source code, runtime configuration, generated report and old documentation disagree, current runtime/source evidence wins. Model names, metrics and results in this document are limited to verified reports. Unknown parameter counts, revisions and exact schemas remain `REQUIRES VERIFICATION`.

## Part 55 - Final Outputs and Release Checklist

Outputs are: corrected `.gitignore`; commit/no-commit lists; secret-risk audit; architecture; technical documentation; model/library/version matrix; evaluation/formulas; testing; provider comparison; glossary; viva bank; presentation script; rapid revision sheet; verified-facts matrix. Before GitHub release:

1. Initialize Git in the intended repository.
2. Review `git status --ignored`.
3. Confirm no `.env`, keys, runtime storage, private corpus, model cache or generated raw report is staged.
4. Add sanitized public sample data only.
5. Run tests/build/self-test again.
6. Verify README commands on a clean environment.
7. Rotate any credential that may have appeared in historical files.
8. Reconcile exact OpenAPI schemas and model revisions.

