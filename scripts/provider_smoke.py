"""Safe live provider diagnostics using the application's provider registry.

Examples (from repository root):
    python scripts/provider_smoke.py --provider ollama
    python scripts/provider_smoke.py --provider groq --user-id <authenticated-user-id>

The Groq path reads the encrypted key for the supplied local user ID. It never
accepts a key on the command line and never prints credentials or prompts.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def _ollama_tags() -> Dict[str, Any]:
    from backend import config
    with urlopen(f"{config.OLLAMA_HOST.rstrip('/')}/api/tags", timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _installed_model_names(tags: Dict[str, Any]) -> list[str]:
    names = []
    for item in tags.get("models", []) or []:
        if isinstance(item, dict):
            name = item.get("name") or item.get("model")
            if name:
                names.append(str(name))
    return names


def smoke(provider_name: str, user_id: Optional[str], model: Optional[str]) -> Dict[str, Any]:
    from backend import config, keystore
    from backend.generation.providers.registry import registry

    started = time.perf_counter()
    result: Dict[str, Any] = {
        "provider": provider_name,
        "configured_model": config.LLM_MODEL if provider_name == "ollama" else config.GROQ_MODEL,
        "status": "FAILED",
        "error": None,
    }

    if provider_name == "ollama":
        result["executable"] = bool(shutil.which("ollama"))
        try:
            tags = _ollama_tags()
            installed = _installed_model_names(tags)
            target = model or config.LLM_MODEL
            result["installed_models"] = installed
            result["model_available"] = any(name == target or name.split(":", 1)[0] == target.split(":", 1)[0] for name in installed)
            if not result["model_available"]:
                result["error"] = f"Configured model '{target}' is not installed. Pull it explicitly with: ollama pull {target}"
                return result
        except (OSError, URLError, ValueError) as exc:
            result["error"] = f"Ollama is not reachable at {config.OLLAMA_HOST}: {type(exc).__name__}"
            return result
    elif provider_name == "groq":
        if not user_id:
            result["error"] = "--user-id is required for Groq because keys are stored per authenticated user."
            return result
        key = keystore.get_key(user_id, "groq")
        if not key:
            result["error"] = "No encrypted Groq key is stored for this user. Add and validate it through the provider settings workflow."
            return result
        provider = registry.get("groq")
        try:
            models = provider.get_model_list(user_id=user_id)
            result["available_models"] = [item.get("id") for item in models if isinstance(item, dict) and item.get("id")]
            if not provider.validate_api_key(key):
                result["error"] = "Stored Groq credential was rejected by the provider."
                return result
        except Exception as exc:
            result["error"] = f"Groq validation failed: {type(exc).__name__}"
            return result
    else:
        result["error"] = f"Unsupported provider: {provider_name}"
        return result

    provider = registry.get(provider_name)
    target_model = model or (config.LLM_MODEL if provider_name == "ollama" else config.GROQ_MODEL)
    try:
        answer = provider.generate_answer(
            "Reply briefly and do not include secrets.",
            "Reply with exactly: provider-smoke-ok",
            user_id=user_id,
            model=target_model,
        )
        result["model"] = target_model
        result["nonempty_response"] = bool(answer and answer.strip())
        result["status"] = "PASSED" if result["nonempty_response"] else "FAILED"
        if not result["nonempty_response"]:
            result["error"] = "Provider returned an empty response."
    except Exception as exc:
        result["error"] = f"Generation failed: {type(exc).__name__}"
    finally:
        result["latency_ms"] = round((time.perf_counter() - started) * 1000, 1)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a minimal live provider smoke test without logging secrets.")
    parser.add_argument("--provider", choices=("ollama", "groq"), required=True)
    parser.add_argument("--user-id", help="Authenticated local user ID for encrypted Groq key lookup")
    parser.add_argument("--model", help="Explicit model; defaults to backend configuration")
    args = parser.parse_args()
    result = smoke(args.provider, args.user_id, args.model)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())