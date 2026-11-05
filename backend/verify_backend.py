"""
Verification script — run from backend/:  python test_verify.py
"""
import sys, os, types, tempfile, pathlib

# ── stub config (avoids torch import) ────────────────────────────────────────
from backend import config as cfg

for mod in ["ollama", "google", "google.genai", "google.genai.types",
            "openai", "anthropic", "groq"]:
    sys.modules.setdefault(mod, types.ModuleType(mod))

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── 1. Fernet roundtrip ───────────────────────────────────────────────────────
with tempfile.TemporaryDirectory() as td:
    cfg.PROVIDER_KEYS_FILE = pathlib.Path(td) / "provider_keys.json"
    cfg.KEYS_SECRET_FILE   = pathlib.Path(td) / "keys.secret"
    from backend import keystore
    keystore._fernet = None
    keystore.set_key("u1", "gemini", "sk-abc")
    assert keystore.get_key("u1", "gemini") == "sk-abc", "roundtrip failed"
    assert "sk-abc" not in cfg.PROVIDER_KEYS_FILE.read_text(), "plaintext on disk"
    assert keystore.get_key("u2", "gemini") is None, "user isolation broken"
    keystore.delete_key("u1", "gemini")
    assert keystore.get_key("u1", "gemini") is None, "delete failed"
    print("[ok] keystore: roundtrip, encryption-at-rest, isolation, delete")

# ── 2. Registry ───────────────────────────────────────────────────────────────
from backend.generation.providers.registry import ProviderRegistry
names = ProviderRegistry().names()
assert set(names) == {"ollama", "gemini", "openai", "claude", "groq"}, names
print(f"[ok] registry: {names}")

# ── 3. Router default ─────────────────────────────────────────────────────────
from backend.generation.providers.router import Router
assert Router().get_provider().name == "ollama"
print("[ok] router: default = ollama")

# ── 4. answer.py signatures ───────────────────────────────────────────────────
import inspect

llm_stub = types.ModuleType("generation.llm_client")
class _E(RuntimeError): pass
llm_stub.LLMError = _E
llm_stub.chat = lambda *a, **kw: ""
llm_stub.stream_chat = lambda *a, **kw: iter([])
sys.modules["generation.llm_client"] = llm_stub

pt = types.ModuleType("generation.prompt_templates")
pt.SYSTEM_PROMPT = pt.ENTITY_EXTRACTION_PROMPT = pt.SUMMARY_PROMPT = ""
pt.build_user_prompt = pt.build_context = lambda *a: ""
sys.modules["generation.prompt_templates"] = pt

# Provide a generation.providers stub that exposes a .router attribute
# so `from generation.providers import router` in answer.py resolves cleanly.
prov_pkg = types.ModuleType("generation.providers")
rmod = types.ModuleType("generation.providers.router")
class _R:
    def generate(self, s, u, history=None, provider=None, user_id=None, image_paths=None, model=None):
        return ""
rmod.router = _R()
prov_pkg.router = rmod.router
sys.modules["generation.providers"] = prov_pkg
sys.modules["generation.providers.router"] = rmod

sys.modules.pop("generation.answer", None)
import backend.generation.answer as ans
for fn in ("answer_query", "extract_entities", "summarize_document"):
    params = list(inspect.signature(getattr(ans, fn)).parameters)
    assert "provider" in params and "user_id" in params, \
        f"missing params in {fn}: {params}"
print("[ok] answer.py: provider + user_id in all three functions")

print("\nAll checks passed.")
