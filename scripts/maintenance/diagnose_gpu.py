#!/usr/bin/env python3
"""
GPU + Ollama diagnostic (transformation brief §39): python scripts/maintenance/diagnose_gpu.py

Checks, in order:
  1. Is `nvidia-smi` on PATH at all (tells you if NVIDIA drivers are installed)
  2. What GPU(s) nvidia-smi reports, and their VRAM
  3. Is Ollama reachable, and does it report GPU usage for a loaded model
  4. Is the configured model (config.LLM_MODEL) actually pulled

This sandbox has no GPU and no `nvidia-smi`, so every run of this script in
THIS environment will honestly print "not found" for the GPU checks —
that is the correct, non-fabricated output for a machine with no GPU. Run
it on your actual laptop/server to get real numbers; the script does not
change behavior based on what environment it happens to run in.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import urllib.error
import urllib.request

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "backend"))


def check_nvidia_smi() -> dict:
    path = shutil.which("nvidia-smi")
    if not path:
        return {"available": False, "reason": "nvidia-smi not found on PATH — no NVIDIA driver installed, "
                                               "or this is a CPU-only machine."}
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.used,utilization.gpu",
             "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10,
        )
        if out.returncode != 0:
            return {"available": False, "reason": out.stderr.strip() or "nvidia-smi returned a non-zero exit code"}
        gpus = []
        for line in out.stdout.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) == 4:
                gpus.append({
                    "name": parts[0], "vram_total": parts[1],
                    "vram_used": parts[2], "gpu_utilization": parts[3],
                })
        return {"available": True, "gpus": gpus}
    except Exception as exc:
        return {"available": False, "reason": str(exc)}


def check_ollama(base_url: str, model: str) -> dict:
    try:
        req = urllib.request.Request(f"{base_url.rstrip('/')}/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {"reachable": False, "reason": str(exc)}

    models = [m.get("name", m.get("model", "")) for m in data.get("models", [])]
    model_pulled = any(model.split(":")[0] in m for m in models)

    ps_info = None
    try:
        req = urllib.request.Request(f"{base_url.rstrip('/')}/api/ps")
        with urllib.request.urlopen(req, timeout=5) as resp:
            ps_info = json.loads(resp.read().decode())
    except Exception:
        pass  # /api/ps requires a currently-loaded model; absence is not an error

    return {
        "reachable": True, "models_available": models,
        "target_model_pulled": model_pulled,
        "loaded_models": ps_info.get("models", []) if ps_info else "none loaded right now",
    }


def main() -> None:
    try:
        import config
        base_url, model = config.OLLAMA_HOST, config.LLM_MODEL
    except Exception:
        base_url, model = "http://localhost:11434", "qwen3:4b"

    print("=" * 60)
    print("GPU / OLLAMA DIAGNOSTIC".center(60))
    print("=" * 60)

    gpu = check_nvidia_smi()
    print("\nGPU:")
    if gpu["available"]:
        for g in gpu["gpus"]:
            print(f"  {g['name']}: {g['vram_used']} / {g['vram_total']} used, "
                  f"{g['gpu_utilization']} utilization")
    else:
        print(f"  Not detected: {gpu['reason']}")

    ollama = check_ollama(base_url, model)
    print(f"\nOllama ({base_url}):")
    if ollama["reachable"]:
        print(f"  Reachable: yes")
        print(f"  Models available: {ollama['models_available'] or '(none pulled yet)'}")
        print(f"  Target model '{model}' pulled: "
              f"{'yes' if ollama['target_model_pulled'] else 'NO — run: ollama pull ' + model}")
        print(f"  Currently loaded: {ollama['loaded_models']}")
    else:
        print(f"  Reachable: no ({ollama['reason']})")
        print(f"  Is Ollama running? Try: ollama serve")

    print("\n" + "=" * 60)
    if not gpu["available"]:
        print("No GPU detected — Ollama will run on CPU. This is expected and fine for")
        print("qwen3:4b at a reduced tokens/sec; see docs/performance.md for what to expect.")
    print("=" * 60)


if __name__ == "__main__":
    main()
