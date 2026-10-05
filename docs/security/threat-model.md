# Threat Model

## Assets
- User accounts (email, password hash) — `storage/users.json`
- Session tokens (bearer, HMAC-signed) and the revocation list
- Uploaded documents/images/audio and their extracted text/chunks
- Vector index (Chroma) and lexical index (SQLite FTS5) — both contain
  derived content from uploaded documents, scoped per user/session
- Cloud provider API keys (Fernet-encrypted at rest)
- Chat history (questions, answers, citations)

## Trust boundaries
1. **Browser <-> FastAPI backend** — untrusted input; the only boundary an
   anonymous internet attacker can reach directly.
2. **FastAPI backend <-> Ollama** — internal Docker network only (not
   published to the host as of this pass); trusted, but Ollama itself has
   no auth of its own, so this boundary matters if the network isolation
   is ever weakened.
3. **FastAPI backend <-> cloud providers (OpenAI/Anthropic/Groq/Gemini)** —
   outbound only, authenticated with per-user encrypted keys.
4. **One user's data <-> another user's data** — enforced entirely at the
   application layer (every retrieval/cache/session/file operation is
   scoped by `user_id`); there is no database-level row-level security
   layer underneath it, so a bug in any one of these scoping checks is a
   direct tenant-isolation breach.

## Threat actors considered
- **Anonymous internet attacker** — can reach `/api/auth/register`,
  `/api/auth/login`, and (if CORS/network config is misconfigured) anything
  else. Mitigated by: rate limiting on register/login, password hashing,
  CORS allowlist, Ollama not being publicly reachable.
- **Authenticated malicious user** — can reach every endpoint with their
  own token. Mitigated by: per-user scoping on all data access, chat/ingest
  rate limits, upload size/count limits, provider allowlist (only
  `registry.names()` are valid provider strings), model names are fixed
  per provider by server config (not user-suppliable), so there's no path
  to an arbitrary model/SSRF-style provider URL injection in this codebase
  as it stands.
- **Malicious document uploader** — uploads a document containing prompt
  injection ("ignore previous instructions...") or oversized/malformed
  content. Partially mitigated: `prompt_templates.SYSTEM_PROMPT` (unchanged
  by this pass) is responsible for treating retrieved content as untrusted
  evidence, not instructions — this was not re-audited in this pass and
  should be. Upload size/count limits now exist; file-signature validation
  does not yet.
- **Compromised/malicious API client** using a stolen bearer token — can
  act as that user until the token is revoked or expires. Mitigated by:
  token TTL (default 7 days — consider shortening for higher-security
  deployments), explicit logout/revocation now available.
- **Insider/admin** — this codebase has no distinct admin role; every
  authenticated user has the same permissions over their own data. There is
  no cross-user admin capability to abuse, but there's also no audit trail
  of who accessed what beyond what `answer.py`'s `_audit()` already logs
  (not reviewed in this pass).
- **Malicious retrieved content** (via RAG evidence injection) — see
  "malicious document uploader" above; this is the same threat surfaced
  through the retrieval pipeline instead of directly.

## Residual risks (known, not addressed in this pass)
- No file-signature/magic-byte validation on uploads.
- No CSRF protection (fine while auth is bearer-token-only; revisit if
  cookie auth is ever introduced).
- In-process rate limiting does not survive a process restart and does not
  coordinate across multiple backend worker processes — fine for the
  single-process local/desktop deployment this app actually targets today;
  would need a Redis-backed limiter for a multi-process production
  deployment.
- Session storage is one JSON file per session with no observed
  file-locking/atomic-write guarantees (not addressed in this pass).
- No dependency vulnerability scanning has been run (no network access in
  this development environment).
- `answer.py`'s prompt-injection handling (treating retrieved documents as
  untrusted evidence rather than instructions) was not re-audited in this
  pass — it predates this work and should get its own dedicated review
  with adversarial test documents (brief §16's
  `tests/security/test_prompt_injection.py` does not exist yet).

## What changed in this pass, mapped to threats above
- Ollama no longer reachable from outside the Docker network → shrinks the
  "anonymous internet attacker" surface if the compose network is otherwise
  exposed.
- Login/register rate limiting + lockout → raises the cost of a credential
  brute-force attack.
- Token revocation → bounds the blast radius of a leaked token to "until
  logout" instead of "until natural expiry" when the user notices.
- CORS allowlist → removes the ability for an arbitrary third-party site to
  make authenticated cross-origin requests on a logged-in user's behalf
  (to the extent the browser's CORS model applies to this bearer-token
  auth scheme — this mitigation matters most if cookie auth is ever added).
- Classified cloud-provider failover → prevents a user's explicit provider
  choice from being silently overridden by a different backend on error,
  which is a correctness/trust issue more than a classic security one, but
  is listed here because §51A treats it as a required guarantee.
