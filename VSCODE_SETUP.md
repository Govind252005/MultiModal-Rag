# Multimodal Offline RAG — VS Code Setup Guide (Windows)

This is a companion to the PowerShell setup guide, but wired for **VS Code**:
workspace config, recommended extensions, one-click run/debug for both
backend and frontend, and integrated terminal usage. It assumes you've
already installed the base tools (Python, Node, Ollama, Tesseract) — if not,
do Section 1 of the PowerShell guide first.

> Folder structure assumed:
> ```
> Minor Project/
> ├── backend/
> └── frontend/
> ```

---

## 0. Open the project

1. Launch VS Code.
2. **File → Open Folder** → select the `Minor Project` root (the one
   containing both `backend/` and `frontend/`). Opening the root, not just
   `backend/`, is what lets the multi-root/tasks setup below work.
3. If prompted **"Do you trust the authors of this folder?"** → click
   **Yes, I trust the authors**.

---

## 1. Install the recommended extensions

Open the Extensions panel (`Ctrl+Shift+X`) and install:

| Extension | Why |
|---|---|
| **Python** (Microsoft) | Interpreter selection, linting, debugging for the FastAPI backend |
| **Pylance** | Fast type checking / IntelliSense for Python |
| **ESLint** | Lint the React/TypeScript frontend |
| **Prettier – Code formatter** | Consistent JS/TS/CSS formatting |
| **Tailwind CSS IntelliSense** | Autocomplete for Tailwind classes in the frontend |
| **Thunder Client** (or REST Client) | Hit `/api/query`, `/api/ingest`, etc. without leaving VS Code |
| **Even Better TOML** *(optional)* | If `config.py` settings ever move to a `.toml` file |

Once you open a `.py` file, VS Code may prompt "Install recommended
extensions?" — accept it if it appears.

---

## 2. Create a `.vscode` workspace config

Create a folder named `.vscode` at the project root, with three files inside
it: `settings.json`, `launch.json`, and `tasks.json`.

### 2.1 `.vscode/settings.json`

```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/backend/venv/Scripts/python.exe",
  "python.terminal.activateEnvironment": true,
  "python.analysis.extraPaths": ["${workspaceFolder}/backend"],
  "terminal.integrated.defaultProfile.windows": "PowerShell",
  "editor.formatOnSave": true,
  "[python]": {
    "editor.defaultFormatter": "ms-python.python"
  },
  "[typescript][typescriptreact][javascript]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode"
  },
  "eslint.workingDirectories": ["frontend"],
  "files.exclude": {
    "**/__pycache__": true,
    "**/venv": true,
    "**/node_modules": true
  }
}
```

### 2.2 `.vscode/launch.json` — one-click debugging

This lets you hit **F5** and pick "Backend" or "Frontend" (or run both via
the compound entry), with real breakpoints in Python and the browser.

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Backend (FastAPI/uvicorn)",
      "type": "debugpy",
      "request": "launch",
      "module": "uvicorn",
      "args": ["main:app", "--reload", "--port", "8000"],
      "cwd": "${workspaceFolder}/backend",
      "console": "integratedTerminal",
      "justMyCode": false
    },
    {
      "name": "Frontend (Chrome @ Vite)",
      "type": "chrome",
      "request": "launch",
      "url": "http://localhost:5173",
      "webRoot": "${workspaceFolder}/frontend/src"
    }
  ],
  "compounds": [
    {
      "name": "Full Stack (Backend + Frontend)",
      "configurations": ["Backend (FastAPI/uvicorn)", "Frontend (Chrome @ Vite)"],
      "stopAll": true
    }
  ]
}
```

> ⚠️ The Frontend debug config attaches Chrome to a **running** `npm run dev`
> server — it doesn't start Vite for you. Use the task below for that, or run
> `npm run dev` manually in a terminal first, then launch "Frontend (Chrome
> @ Vite)".

### 2.3 `.vscode/tasks.json` — run both servers with one command

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Backend: uvicorn",
      "type": "shell",
      "command": "./venv/Scripts/Activate.ps1; uvicorn main:app --reload --port 8000",
      "options": { "cwd": "${workspaceFolder}/backend" },
      "problemMatcher": [],
      "isBackground": true,
      "presentation": { "panel": "dedicated", "group": "servers" }
    },
    {
      "label": "Frontend: npm run dev",
      "type": "shell",
      "command": "npm run dev",
      "options": { "cwd": "${workspaceFolder}/frontend" },
      "problemMatcher": [],
      "isBackground": true,
      "presentation": { "panel": "dedicated", "group": "servers" }
    },
    {
      "label": "Run Full Stack",
      "dependsOn": ["Backend: uvicorn", "Frontend: npm run dev"],
      "dependsOrder": "parallel",
      "problemMatcher": []
    }
  ]
}
```

