# What changed — your 8 requests

A point-by-point map of what was built for each change and how to use it.

## 1. New chat + saved chats with their own files (ChatGPT-style)
- A left **sidebar** lists every saved chat; **New chat** starts a fresh screen.
- Each chat has its **own isolated library** — a new chat shows zero files.
- Everything is **saved**: reopen an old chat and its messages *and* its
  attached documents/images/audio come back. The LLM also gets the recent
  conversation as context, so follow-up questions "remember" earlier turns.
- How it works: every indexed chunk is tagged with a `session_id`; chats are
  stored as JSON under `backend/storage/sessions/`, uploads under
  `backend/data/<session_id>/`. Files: `backend/sessions.py`, session routes in
  `main.py`, `Sidebar.tsx`.

## 2. Search only the sources you pick (no more stray PDF)
- Next to the input there's a **Scope** selector: choose a **type**
  (All / Documents / Images / Audio) **and/or tick specific files**.
- Tick one image → only that image is searched; nothing from other sources.
- Because each chat is isolated (see #1), other chats' files can never leak in.
- Files: `ScopePanel.tsx`, `retrieval/search.py` (`build_where` filters by
  session + modality + filenames).

## 3. Light / dark theme toggle
- Sun/Moon button in the header flips the theme; your choice is remembered
  (localStorage) and applied before the page paints (no flash).
- Files: `tailwind.config.js` (`darkMode: 'class'`), `index.html`, dark styles
  across all components.

## 4. Mobile friendly (for sharing/testing on a phone)
- Responsive layout: sidebar and sources become slide-over drawers, the header
  compacts, buttons collapse to icons, a floating **Sources** button appears.
- Test from your phone on the same Wi-Fi — see DEPLOYMENT.md ("LAN").

## 5. Better OCR + fixed citation duplication
- OCR now **preprocesses** each image (grayscale → autocontrast → upscale small
  screenshots → sharpen) and uses the LSTM engine with a uniform-block page
  mode. Big accuracy jump on screenshots.
- Citation mix-up fixed: an image used to appear up to 3 times (OCR + caption +
  visual). Results are now **de-duplicated to one citation per source**
  (per file, per page, or per timecode).
- Files: `ingestion/image_pipeline.py`, `retrieval/search.py` (`_citation_key`).

## 6. Faster processing
- Models are **warmed up at startup** (background thread) so the first query
  isn't slow.
- The LLM is kept **resident in memory** between requests (`keep_alive`).
- Embeddings are **batched** for GPU throughput.
- Speed levers in `config.py`: use `WHISPER_MODEL=base`, `LLM_MODEL=qwen3:4b`,
  or a bigger `EMBED_BATCH_SIZE` if you want more speed.

## 7. Different languages — yes
- **Audio:** Whisper auto-detects and transcribes **90+ languages** (Hindi,
  etc.) accurately, offline. Set `WHISPER_TASK=translate` to get English out of
  any spoken language, or `WHISPER_LANGUAGE=hi` to force one.
- **Text search:** the embedding model is now **multilingual** (50+ languages),
  so a Hindi query can match Hindi/English content.
- **Image OCR:** English by default. For Hindi/other text in images, install the
  language data and set `OCR_LANG=eng+hin` (Docker image already includes Hindi;
  on Windows tick the extra language in the Tesseract installer).
- **Answers:** the Qwen3 LLM is multilingual, so it can answer in the
  language you ask in.

## 8. Deployment / sharing (offline, with frontend)
- **Docker (one command):** `docker compose up -d --build` runs Ollama +
  backend + frontend together; open `http://localhost:8080`.
- **Native scripts:** `scripts/run-windows.bat` builds the frontend and has the
  backend serve it on `http://localhost:8000` (single process). Dev mode:
  `scripts/dev-windows.bat`.
- **Share on LAN:** both bind to `0.0.0.0`, so anyone on the same Wi-Fi can open
  `http://<your-ip>:8080` (Docker) or `:8000` (native) — including a phone.
- Full instructions: **DEPLOYMENT.md**.

---

### New setup notes
- **FFmpeg** is only needed if some audio file fails to decode (the Docker image
  already includes it).
- For **Hindi OCR** on Windows, install Tesseract's Hindi language data, then set
  `OCR_LANG=eng+hin`.
- First run still downloads models once (needs internet once); after that it's
  fully offline.

---

# v3 — OCR, precise citations & multi-user login

### OCR is now much better (PaddleOCR) + chunked
- Switched image OCR to **PaddleOCR** (deep-learning) with a Tesseract fallback —
  far more accurate on screenshots/photos, multilingual, GPU-accelerated.
- Small images are **upscaled** first (big accuracy win on low-res screenshots).
- Text-heavy images are **split into multiple OCR chunks**, so a big image is
  read fully and each part is retrievable + citable on its own.
- Opening an image citation now shows **"Text read from image"** (the exact OCR
  chunk it used) alongside the image preview, and labels it "Text block i of n".
- First run downloads the PaddleOCR models (~100 MB) once, then fully offline.

### Precise page numbers (documents) + timecodes (audio)
- Document citations show a **"Found on page X"** badge when expanded (PDF pages
  are tracked per page).
- Audio citations show a **"Spoken at MM:SS"** badge and a **Play from MM:SS**
  button — jump straight to that moment to listen. Audio is now cut into finer
  ~12s windows for tighter timing.

### Multi-user login — private spaces (privacy fix)
- Everyone must **register (email + password)** the first time, then **log in**.
- Passwords are salted + hashed (PBKDF2); login issues a signed, expiring token.
- **Every user only sees their own** chats, files, and search results — one
  person can never see another's uploads. Enforced on every route (queries,
  file listing, media downloads, and citation source lookups all check the
  owner). All local + offline; accounts live in `backend/storage/users.json`.
- See **RUN_AND_LOGIN.md** for the exact run commands and the login flow.

> Note: this is app-level auth suited to a local/LAN offline deployment (not a
> hardened public internet service). For public exposure, add HTTPS + rate
> limiting behind a reverse proxy.
