# Viva Defence Pack

For the complete 55-part project documentation, use [COMPLETE_PROJECT_DOCUMENTATION.md](./COMPLETE_PROJECT_DOCUMENTATION.md). This file is the rehearsal companion.
The literal five-field matrix for all 210 prompts is [VIVA_FULL_ANSWER_MATRIX.md](./VIVA_FULL_ANSWER_MATRIX.md).

## Required five-field answer format

For every question, rehearse the response in this order. The compact answer tables below provide the project-specific substance; expand each row into these five fields during preparation:

```text
Question: the examiner's exact wording
Ideal Answer: technically complete answer tied to this project
Short Answer: one or two sentences for a time-limited response
Detailed Answer: mechanism, formula, code/config evidence and tradeoff
Possible Follow-up: the next question an examiner is likely to ask
Important Point: one fact or limitation that must not be omitted
```

Do not fill a field with an assumption. Use `NOT IMPLEMENTED` or `REQUIRES VERIFICATION` when the repository does not prove it.

Use the answer pattern for every question: **short answer**, then **project-specific detail**, then **limitation**, then the **follow-up point**. Never claim a component is implemented unless it appears in the verified matrix in the main knowledge base.

## 30-second opening answer

This project is a multimodal RAG application. It ingests PDF, DOC/DOCX, images and audio, converts evidence into text and vectors, searches with both Chroma dense retrieval and SQLite FTS5 BM25, fuses results with RRF, reranks candidates, and asks either local Ollama or cloud Groq to generate a cited answer. When evidence is missing, the prompt requires abstention.

## Basic questions

