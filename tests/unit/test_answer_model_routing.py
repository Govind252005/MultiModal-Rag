from backend.generation import answer


def test_answer_query_passes_resolved_model_to_provider_router(monkeypatch):
    calls = {}

    monkeypatch.setattr(
        answer,
        "prepare_answer_context",
        lambda *args, **kwargs: {
            "system": "system",
            "user": "user",
            "history": [],
            "citations": [],
            "image_paths": None,
        },
    )

    def fake_generate(system, user, **kwargs):
        calls.update(kwargs)
        return "provider answer"

    monkeypatch.setattr(answer.router, "generate", fake_generate)

    result = answer.answer_query(
        "question",
        [{"id": "chunk-1", "file": "source.pdf", "snippet": "evidence"}],
        provider="groq",
        model="openai/gpt-oss-120b",
    )

    assert result["used_llm"] is True
    assert calls["provider"] == "groq"
    assert calls["model"] == "openai/gpt-oss-120b"