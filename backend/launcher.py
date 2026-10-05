"""
Desktop launcher for the Multimodal Offline RAG app.
...
"""

from __future__ import annotations

import os
import sys
import time
import threading
import webview
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError


def _bootstrap_paths() -> Path:
    """Return the directory that contains main.py / config.py and put it on
    sys.path. Works both from source and inside a PyInstaller bundle."""
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        base = Path(__file__).resolve().parent
    base_str = str(base)
    if base_str not in sys.path:
        sys.path.insert(0, base_str)
    try:
        os.chdir(base_str)
    except OSError:
        pass
    return base


HOST = os.getenv("RAG_HOST", "127.0.0.1")
PORT = int(os.getenv("RAG_PORT", "8000"))
BASE_URL = f"http://{HOST}:{PORT}"


def _redirect_console_streams(data_home: Path) -> None:
    """--windowed PyInstaller builds have no console, so sys.stdout/stderr
    are None. Any print()/logging call would crash with 'Bad file
    descriptor'. Redirect to a log file instead of losing the output."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    log_dir = Path(data_home) / "Logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = open(log_dir / "app.log", "a", encoding="utf-8", buffering=1)
    sys.stdout = log_file
    sys.stderr = log_file


def _wait_for_health(url: str, timeout: float = 180.0) -> bool:
    """Poll the health endpoint until it answers or we time out. 180s
    (not 90s) because first-run model loading can genuinely take longer
    than 90s on CPU-only machines - the old timeout fired before the
    server was actually done starting."""
    deadline = time.time() + timeout
    health = f"{url}/api/health"
    while time.time() < deadline:
        try:
            with urlopen(health, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except (URLError, OSError):
            pass
        time.sleep(1.0)
    return False


def _check_ollama() -> None:
    """Warn (do not fail) if the local Ollama server is unreachable."""
    from backend import config  # imported after _bootstrap_paths()

    ollama_host = getattr(config, "OLLAMA_HOST", "http://localhost:11434")
    model = getattr(config, "LLM_MODEL", "qwen3:4b")
    try:
        with urlopen(f"{ollama_host}/api/tags", timeout=3) as resp:
            body = resp.read().decode("utf-8", "ignore")
        if model.split(":")[0] not in body:
            print(
                f"[warning] Ollama is running but model '{model}' was not found.\n"
                f"          Pull it once with:  ollama pull {model}\n"
                f"          (The app works now; local answers need this model.)"
            )
        else:
            print(f"[ok] Ollama reachable at {ollama_host} with '{model}'.")
    except (URLError, OSError):
        print(
            f"[warning] Could not reach Ollama at {ollama_host}.\n"
            f"          Start it (install from https://ollama.com), then run:\n"
            f"              ollama pull {model}\n"
            f"          The UI still opens; only LLM answers require Ollama.\n"
            f"          Cloud providers (with an API key) work without it."
        )


def _run_server() -> None:
    """Runs uvicorn on a background thread. webview.start() has to own the
    main thread on Windows, so uvicorn can no longer block it here like it
    did in the old browser-based launcher."""
    import uvicorn
    from backend.main import app
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


def main() -> None:
    base = _bootstrap_paths()

    from backend import config  # noqa: F401  (also creates the writable data dirs)

    _redirect_console_streams(config.DATA_HOME)

    print("=" * 60)
    print("  Multimodal Offline RAG")
    print("=" * 60)
    print(f"  Code dir : {base}")
    print(f"  Data dir : {config.DATA_HOME}")
    print(f"  URL      : {BASE_URL}")
    print("  Starting server... (first launch loads models, please wait)")
    print("=" * 60)

    threading.Thread(target=_run_server, daemon=True).start()

    if _wait_for_health(BASE_URL):
        _check_ollama()
        print(f"\n  Multimodal RAG is ready:  {BASE_URL}\n")
    else:
        print(
            f"[error] Server did not become healthy within the timeout.\n"
            f"        Opening the window anyway - try reloading if it's blank."
        )

    webview.create_window(
        "Multimodal RAG",
        BASE_URL,
        width=1280,
        height=820,
        min_size=(900, 600),
    )
    webview.start(gui="edgechromium")


if __name__ == "__main__":
    main()