| # | Question | Short/ideal answer | Project detail and follow-up |
|---:|---|---|---|
| 1 | What is your project? | A multimodal grounded document QA system. | It combines ingestion, retrieval, reranking and cited generation. Follow-up: explain one query end to end. |
| 2 | What problem does it solve? | Finding and answering questions over mixed personal documents and media. | It reduces manual reading and supports evidence-backed responses. |
| 3 | What is AI? | The study of systems that perform tasks associated with intelligence. | RAG is an AI application built from ML models and software components. |
| 4 | What is ML? | Learning patterns from data rather than writing every rule manually. | The embedding and language models are pretrained ML models used at inference time. |
| 5 | What is deep learning? | ML using multilayer neural networks. | Transformers, CLIP, BLIP and Whisper are deep-learning models. |
| 6 | What is NLP? | Processing and understanding human language computationally. | Text extraction, embeddings, FTS5 queries and answer generation use NLP. |
| 7 | What is an LLM? | A model that predicts and generates token sequences. | Ollama qwen3:4b and Groq openai/gpt-oss-120b are configured generation providers. |
| 8 | What is RAG? | Retrieval-Augmented Generation: retrieve evidence before generation. | The prompt receives ranked chunks and requires numbered citations. |
| 9 | Why RAG? | It gives the generator current, task-specific evidence without retraining. | The system can ingest new files and answer from them at query time. |
| 10 | What is multimodal RAG? | RAG over more than one input modality. | Images use OCR, captions and CLIP; audio uses Whisper transcripts. |
| 11 | What is an embedding? | A learned numeric representation. | MiniLM creates 384D text vectors; CLIP creates 512D image vectors. |
| 12 | What is a vector? | An ordered list of numbers. | Chroma compares normalized vectors using cosine distance. |
| 13 | What is semantic search? | Search based on meaning rather than exact words. | A paraphrase may retrieve a chunk even when the words differ. |
| 14 | What is keyword search? | Search based on terms appearing in text. | SQLite FTS5 supplies the lexical BM25 branch. |
| 15 | What is BM25? | A term-frequency and inverse-document-frequency ranking function. | The project uses SQLite FTS5 `bm25`, not the removed `rank_bm25` package. |
| 16 | What is a vector database? | Storage and search for vectors with metadata. | Chroma stores `rag_text` and `rag_image`; it does not store the LLM. |
| 17 | What is chunking? | Splitting long content into retrievable units. | The semantic target is 220 words, minimum 80, with a 40-word fallback overlap. |
| 18 | What is Top-K? | The first K ranked candidates. | Evaluation commonly uses K=5; runtime default top_k is 10. |
| 19 | What is a prompt? | The input instructions and data given to a model. | The system prompt defines grounding, citation and abstention rules. |
| 20 | What is a token? | A tokenizer unit used by a language model. | Context budgeting uses a word proxy, so it is approximate. |
| 21 | What is hallucination? | An unsupported or fabricated model output. | Retrieval and strict prompts reduce risk; they do not eliminate it. |
| 22 | What is grounding? | Tying an answer to supplied evidence. | Answers are expected to cite returned source labels. |
| 23 | What is a citation? | A pointer from an answer claim to evidence. | The format is `[number]`, mapped to file/page, timestamp or image source. |
| 24 | What is OCR? | Optical Character Recognition of text in images. | PaddleOCR is primary and Tesseract is a fallback. |
| 25 | What is ASR? | Automatic Speech Recognition. | faster-whisper creates timestamped audio transcript chunks. |
| 26 | What is inference? | Running a trained model to produce an output. | This project performs inference; it does not train its models. |
| 27 | What is fine-tuning? | Updating pretrained weights on task data. | **NOT IMPLEMENTED**; RAG was chosen instead for changing document content. |
| 28 | What is temperature? | A generation randomness control. | Runtime Ollama temperature is configured at 0.0; cloud config uses 0.1. |
| 29 | What is latency? | Time taken to produce a result. | The real Ollama report records retrieval/generation stage and total percentiles. |
| 30 | What is a test? | An executable check of expected behavior. | Current verified result is 82 Python tests passed, plus compile/build/self-test. |
| 31 | What is a Transformer? | A neural architecture based on attention. | The project consumes Transformer-based pretrained models rather than training one. |
| 32 | What is attention? | A learned weighting of token interactions. | It helps models focus on relevant context, but it is not the same as retrieval. |
| 33 | What is a foundation model? | A broadly pretrained model adapted to many tasks. | The project uses foundation models as fixed inference components. |
| 34 | What is an API? | A contract for software-to-software communication. | React calls FastAPI endpoints using JSON or multipart requests. |
| 35 | What is JSON? | A structured text data format. | It carries query, session, provider and response data. |
| 36 | What is REST? | A resource-oriented HTTP API style. | The backend exposes GET, POST, PATCH and DELETE routes. |
| 37 | What is a database index? | A structure that speeds up lookup. | Chroma and FTS5 are different index types for different signals. |
| 38 | What is a cache? | Stored reusable computation or data. | Redis is optional; local indexes are persistent state, not merely cache. |
| 39 | What is a session? | A scoped interaction/context identifier. | Sessions scope uploaded files, queries and source access. |
| 40 | What is authentication? | Verifying who a caller is. | The API uses bearer tokens and auth routes. |
| 41 | What is authorization? | Deciding what an authenticated user may do. | User/session scoping and admin/provider routes are separate concerns. |
| 42 | What is CORS? | A browser cross-origin access policy. | Configuration defaults to local origins. |
| 43 | What is a dependency? | External code required by a project. | Versions are listed in backend requirements and frontend package files. |
| 44 | What is a virtual environment? | An isolated Python package environment. | `.venv/` is local machine state and must not be committed. |
| 45 | What is a build? | Transforming source into runnable output. | Vite creates frontend production assets. |
| 46 | What is a unit test? | A test of a small isolated behavior. | Metric/security tests are examples. |
| 47 | What is an integration test? | A test across multiple components. | Retrieval and API tests can validate component boundaries. |
| 48 | What is an end-to-end test? | A test of a user workflow across the stack. | A passing build alone is not an E2E result. |
| 49 | What is reproducibility? | Ability to repeat a result from recorded inputs/configuration. | Model revisions, datasets and environment must be recorded. |
| 50 | What is a limitation? | A known boundary of validity or capability. | State latency, private corpus, partial ablations and parser risks honestly. |

