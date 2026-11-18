# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary users are enterprise analysts, technical researchers, legal/compliance investigators, and intelligence officers working in air-gapped, privacy-critical, or regulated environments. They handle sensitive or confidential documents, OCR screenshots, structured data tables, and recorded audio that cannot be leaked or transmitted to third-party cloud LLM APIs. Their core job is to ask questions across multi-source collections, receive synthesized answers, and immediately verify the exact supporting evidence in context.

## Product Purpose

Provide an enterprise-grade, privacy-first, fully offline multimodal RAG (Retrieval-Augmented Generation) workspace. The product exists to make local artificial intelligence trustworthy and verifiable for mission-critical operations without data egress. Success means an analyst can upload heterogeneous enterprise media (PDFs, Word docs, tables, screenshots, audio notes) and receive grounded answers with clickable, character-accurate citations and side-by-side evidence inspection within seconds.

## Positioning

100% on-premises, air-gapped multimodal intelligence with character-level citation verification. Unlike cloud conversational AI tools that require external API egress, and unlike generic search tools that return unverified text snippets, this platform runs embeddings, OCR, reranking, and LLM reasoning entirely on local hardware (Ollama / CUDA) while binding every generated claim to an interactive, side-by-side evidence viewer with page numbers, OCR overlays, and audio timestamps.

## Operating Context

- **Environment**: Desktop and enterprise workstations (1440px / 1024px / 768px), local intranet servers, or secure air-gapped lab nodes running Windows or Linux with CUDA GPU acceleration.
- **Data Ingestion**: Multi-format files including multi-page PDF files, DOCX documents, Excel spreadsheets, PNG/JPEG images/screenshots, and WAV/MP3 audio recordings.
- **User Rituals**: Creating focused investigation sessions, managing thematic collections, querying through text or voice dictation, attaching comparative image screenshots, clicking numbered citation pills (`[1]`, `[2]`), and validating source passages directly in an integrated document split-viewer.

## Capabilities and Constraints

- **Local Inference Engine**: Local Ollama runtime (`qwen2.5:7b-instruct` / `qwen3:4b`), local SentenceTransformers embeddings (`paraphrase-multilingual-MiniLM-L12-v2`), local CLIP (`clip-ViT-B-32`), local Faster-Whisper, and local PaddleOCR (`PP-OCRv6`).
- **Hybrid Retrieval Pipeline**: Dense semantic vector search merged with SQLite FTS5 BM25 lexical search via Reciprocal Rank Fusion (RRF), guarded against non-Latin cross-encoder degradation.
- **Enterprise Controls**: Multi-tenant session isolation, role-based access control (Admin vs. Member), security audit logging, rate limiting, and zero external network dependencies.
- **Technical Constraints**: Must run offline without requiring external API keys (cloud providers Groq, OpenAI, Claude, Gemini remain optional user-configured fallbacks). All uploaded media must stay within local tenant storage.

## Brand Commitments

- **Name**: Enterprise Multimodal Offline RAG Platform (Multimodal Offline RAG).
- **Tone & Voice**: Authoritative, precise, restrained, and audit-ready. UI copy prioritizes clarity, technical veracity, and verification confidence over playful or promotional jargon.
- **Visual Identity**: Clean enterprise data-density, high contrast legibility, restrained indigo/accent tokens (`brand`, `accent`), neutral surface levels (`surface-50` through `surface-950`), supporting both dark and light modes.

## Evidence on Hand

- Production runbook and deployment guides: `PRODUCTION_RUNBOOK.md`, `PRODUCTION_DEPLOYMENT.md`, `PRODUCTION_ACCEPTANCE_REPORT.md`.
- Frontend architecture: React 18 SPA (Vite + TypeScript + Tailwind CSS + Lucide Icons + KaTeX).
- Acceptance test benchmarks: Hit@1 = 0.80, Hit@5 = 1.00, MRR = 0.90, NDCG@5 = 0.9262 across multilingual and multimodal test suites.
- Verified test datasets: Legal reports, university practical manuals (`SVVT_Practical_File_Govind_Shree_lochan_Updated.pdf`), UI screenshots (`Screenshot (2).png`), and Devanagari Hindi evaluation corpora.

## Product Principles

1. **Verification Over Hallucination**: An answer without traceable evidence is incomplete; every substantive factual claim must link directly to an exact source citation and location.
2. **Zero-Egress by Default**: Privacy is absolute. All document parsing, OCR extraction, vector search, and generation run locally on host compute unless the user explicitly configures an external provider.
3. **Restraint and Operational Clarity**: Interface complexity recedes to let the analyst focus on document text, data comparisons, and evidence analysis.
4. **Multimodal Cohesion**: Documents, tables, screenshots, and spoken audio are first-class search citizens, treated with equal fidelity in retrieval and citation presentation.

## Accessibility & Inclusion

- Keyboard navigability across search inputs, citation buttons, and split-viewer sidebars.
- Full contrast compliance across both Light and Dark themes.
- Unicode and Devanagari script integrity across passage highlights, tables, and search suggestions.
- Clear disclosure for assistive features (e.g. browser Web Speech API dictation vs. local whisper).

