"""
Unit tests for Cloud Providers (Claude, OpenAI, Groq, Gemini) API key verification,
dynamic model listing, and runtime answer model activation.
"""

from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from backend.generation.providers import registry
from backend.generation.providers.cloud_providers import OpenAIProvider, ClaudeProvider, GroqProvider
from backend.generation.providers.gemini_provider import GeminiProvider
from backend.generation import active_provider
from backend.main import app


@pytest.fixture
def test_client():
    return TestClient(app)


def test_cloud_providers_registered():
    """Verify that all four required cloud providers and local ollama are present."""
    names = registry.names()
    for prov in ("ollama", "gemini", "openai", "claude", "groq"):
        assert prov in names, f"Provider '{prov}' must be registered."


def test_openai_model_list_and_validation():
    prov = OpenAIProvider()
    assert len(prov.DEFAULT_MODELS) >= 5

    # Fallback when no key is set
    models = prov.get_model_list(user_id="nonexistent_user")
    assert any(m["id"] == "gpt-4o" for m in models)
    assert any(m["id"] == "gpt-4o-mini" for m in models)

    # Validation failure on invalid key
    assert prov.validate_api_key("invalid-sk-key") is False


def test_claude_model_list_and_validation():
    prov = ClaudeProvider()
    assert len(prov.DEFAULT_MODELS) >= 4

    # Fallback when no key is set
    models = prov.get_model_list(user_id="nonexistent_user")
    assert any("claude-3-5-sonnet" in m["id"] for m in models)
    assert any("claude-3-5-haiku" in m["id"] for m in models)

    # Validation failure on invalid key
    assert prov.validate_api_key("invalid-anthropic-key") is False


def test_groq_model_list_and_validation():
    prov = GroqProvider()
    assert len(prov.DEFAULT_MODELS) >= 5

    # Fallback when no key is set
    models = prov.get_model_list(user_id="nonexistent_user")
    assert any("llama-3.3-70b" in m["id"] for m in models)
    assert any("llama-3.1-8b" in m["id"] for m in models)

    # Validation failure on invalid key
    assert prov.validate_api_key("invalid-groq-key") is False


def test_gemini_model_list_and_validation():
    prov = GeminiProvider()
    assert len(prov.DEFAULT_MODELS) >= 4

    # Fallback when no key is set
    models = prov.get_model_list(user_id="nonexistent_user")
    assert any("gemini-2.0-flash" in m["id"] for m in models)
    assert any("gemini-1.5-flash" in m["id"] for m in models)

    # Validation failure on invalid key
    assert prov.validate_api_key("invalid-gemini-key") is False


def test_active_provider_model_selection():
    """Verify that an explicit custom model can be set and retrieved per user."""
    user_id = "test_user_phase7"
    active_provider.set_active(user_id, "openai", model="gpt-4o")
    info = active_provider.get_active_full(user_id)
    assert info["provider"] == "openai"
    assert info["model"] == "gpt-4o"
    assert info["mode"] == "cloud"

    # Switching back to local resets to Ollama LLM model
    active_provider.set_active(user_id, "ollama")
    info_local = active_provider.get_active_full(user_id)
    assert info_local["provider"] == "ollama"
    assert info_local["mode"] == "local"