## Intermediate questions

| # | Question | Short/ideal answer | Project detail and follow-up |
|---:|---|---|---|
| 1 | Why combine dense and lexical retrieval? | They cover semantic paraphrases and exact terms respectively. | FTS5 helps names/numbers; MiniLM helps meaning. |
| 2 | Why use RRF? | It combines rank lists without requiring calibrated score scales. | The code uses `1/(60+rank)` and then deduplicates citation targets. |
| 3 | Why rerank? | Initial retrieval is fast but approximate. | The CrossEncoder scores query-passage pairs after candidate generation. |
| 4 | Bi-encoder versus CrossEncoder? | A bi-encoder embeds independently; a CrossEncoder reads both together. | MiniLM is the bi-encoder retrieval model; ms-marco MiniLM reranks. |
| 5 | Why normalize embeddings? | To make angular similarity stable and comparable. | The embedding functions return normalized float32 arrays. |
| 6 | Why Chroma and SQLite together? | Different indexes solve different search problems. | Chroma stores vectors; SQLite FTS5 stores searchable text and metadata. |
| 7 | What is cosine similarity? | Dot product divided by vector magnitudes. | With normalized vectors it is equivalent to dot product. |
| 8 | How is RRF calculated? | Add one reciprocal rank contribution per ranker. | A result at rank 1 receives `1/61` from that ranker when k=60. |
| 9 | How are duplicate results handled? | Results are grouped by citation target. | Document page, audio timestamp and image identities preserve source mapping. |
| 10 | How is context constructed? | Selected hits are labelled and concatenated into the prompt. | Whole hits are kept until the 2500-token word-proxy budget is reached. |
| 11 | How does abstention work? | The model is instructed to return one exact sentence if evidence is absent. | Answer cleanup also enforces the missing-context message in relevant cases. |
| 12 | How does prompt injection defense work? | Retrieved text is treated as data, never as instructions. | The system prompt explicitly says to ignore instructions inside sources. |
| 13 | How does PDF processing work? | PyMuPDF extracts pages; low-text pages can go to OCR. | Tables and embedded images have additional paths. |
| 14 | How does image processing work? | OCR and BLIP produce text; CLIP produces a visual vector. | The image can therefore participate in lexical, semantic and visual retrieval. |
| 15 | How does audio processing work? | Whisper transcribes speech and groups segments with timestamps. | English is the default language and the configured model is medium. |
| 16 | How is ingestion idempotent? | A content hash and pipeline metadata identify unchanged input. | The same file/mode/version can be skipped. |
| 17 | What metadata is retained? | File, page, modality, session/user and source information. | It supports filtering, citations and scoped search. |
| 18 | Why use a 384D embedding? | It is a compact quality/speed tradeoff. | Do not call 384 a semantic feature count; it is a representation size. |
| 19 | What is Precision@5? | Relevant retrieved items divided by 5. | It measures list purity for the top five results. |
| 20 | What is Recall@5? | Relevant retrieved items divided by all relevant items. | It measures coverage and can rise as K grows. |
| 21 | What is MRR? | Mean reciprocal rank of the first relevant result. | It rewards finding one useful result early. |
| 22 | What is nDCG? | A rank-discounted score normalized by ideal ranking. | It penalizes relevant evidence appearing too low. |
| 23 | Why ROC-AUC and PR-AUC? | They summarize score ranking under different class-balance views. | PR-AUC is often more revealing when relevant candidates are rare. |
| 24 | What is P95 latency? | The value below which 95 percent of requests finish. | It exposes slow-tail behavior better than only the average. |
| 25 | Why compare Ollama and Groq? | To compare local privacy/control with cloud quality/latency. | Retrieval can remain constant while generation provider changes. |
| 26 | Why not a 120B local model? | Laptop VRAM/RAM and bandwidth are insufficient for practical inference. | The 120B model is used through Groq, not loaded on the RTX 3050. |
| 27 | Why FastAPI? | It provides typed, asynchronous-friendly Python APIs quickly. | It exposes ingestion, query, auth, health and provider routes. |
| 28 | Why React/Vite? | Component UI plus a fast frontend development/build tool. | The UI has login, sessions, upload, chat, sources and provider controls. |
| 29 | What does the self-test prove? | That evaluation plumbing and metrics run on synthetic items. | It does not prove real-world accuracy or OCR/audio quality. |
| 30 | What is an ablation? | Removing one component to measure its contribution. | Here several ablations are approximated, so causal claims are not justified. |
| 31 | How are source citations mapped? | Retrieval metadata is converted into numbered source labels. | The answer cleanup retains only citations used in the final answer. |
| 32 | Why keep page and timestamp metadata? | It makes evidence inspectable. | A page or audio time is more useful than a filename alone. |
| 33 | What is lexical tokenization? | Splitting text into searchable terms. | FTS5 uses a unicode61 tokenizer and safely builds OR terms. |
| 34 | Why quote FTS5 terms? | To reduce query syntax surprises. | The implementation tokenizes words and quotes them before OR joining. |
| 35 | What is metadata filtering? | Restricting candidates by attributes. | Session, user, modality and sections can constrain retrieval. |
| 36 | Why use content hashes? | To detect identical file bytes. | It supports idempotent ingestion and avoids repeated work. |
| 37 | Why store pipeline version? | Parsing/indexing behavior can change over time. | A version mismatch can justify re-ingestion. |
| 38 | Why use fallback OCR? | One OCR engine can fail on a document. | Tesseract provides a fallback after PaddleOCR errors. |
| 39 | Why group audio segments? | Individual speech segments may be too short as evidence. | Approximately 12-second windows preserve timestamps while improving context. |
| 40 | Why caption images? | Captions make visual content available to text retrieval. | Caption text complements, rather than replaces, CLIP vectors. |
| 41 | Why use an image-query branch? | Some questions describe visual content rather than text. | CLIP text-to-image search is conditional for visual/image scopes. |
| 42 | What is a dense candidate? | A result from vector similarity search. | Chroma returns dense candidates before fusion. |
| 43 | What is a sparse candidate? | A result from term-based search. | FTS5 BM25 supplies sparse/lexical candidates. |
| 44 | Why not merge raw scores? | Dense distances and BM25 scores have different scales. | Rank fusion is more robust for this combination. |
| 45 | What is query scope? | The subset of indexed evidence searched. | The UI/backend can scope by session, user or modality. |
| 46 | Why is direct extraction used? | Some fields are easier to answer deterministically. | Patterns such as invoice numbers or amounts can bypass unnecessary generation. |
| 47 | Why clean reasoning markers? | Internal reasoning text should not leak into the answer. | The answer path finalizes/cleans provider output. |
| 48 | Why return a source snippet on provider failure? | It preserves some evidence when generation is unavailable. | This is a fallback, not a full generated answer. |
| 49 | What is a health endpoint for? | To expose service/dependency readiness. | The backend has live, ready and dependency health routes. |
| 50 | What is a provider router? | A component that selects a generation backend. | It allows local/cloud activation without changing retrieval code. |

