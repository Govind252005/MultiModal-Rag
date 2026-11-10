# Production Incident Response & Troubleshooting Runbook

## 1. Incident Classification Matrix

| Severity | Definition | Target Resolution | Primary Action |
|---|---|---|---|
| **SEV-1 (Critical)** | Core API down, SQLite corrupted, data loss risk | < 1 hour | Fail over to backup snapshot, restart service |
| **SEV-2 (Major)** | Local Ollama unresponsive, cloud fallback failing | < 2 hours | Restart Ollama daemon, switch answer model |
| **SEV-3 (Moderate)** | Memory consumption elevated, single user locked out | < 8 hours | Purge cache, reset user credentials |
| **SEV-4 (Minor)** | Minor UI layout glitch, non-blocking warning log | Next release cycle | Log issue, patch in staging |

---

## 2. Common Scenarios & Remediation

### Scenario A: Local Ollama Unresponsive (`/health/ready` returns `"ollama": "unavailable"`)
- **Symptoms**: Answer generation times out or returns HTTP 503.
- **Diagnostic**:
  ```powershell
  Get-Process ollama
  curl http://127.0.0.1:11434/api/tags
  ```
- **Remediation**:
  1. Restart Ollama daemon:
     ```powershell
     Stop-Process -Name ollama -Force -ErrorAction SilentlyContinue
     Start-Process -FilePath "ollama" -ArgumentList "serve"
     ```
  2. Confirm model is loaded:
     ```powershell
     ollama list
     # If qwen3:4b missing:
     ollama pull qwen3:4b
     ```

### Scenario B: SQLite Database Locked / WAL Accumulation
- **Symptoms**: `sqlite3.OperationalError: database is locked` on document indexing.
- **Remediation**:
  1. Force WAL checkpoint:
     ```python
     import sqlite3
     con = sqlite3.connect("storage/lexical_index.sqlite3")
     con.execute("PRAGMA wal_checkpoint(TRUNCATE);")
     con.close()
     ```
  2. If locking persists, verify no orphaned background worker processes are holding the file handle.

### Scenario C: High Memory Pressure / VRAM Exhaustion
- **Symptoms**: CUDA out-of-memory error during embedding or CLIP image analysis.
- **Remediation**:
  1. Check GPU utilization:
     ```powershell
     nvidia-smi
     ```
  2. Fall back embedding to CPU in `.env.production` if GPU VRAM is constrained:
     ```ini
     DEVICE=cpu
     ```
  3. Restart FastAPI service to free pooled PyTorch memory.

### Scenario D: Accidental Cloud Egress Exposure Alert
- **Symptoms**: User reports sensitive proprietary document was sent to cloud provider.
- **Remediation**:
  1. Immediately check `storage/audit_log.jsonl` for request ID and model used.
  2. In **Models & Settings**, disable or revoke the affected Cloud API key.
  3. Switch system default model back to `Local Qwen (Ollama)`.
  4. Review user consent records and the cloud provider's data retention policy.

