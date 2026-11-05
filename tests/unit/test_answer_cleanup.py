from backend.generation import answer


def test_reasoning_draft_is_finalized_once(monkeypatch):
    calls = []

    def fake_generate(system, user, **kwargs):
        calls.append((system, user))
        return "Dr. Charu Gupta [2]"

    monkeypatch.setattr(answer.router, "generate", fake_generate)

    result = answer._finalize_answer(
        "We are given a question. We must inspect the context.",
        "Question: Who is the Faculty Supervisor?\n[2] Faculty Supervisor: Dr. Charu Gupta",
        "ollama",
        "user-1",
        "qwen3:4b",
    )

    assert result == "Dr. Charu Gupta [2]"
    assert len(calls) == 1


def test_reasoning_cannot_reach_the_user_if_finalization_still_fails():
    result = answer._enforce_clean_answer(
        "First, I need to inspect the context. The answer is incomplete."
    )

    assert result == answer.prompt_templates.MISSING_CONTEXT_MESSAGE
