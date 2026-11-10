# Enterprise Administration Guide

## 1. Role-Based Access Control (RBAC) & User Management
The platform enforces a strict multi-tenant authorization matrix separating enterprise administrators from regular employees.

### User Roles
- **Admin**:
  - Full access to `/api/admin/users`, `/api/admin/audit-logs`, and system metrics.
  - Ability to create users, reset passwords, update roles, and enable/disable accounts.
  - Ability to manage system-wide cloud provider keys and configure default models.
  - Unrestricted collection management across organizational tenants.
- **Member (User)**:
  - Restricted to chat generation, private document upload, personal collections, and own search sessions.
  - Strictly blocked from administrative endpoints (HTTP 403 Forbidden).
  - Cannot view, modify, or delete collections or documents owned by other users.

### User Lifecycle Management
- **Account Disablement**: When an employee departs, toggle status to `disabled` via the Admin Console or `PATCH /api/admin/users/{user_id}`.
- **Instant Revocation**: Any active JWT / bearer session token for a disabled user is immediately rejected at the API gateway on the next request.

---

## 2. Document & Collection Isolation
- **Organization Boundary (`org_id`)**: Every vector chunk, lexical entry, and session log is partitioned by `org_id`.
- **Intra-Organization Isolation**: Collections are bound to `owner_id`. A user in the same org cannot alter or delete collections owned by peers unless the collection is explicitly marked `is_shared=true`.
- **IDOR Safeguards**: Direct document deletion attempts across user boundaries return HTTP 403/404.

---

## 3. Cloud Provider & API Key Management
The platform supports optional cloud answer generation providers: **Claude (Anthropic)**, **OpenAI**, **Groq**, and **Google Gemini**.

### Key Ingestion & Verification
1. Navigate to **Models & Settings** -> **Provider Configuration**.
2. Enter the API key for the chosen provider.
3. Click **Verify Key**:
   - The backend performs a live test probe against the provider API.
   - If the key is invalid or lacks quota, the UI displays `Invalid Key ✗` and rejects persistence.
   - If valid, the UI displays `Verified ✓`, encrypts the key at rest using Fernet (AES-128-CBC + HMAC-SHA256), and dynamically populates the **Available Models** dropdown.
4. Select the desired model (e.g. `claude-3-5-sonnet-20241022`, `gpt-4o`, `llama-3.3-70b-versatile`, `gemini-1.5-pro`) and click **Save**.

### Cloud Privacy Disclosure
When any non-local model is selected as the active Answer Model, an enterprise amber disclaimer banner is rendered above the chat composer:
> *"Cloud Generation Active: Your question and retrieved source passages will be transmitted to external servers for answer generation."*

---

## 4. Comprehensive Audit Trails
Every sensitive enterprise operation is recorded with a structured JSONL audit entry (`storage/audit_log.jsonl`):
- User authentication events (login, logout, token refresh).
- Document ingestion, chunking, and document deletion.
- Collection creation, updating, document addition, and collection deletion.
- Admin user modifications and role elevations.
- API key ingestion, verification, and rotation.

Logs can be viewed in real-time under the **Audit Logs** tab in Enterprise Administration.

