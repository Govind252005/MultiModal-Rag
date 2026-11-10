# Production Runbook: Enterprise Multimodal Offline RAG Platform

## 1. System Overview & Architecture
The Enterprise Multimodal Offline RAG Platform is an on-premises, privacy-first intelligence platform. It runs fully offline with zero mandatory internet egress, powered by local vector search (ChromaDB), SQLite FTS5 lexical indexing, reciprocal rank fusion (RRF), cross-encoder neural reranking, and local inference via Ollama (`qwen3:4b`).

### Key Network Ports
- **FastAPI Core Service**: `8000` (Default HTTP/REST API & SSE Streamer)
- **Vite Development UI (Dev only)**: `5173`
- **Ollama LLM Daemon**: `11434` (Bound strictly to `127.0.0.1` locally)
- **Nginx Reverse Proxy (Production)**: `443` (TLS 1.3 Termination) / `80` (Redirect)

---

## 2. Service Management

### Linux (Systemd)
- **Start Core Service**: `sudo systemctl start multimodal-rag.service`
- **Stop Core Service**: `sudo systemctl stop multimodal-rag.service`
- **Restart Core Service**: `sudo systemctl restart multimodal-rag.service`
- **Status & Diagnostics**: `sudo systemctl status multimodal-rag.service`
- **Follow Logs**: `sudo journalctl -u multimodal-rag.service -f`
- **Scheduled Backup Timer**: `sudo systemctl status multimodal-rag-backup.timer`

### Windows (PowerShell / Services)
- **Start Production Service**:
  ```powershell
  cd MultiModal-Rag-main
  .\scripts\start-production.ps1
  ```
- **Stop Production Service**:
  ```powershell
  .\scripts\stop-production.ps1
  ```
- **Run Standalone Daemon Directly**:
  ```powershell
  # Start Ollama
  Start-Process -FilePath "ollama" -ArgumentList "serve"
  # Start FastAPI Production Server
  .\backend\venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4
  ```

---

## 3. Health & Liveness Probes
Production orchestrators, load balancers, and external watchdogs probe three endpoints:
- **Liveness Probe**: `GET /health/live`  
  Returns `{"status": "alive"}` (HTTP 200). Use for k8s pod restart decisions.
- **Readiness Probe**: `GET /health/ready`  
  Returns `{"status": "ready", "storage": "ok", "ollama": "ok"}`. Confirms filesystem storage and local Ollama daemon availability.
- **Deep Dependency Inspection**: `GET /health/dependencies`  
  Exposes SQLite FTS5 status, ChromaDB collections, disk storage capacity (`free_gb`), circuit breaker states, and memory metrics.
- **Prometheus Metrics**: `GET /metrics`  
  Exposes standard Prometheus scrape metrics including HTTP latency histograms, counter requests, and system resource counters.

---

## 4. LAN & Wi-Fi Multi-Device Sharing
To allow team members, colleagues, or mobile devices on the same local network / Wi-Fi to test the platform:

1. **Host Binding**: Set `HOST=0.0.0.0` in `.env.production` (or CLI `--host 0.0.0.0`).
2. **Find Host IP**:
   ```powershell
   Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -like "*Wi-Fi*" -or $_.InterfaceAlias -like "*Ethernet*" }
   ```
   Example: `192.168.1.105`
3. **Open Inbound Windows Firewall Rule**:
   ```powershell
   New-NetFirewallRule -DisplayName "Multimodal RAG Server (Port 8000)" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
   ```
4. **Access Across Devices**:
   - Colleagues open `http://192.168.1.105:8000` in their mobile browser (Safari, Chrome) or desktop browser.
   - Each colleague registers an independent account with private collections, session isolation, and personalized audit logging.

---

## 5. Security & Cryptographic Standard
- **Key Store Encryption**: API keys and secrets in `backend/keystore.py` are encrypted using Python's `cryptography.fernet.Fernet`.
- **Accurate Cryptographic Cipher**: Fernet operates strictly with **AES-128-CBC with PKCS7 padding and HMAC-SHA256 authenticated encryption** (128-bit AES encryption key + 128-bit HMAC authentication key derived from a 256-bit secret).
- **Session Tokens**: Cryptographically signed SHA-256 session tokens with 24-hour expiration and immediate database-backed revocation.
- **Cloud Egress Protection**: Default configuration operates 100% locally. Ingesting cloud keys requires manual entry in the Admin/Model Settings UI, and an explicit Privacy Disclosure banner appears before any query passes to external cloud providers.

