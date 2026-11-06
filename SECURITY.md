# Enterprise Security & Privacy Architecture

## 1. Security Overview

The Enterprise Multimodal Offline RAG Platform is built with defense-in-depth principles designed for private enterprise workspaces, air-gapped defense/legal environments, and strictly confidential research facilities.

All core functions—document parsing, OCR, multi-vector indexing, BM25 lexical indexing, dense embedding generation, cross-lingual retrieval, and generative reasoning via Ollama—run 100% on-premises without mandatory third-party network egress.

---

## 2. Authentication & Session Security

- **Cryptographic Token Verification**: Session tokens are signed using HMAC-SHA256 with an ephemeral/persistent secret key (`storage/secret.key`).
- **Account Status Validation**: Every authenticated request evaluates account status. Disabled or suspended accounts are rejected with `HTTP 403 Forbidden`, immediately revoking active sessions without waiting for token expiration.
- **Brute Force & Rate Limiting**:
  - Sliding-window rate limiter prevents credential stuffing on `/api/auth/login` (maximum 5 attempts per 60 seconds with automatic 300-second lockout).
  - Registration endpoint rate-limited to 10 attempts per hour.
  - Chat query endpoint rate-limited to 30 requests per minute per IP/user.

---

## 3. Strict Role-Based Access Control (RBAC) & Multi-Tenancy

- **Role Separation**:
  - `admin`: Full administrative control, user provisioning, role adjustments, account deactivation, and enterprise audit log inspection.
  - `user`: Standard document analysis, isolated collection management, personal session history, and scoped retrieval.
- **Multi-Tenant Data Isolation**:
  - Vector embeddings in ChromaDB are tagged with metadata `{ user_id: ..., org_id: ..., session_id: ... }`.
  - Document deletions enforce ownership: a user can only delete documents belonging to their own sessions or organization. Cross-tenant deletion attempts are rejected with `HTTP 403 Forbidden`.
  - Collections enforce strict boundaries: updating or deleting a collection belonging to another user raises `HTTP 404 Not Found` to prevent metadata leakage or existence probing.

---

## 4. Ingestion Safety & File Upload Hardening

- **Binary Magic-Byte Inspection**:
  - File uploads reject content-type spoofing (e.g., an executable renamed to `.pdf` or `.png`).
  - Strict magic headers verified:
    - PDF: `%PDF`
    - PNG: `\x89PNG\r\n\x1a\n`
    - JPEG: `\xff\xd8\xff`
    - DOCX / XLSX / PPTX: `PK\x03\x04`
    - Audio: RIFF/WAVE or MP3 sync frames
  - Invalid headers trigger an immediate `HTTP 400 Bad Request`.
- **Path Traversal Defense**:
  - All filenames are sanitized with strict base name extraction. Payloads containing `../`, `..\\`, null bytes, or absolute path prefixes are rejected with `HTTP 400 Bad Request`.
- **Resource Exhaustion Limits**:
  - Maximum upload size: 200MB per file.
  - Maximum batch upload: 20 files per request.
  - PDF page count cap: Documents exceeding 1,000 pages are rejected during parsing.

---

## 5. Offline Privacy & Network Boundaries

| Component | Default Mode | Network Requirement | Privacy Classification |
|---|---|---|---|
| **Embeddings (BGE-M3 / MiniLM)** | Local SentenceTransformers | 0 (Zero egress) | 100% Local Confidential |
| **Cross-Modal Embeddings (CLIP)** | Local PyTorch | 0 (Zero egress) | 100% Local Confidential |
| **Lexical Indexing (SQLite FTS5)** | Local Embedded SQLite | 0 (Zero egress) | 100% Local Confidential |
| **Vector Indexing (ChromaDB)** | Local Embedded Chroma | 0 (Zero egress) | 100% Local Confidential |
| **OCR & Parsing (PaddleOCR / MuPDF)** | Local CPU/CUDA | 0 (Zero egress) | 100% Local Confidential |
| **Audio Transcription (Whisper)** | Local Faster-Whisper | 0 (Zero egress) | 100% Local Confidential |
| **LLM Inference (Ollama / Qwen)** | Local HTTP `127.0.0.1:11434` | 0 (Zero egress) | 100% Local Confidential |
| **Live Dictation (Web Speech API)** | Browser API | Browser-dependent (Cloud/Local) | Disclosed via UI banner |
| **Cloud Providers (Gemini / Claude)** | Optional per-user opt-in | External HTTPS API | Requires user explicit key |

---

## 6. Audit Logging & Compliance

- **Append-Only Audit Trail**: High-risk security events (logins, logouts, role escalations, user status modifications, document deletions, collection operations) are logged to `storage/audit_log.jsonl`.
- **Query Scoping**: Audit log queries are restricted to authenticated administrators (`require_admin` dependency).

---

## 7. Reporting Security Vulnerabilities

To report security issues, contact the designated enterprise security team or open a private security advisory in your internal enterprise Git repository.