## Advanced questions

| # | Question | Short/ideal answer | Project detail and follow-up |
|---:|---|---|---|
| 1 | Why can retrieval have high Hit@5 but modest Precision@5? | One relevant item may be found among several irrelevant items. | The real run shows Hit@5 0.8407 and Precision@5 0.3319. |
| 2 | Why did Ollama and Groq retrieval values match? | Retrieval is upstream of provider selection. | Same corpus/session/index means provider affects generation, not candidates. |
| 3 | What does MAP add beyond MRR? | MAP rewards multiple relevant items at their ranks, not only the first. | It is useful when a question has several supporting chunks. |
| 4 | Why does nDCG matter? | Position matters, and nDCG normalizes against the ideal order. | A relevant chunk at rank 1 is more useful than the same chunk at rank 10. |
| 5 | What is a false negative in retrieval? | A relevant document that was not retrieved. | It reduces Recall@K and can make a correct answer impossible. |
| 6 | Why can increasing K hurt generation? | More candidates can add noise and consume context budget. | Reranking and truncation are needed to control context quality. |
| 7 | Why can a CrossEncoder be too expensive? | It evaluates each query-candidate pair jointly. | It is applied after a smaller candidate set, batch 16. |
| 8 | What is score calibration? | Making scores from different systems comparable. | RRF avoids needing direct dense/BM25 score calibration. |
| 9 | Why is FTS5 useful for invoices or IDs? | Exact strings and rare terms are strong lexical signals. | Dense encoders may blur uncommon identifiers. |
| 10 | Why is semantic chunking useful? | It keeps related sentences together. | It embeds sentences and groups them by similarity and word limits. |
| 11 | What is the risk of word-proxy token budgeting? | Words and model tokens do not have a fixed one-to-one mapping. | The 2500 value is operationally approximate. |
| 12 | What is a grounded refusal? | A refusal caused by insufficient retrieved evidence. | The exact missing-context sentence is part of the prompt contract. |
| 13 | Why is citation presence insufficient? | A citation can exist but point to irrelevant evidence. | Evaluate presence, source precision and claim-level accuracy separately. |
| 14 | What is claim-level citation accuracy? | Whether claims are supported by cited evidence. | It is stricter than merely checking `[1]` syntax. |
| 15 | Why can cloud generation create privacy concerns? | User context leaves the local machine. | Provider choice must be explicit for sensitive documents. |
| 16 | What does normalized vector length do? | It removes magnitude as a source of similarity variation. | Direction carries the comparison signal for cosine search. |
| 17 | Why is PR-AUC sensitive to imbalance? | It focuses on precision and recall of positive items. | This is relevant when only a few chunks are relevant. |
| 18 | Why can ROC-AUC look good while answers are poor? | Ranking candidates is not the same as composing a correct answer. | Generation, grounding and citations need separate evaluation. |
| 19 | What is provider failover? | Switching after a retryable provider failure. | It is configured, but failover behavior should be verified under live outage tests. |
| 20 | What is multimodal alignment here? | Connecting image/audio-derived evidence to the same retrieval question. | Current alignment is through CLIP, OCR, captions and transcripts, not a single multimodal LLM. |
| 21 | Why is the current table path a risk? | A parser helper can reference `current_section` outside its arguments. | Treat table support as partial until a regression test fixes it. |
| 22 | Why is CPU OCR notable? | It increases latency and may limit throughput. | The PaddleOCR loader currently passes CPU even though configuration exposes a GPU option. |
| 23 | What is reproducibility risk from unpinned Chroma? | A future install can resolve a different implementation. | Pin runtime dependencies and record model revisions. |
| 24 | Why should local indexes not be committed? | They are machine-specific generated state and may contain private data. | Rebuild them from sanitized input during setup. |
| 25 | Why is the evaluation corpus a security issue? | Private documents can be exposed in a public repository. | Use synthetic/redacted samples and keep the current corpus ignored. |
| 26 | What is a fair provider comparison? | Hold corpus, questions, K and retrieval fixed, then compare generation outcomes. | Report external API variability and separate retrieval from generation metrics. |
| 27 | Why is self-test not a benchmark? | Synthetic examples are small and deliberately controlled. | Use the 250-question report for benchmark claims. |
| 28 | Why not fine-tune? | The problem is changing document knowledge, not a stable label mapping. | Fine-tuning could be future work but needs data and careful evaluation. |
| 29 | Why not train embeddings? | The project needs a strong pretrained baseline within its scope/hardware. | Domain training is future work after a larger labelled corpus exists. |
| 30 | What does the hardware report prove? | It records the environment and observed resource samples for that run. | It does not guarantee identical performance on another laptop. |
| 31 | How would you calibrate confidence? | Compare scores against labelled outcomes and fit a calibration method. | Current relevance normalization is not a validated probability. |
| 32 | How would you test retrieval drift? | Re-run a fixed labelled benchmark after model/index changes. | Compare metric deltas and dataset/model hashes. |
| 33 | Why can min-max normalization be unstable? | A single extreme result changes every scaled score. | Treat displayed relevance as a ranking aid, not probability. |
| 34 | What is data leakage in evaluation? | Test information influences indexing, prompts or labels improperly. | Keep evaluation documents/questions and system tuning separated. |
| 35 | Why use a fixed top K for comparison? | It controls the candidate budget. | Provider comparisons should keep K and corpus constant. |
| 36 | What is a recall ceiling? | The maximum answer quality limited by retrieved evidence. | A generator cannot recover evidence never retrieved. |
| 37 | What is context dilution? | More irrelevant context weakens useful signal. | It is a reason not to increase K blindly. |
| 38 | What is prompt budget pressure? | Context, instructions and answer tokens compete for model capacity. | The project limits retrieved context and provider prediction length. |
| 39 | Why use exact abstention wording? | It makes abstentions detectable and consistent. | The evaluator can measure abstention behavior. |
| 40 | What is a faithfulness warning? | A signal that output claims do not align with evidence. | Groq report records a warning rate; interpret it with evaluator assumptions. |
| 41 | Why can token-F1 be low for a correct answer? | Paraphrases have low lexical overlap. | Use it with relevance/faithfulness, not alone. |
| 42 | Why is answer correctness evaluator-dependent? | Reference answers and scoring rules define correctness. | Document the metric implementation and thresholds. |
| 43 | What makes an ablation valid? | Only one component changes while other conditions remain fixed. | Simulated scaling is not equivalent to a live component toggle. |
| 44 | What is a benchmark confounder? | Another changing factor that affects comparison. | Provider availability, corpus changes and model updates are confounders. |
| 45 | Why report resource metrics? | Quality without cost/latency is incomplete for deployment. | VRAM/RAM and P95 matter on an RTX 3050 laptop. |
| 46 | Why is 4B not automatically worse? | Suitability depends on latency, privacy, hardware and task. | A smaller local model can be the correct engineering tradeoff. |
| 47 | Why is 120B not automatically better? | Larger models cost more and can still lack retrieved evidence. | It may improve generation but does not repair retrieval misses. |
| 48 | What is a secure ingestion boundary? | A controlled parser/resource limit around untrusted files. | Future work should isolate parsers and scan uploads. |
| 49 | What is prompt injection through retrieval? | A source contains text attempting to control the model. | The prompt says retrieved text is untrusted data, but defense is layered. |
| 50 | What is the strongest research claim? | The system demonstrates a measured modular RAG pipeline. | Avoid claiming universal superiority or complete multimodal understanding. |

