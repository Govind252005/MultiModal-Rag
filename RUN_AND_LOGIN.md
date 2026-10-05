# How to run the server (with login) — quick commands

Your service now requires every person to **register / log in** before they can
ingest files or search. Each account has a fully private space — nobody sees
anyone else's files or chats.

---

## First-time setup (once per machine)

1. Install: Python, Node, Ollama, (Tesseract optional). See `SETUP_GUIDE.md`.
2. Pull the local LLM once (needs internet once, then offline):
   ```bat
   ollama pull qwen3:8b
   ```
3. Backend deps:
   ```bat
   cd backend
   python -m venv venv
   venv\Scripts\activate
   pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
   pip install -r requirements.txt
   ```
   >First image OCR/search downloads the PaddleOCR models once (only during initial setup or Docker build). After that, OCR runs completely offline.
   > fully offline.

---

## Run it — DEV mode (two windows, hot reload)

```bat
:: from the project root
scripts\dev-windows.bat
```
- Frontend: http://localhost:5173
- Backend:  http://localhost:8000

Or manually:
```bat
:: Terminal 1
cd backend && venv\Scripts\activate && uvicorn main:app --reload --host 0.0.0.0 --port 8000
:: Terminal 2
cd frontend && npm install && npm run dev -- --host
```

## Run it — PRODUCTION mode (one URL, one process)

```bat
scripts\run-windows.bat
```
This builds the frontend and the backend serves it at **http://localhost:8000**.

---

## The login flow (what each person does)

1. Open the app URL in the browser.
2. First time → click **Register**, enter email + password (min 6 chars).
3. Next times → just **Log in** with the same email + password.
4. After login they land in their **own private space** and can create chats,
   upload PDFs/images/audio, and search — all isolated to their account.

Accounts are stored locally on the server in `backend/storage/users.json`
(passwords are salted + hashed, never stored in plain text). The signing key is
`backend/storage/secret.key`. Everything is offline.

---

## Share with others on the same Wi-Fi (LAN)

Both modes bind to `0.0.0.0`, so others can reach your machine:

1. Find your IP: `ipconfig` → IPv4 Address (e.g. `192.168.1.42`).
2. They open `http://192.168.1.42:8000` (production) or `:5173` (dev) and
   register their own account.
3. Allow the port through Windows Firewall if prompted.

For Docker deployment instead, see `DEPLOYMENT.md`.

---

## Multilingual / Hindi

- **Audio**: Whisper auto-detects & transcribes 90+ languages (incl. Hindi).
- **Text search**: multilingual embeddings (Hindi query matches Hindi/English).
- **Image OCR in Hindi**: set `PADDLEOCR_LANGS=en,hi` before starting the backend:
  ```bat
  set PaddleOCR_LANGS=en,hi
  uvicorn main:app --host 0.0.0.0 --port 8000
  ```

## Reset / start clean
Log in and call `POST /api/reset` (deletes only *your* data), or delete the
`backend/storage` and `backend/data` folders while the server is stopped.