Run it via **Terminal → Run Task… → Run Full Stack**, or bind a keyboard
shortcut to `workbench.action.tasks.runTask`.

---

## 3. Select the Python interpreter

If the venv doesn't already exist, build it first (Section 4 below), then:

1. `Ctrl+Shift+P` → **Python: Select Interpreter**.
2. Choose the one at `.\backend\venv\Scripts\python.exe`.
3. Confirm the bottom-right status bar shows that interpreter.

This makes Pylance resolve imports (`fastapi`, `torch`, `chromadb`, etc.)
correctly and lets `F5` debugging use the right environment.

---

## 4. First-time environment setup (via VS Code's integrated terminal)

Open a terminal with `` Ctrl+` `` (it defaults to PowerShell per the
settings.json above). This replaces doing it in a separate PowerShell window.

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements.txt
python -c "from retrieval import embeddings; embeddings.warmup(); print('models ready')"
```

Open a **second** terminal (`+` icon in the terminal panel, or the split-
terminal button) for the frontend:

```powershell
cd frontend
npm install
```

> Tip: name your terminals by right-clicking the terminal tab → **Rename**
> (e.g. "backend" / "frontend") so it's obvious which is which once both are
> running side by side.

---

## 5. Running the app day-to-day

Once the venv and `node_modules` exist, you don't need to redo Section 4.
Pick whichever workflow you prefer:

- **Fastest:** `Terminal → Run Task… → Run Full Stack` (starts both, dedicated
  panels for each).
- **With breakpoints in Python:** press `F5`, choose **Full Stack (Backend +
  Frontend)** — this launches uvicorn under the debugger and opens Chrome
  attached to Vite. Set breakpoints directly in `search.py`, `answer.py`, etc.
- **Manual:** two integrated terminals, same commands as the PowerShell guide
  (`uvicorn main:app --reload --port 8000` and `npm run dev`).

Then open <http://localhost:5173> for the app, and
<http://localhost:8000/docs> for the interactive API docs.

---

## 6. Testing the backend from VS Code (no frontend needed)

**Option A — Thunder Client:**
1. Click the Thunder Client icon in the sidebar → **New Request**.
2. `POST http://localhost:8000/api/query` with a JSON body like
   `{"query": "show me the report on 2024 development"}`.
3. Save requests into a Thunder Client collection so you can re-run them
   during the demo/viva without retyping.

**Option B — integrated terminal, same as PowerShell:**
```powershell
python -m ingestion.ingest "C:\path\to\some_report.pdf"
```

---

## 7. Debugging tips specific to VS Code

| Situation | What to do |
|---|---|
| Breakpoint in `retrieval/search.py` not hitting | Make sure you launched via **F5 → Backend**, not a plain terminal `uvicorn` command — only the debugger config attaches the debugger. |
| Pylance shows red squiggles on `import torch`/`chromadb` | Wrong interpreter selected — redo Section 3. |
| `--reload` restarts kill your debug session | Expected with `--reload`; for a debugging-heavy session, drop `--reload` from `launch.json` args once you're past initial setup. |
| ESLint not linting frontend files | Confirm `eslint.workingDirectories` in `settings.json` points to `"frontend"`, and that `frontend/node_modules` exists (`npm install`). |
| Terminal doesn't auto-activate venv | Reopen the terminal after setting `python.terminal.activateEnvironment: true`, or manually run `.\venv\Scripts\Activate.ps1`. |
| Everything else (Ollama, CUDA, Tesseract, OOM) | Same fixes as the PowerShell guide's Troubleshooting table (Section 8) — those are environment-level, not editor-level. |

---

## 8. Quick reference

| Task | VS Code way |
|---|---|
| Start both servers | Run Task → **Run Full Stack** |
| Debug backend with breakpoints | `F5` → **Backend (FastAPI/uvicorn)** |
| Debug both with breakpoints + browser | `F5` → **Full Stack (Backend + Frontend)** |
| Hit an API endpoint manually | Thunder Client |
| Switch Python env | `Ctrl+Shift+P` → Python: Select Interpreter |
| Open two terminals side by side | `` Ctrl+` `` then split-terminal icon |

See `README.md` for folder layout and `SETUP.md` (PowerShell version) for
the from-scratch tool installation steps.
