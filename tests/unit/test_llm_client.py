from backend.generation import llm_client


class _FakeClient:
    def __init__(self):
        self.kwargs = None

    def chat(self, **kwargs):
        self.kwargs = kwargs
        if kwargs.get("stream"):
            return iter([
                {"message": {"thinking": "private reasoning", "content": "final"}},
                {"done": True, "eval_count": 1, "prompt_eval_count": 1},
            ])
        return {
            "message": {
                "thinking": "private reasoning",
                "content": "final answer [1]",
            }
        }


def test_chat_disables_thinking_and_returns_content_only(monkeypatch):
    fake = _FakeClient()
    monkeypatch.setattr(llm_client, "_client", lambda: fake)

    result = llm_client.chat("system", "question")

    assert result == "final answer [1]"
    assert fake.kwargs["think"] is False


def test_stream_chat_discards_separate_thinking_field(monkeypatch):
    fake = _FakeClient()
    monkeypatch.setattr(llm_client, "_client", lambda: fake)

    chunks = list(llm_client.stream_chat("system", "question"))

    assert [chunk["delta"] for chunk in chunks if "delta" in chunk] == ["final"]
    assert chunks[-1]["text"] == "final"
    assert chunks[-1]["metrics"]["thinking_enabled"] is False
    assert fake.kwargs["think"] is False


def test_clean_answer_does_not_introduce_or_duplicate_svg_tokens():
    raw = "An answer with svg svg in the supplied content."

    assert llm_client.clean_answer(raw) == raw


def test_clean_answer_normalizes_clickable_citation_style():
    assert llm_client.clean_answer("CICPS3913E【1】") == "CICPS3913E[1]"


def test_clean_answer_removes_visible_reasoning_before_final_marker():
    raw = (
        "We are given a user question. We must inspect the context. "
        "Therefore, the answer is: Dr. Charu Gupta [3]"
    )

    assert llm_client.clean_answer(raw) == "Dr. Charu Gupta [3]"


def test_clean_answer_handles_common_qwen_reasoning_preamble():
    raw = (
        "Okay, let me go through the retrieved context. Looking at the context, "
        "the answer is Dr. Charu Gupta [1]"
    )

    assert llm_client.clean_answer(raw) == "Dr. Charu Gupta [1]"


def test_reasoning_markers_cover_context_explanations():
    assert llm_client._REASONING_MARKER_RE.search(
        "Wait, the context states that Faster-Whisper is used."
    )
    assert llm_client._REASONING_MARKER_RE.search(
        "The instruction says: extract only the requested title."
    )
    assert llm_client._REASONING_MARKER_RE.search(
        "First, I need to understand the question. Let me look at the context."
    )