## Trick questions and safe answers

1. **Does RAG eliminate hallucination?** No. It supplies evidence and enforces a prompt policy, but the generator can still misread or overstate it.
2. **Is 384 the number of words the model understands?** No. It is the embedding vector dimension.
3. **Does Chroma contain qwen3:4b?** No. Chroma contains vectors and metadata; Ollama serves the LLM.
4. **Was GPT-4 tested?** Not verified in the reported runs. Provider hooks are not proof of a benchmark.
5. **Is every generated citation correct?** No. Citation presence, source precision and claim accuracy are different metrics.
6. **Does a high Recall@5 mean the answer is correct?** No. Retrieval coverage does not guarantee generation correctness.
7. **Is the self-test real-user evidence?** No. It is synthetic plumbing validation.
8. **Is audio directly understood by qwen3:4b?** The verified pipeline transcribes audio first; direct audio understanding is not claimed.
9. **Are tables fully reliable?** No. They are partially implemented and need parser regression coverage.
10. **Is Groq local?** No. It is a cloud API path.
11. **Can the RTX 3050 run GPT-OSS 120B?** Not as a practical full local model; the project uses Groq for that model.
12. **Is BM25 a neural model?** No. It is a lexical ranking function.
13. **Does a vector store replace a database?** It solves vector search; the project also uses SQLite and filesystem storage.
14. **Does RRF average similarity scores?** No. It combines rank positions.
15. **Can increasing K always improve quality?** No. It can increase recall while adding noise and latency.
16. **Does a cloud model prove the local model is bad?** No. It compares one deployment tradeoff under one evaluation setup.
17. **Does a passing build prove the UI works end to end?** No. It proves compilation/bundling.
18. **Are model parameter counts verified for every component?** No. Exact runtime metadata requires verification.
19. **Are ablations causal?** Not all. Several are approximated by the evaluation runner.
20. **Can a prompt alone guarantee security?** No. It is one defense layer; input validation, isolation and access control also matter.
21. **Is OCR always run?** No. It depends on modality, ingestion mode and extracted text quality.
22. **Does the system support Markdown ingestion?** The current supported extension set does not verify it; mark it not implemented.
23. **Does P95 mean the slowest request?** No. It is the 95th percentile, not the maximum.
24. **Is token F1 a factuality metric?** No. It measures overlap, not truth.
25. **Does a source citation prove a claim?** No. The cited passage must actually support the claim.
26. **Are API keys safe because they are encrypted in storage?** Encryption at rest does not justify committing key files or leaking runtime access.
27. **Does RAG require fine-tuning?** No. Retrieval and prompting work with pretrained models.
28. **Is CLIP OCR?** No. CLIP creates image/text embeddings; OCR extracts characters.
29. **Is Whisper an LLM for document QA?** No. It is an ASR model.
30. **Is the project a multimodal foundation model?** No. It is a multimodal retrieval pipeline composed of specialized models.

