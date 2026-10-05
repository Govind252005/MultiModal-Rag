import json

from scripts.provider_smoke import _installed_model_names


def test_ollama_model_parser_accepts_supported_response_shapes():
    assert _installed_model_names({"models": [{"name": "qwen3:4b"}, {"model": "llama3:8b"}]}) == ["qwen3:4b", "llama3:8b"]


def test_ollama_model_parser_ignores_malformed_entries():
    assert _installed_model_names({"models": [{"digest": "x"}, "bad", None]}) == []