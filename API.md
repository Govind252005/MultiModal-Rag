# Enterprise REST API Reference

The backend exposes a FastAPI REST service on `http://localhost:8000`. All mutating and retrieval endpoints require an authentication token passed via cookie (`session_token`) or Bearer header (`Authorization: Bearer <token>`).

---

## 1. Authentication & User Endpoints

### `POST /api/auth/register`
Create a new user account.
- **Request Body**:
  ```json
  {
    "email": "user@enterprise.local",
    "password": "StrongPassword123!",
    "full_name": "Enterprise Analyst"
  }
  ```
- **Response**: `200 OK` with user profile and session token.

### `POST /api/auth/login`
Authenticate an existing user.
- **Request Body**:
  ```json
  {
    "email": "user@enterprise.local",
    "password": "StrongPassword123!"
  }
  ```
- **Response**: `200 OK` with user profile and session token cookie.

### `GET /api/auth/me`
Retrieve profile of currently authenticated user.
- **Response**:
  ```json
  {
    "user": {
      "id": "usr_...",
      "email": "user@enterprise.local",
      "full_name": "Enterprise Analyst",
      "role": "user",
      "status": "active"
    }
  }
  ```

---

## 2. Ingestion & Document Endpoints

### `POST /api/upload`
Upload one or more documents for parsing and indexing.
- **Content-Type**: `multipart/form-data`
- **Form Fields**:
  - `files`: Binary document files (PDF, DOCX, XLSX, PPTX, PNG, JPG, MP3, WAV).
  - `session_id`: Active chat session ID.
- **Response**: `200 OK` with ingested document status and chunk statistics.

### `GET /api/documents`
List documents belonging to the user's sessions.
- **Response**:
  ```json
  [
    {
      "name": "Global_Compliance_Handbook.docx",
      "size": 24576,
      "modality": "docx",
      "chunk_count": 14,
      "page_count": 5
    }
  ]
  ```

### `DELETE /api/documents/{filename}`
Delete a document and purge its corresponding vectors and lexical entries.
- **Response**: `200 OK` or `403 Forbidden` if document belongs to another tenant.

---

## 3. Grounded Query & Retrieval Endpoints

### `POST /api/query`
Run hybrid multi-vector retrieval and stream grounded generation.
- **Request Body**:
  ```json
  {
    "session_id": "sess_...",
    "query": "What were the material facts in Rylands v Fletcher?",
    "top_k": 5,
    "selected_files": ["Rylands_v_Fletcher_1868.pdf"],
    "stream": true
  }
  ```
- **Response**: Server-Sent Events (SSE) stream containing text chunks and final citations metadata.

### `GET /api/document/{session_id}/{filename}`
Fetch structured document content for split-screen evidence verification.
- **Response**:
  ```json
  {
    "filename": "Rylands_v_Fletcher_1868.pdf",
    "modality": "pdf",
    "has_pages": true,
    "page_count": 5,
    "pages": [
      {
        "page_number": 1,
        "text": "..."
      }
    ]
  }
  ```

---

## 4. Collections & Scope Endpoints

### `GET /api/collections`
List collections accessible to the current user.
- **Response**: Array of collection objects.

### `POST /api/collections`
Create a new isolated document collection.
- **Request Body**:
  ```json
  {
    "name": "Legal Department Contracts",
    "description": "Executed vendor agreements and NDA documentation",
    "document_ids": ["doc_1", "doc_2"]
  }
  ```

---

## 5. Enterprise Administration Endpoints

### `GET /api/admin/users`
List enterprise users (Requires `admin` role).
- **Response**: Array of user management records.

### `PATCH /api/admin/users/{user_id}/status`
Enable or disable a user account.
- **Request Body**: `{"status": "disabled"}`
- **Response**: Updated user record.

### `GET /api/admin/audit-logs`
Retrieve tamper-evident audit logs with optional filtering.
- **Query Params**: `limit=100`, `event_type=auth.login`, `user_id=...`
- **Response**: `{"events": [...], "logs": [...]}`