## Follow-up prompts to rehearse

1. Show the exact file where the prompt is defined.
2. Which model creates the query vector?
3. What happens if Chroma returns no result?
4. What happens if the API key is missing?
5. Where are page numbers stored?
6. Why can two documents with different words retrieve together?
7. What is the difference between MRR and MAP?
8. Why is P95 useful to a user?
9. Which tests prove the frontend compiles?
10. Which test proves the self-test path?
11. Which report contains the real Ollama result?
12. Which report contains the real Groq result?
13. What is not tested by the self-test?
14. How would you test OCR properly?
15. How would you fix table extraction?
16. How would you make the experiment reproducible?
17. What would you log for a failed query?
18. What data should never enter Git?
19. How would you prevent prompt injection from a PDF?
20. What happens when the user asks outside the corpus?
21. Why is the final answer allowed to abstain?
22. How does provider switching affect retrieval?
23. Why are images represented twice, as text and vectors?
24. Why are timestamps important for audio citations?
25. What does normalization change mathematically?
26. What is the cost of CrossEncoder reranking?
27. Why is SQLite FTS5 not the same as dense search?
28. What would a real ablation require?
29. Which configuration value differs between `.env.example` and evaluation config?
30. What is your most important current limitation?

## Defence closing sentence

The strongest claim I can defend is that the project implements a modular, evidence-aware multimodal RAG pipeline and has reproducible software/evaluation checks. I should not claim that it eliminates hallucination, fully understands every modality end to end, or proves causal component improvements without additional experiments.
