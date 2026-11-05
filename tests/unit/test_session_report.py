import json

from evaluation.session_report import analyze_session, build_report, render_markdown


def write_session(tmp_path, name, messages):
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps({"id": name, "owner_id": "u1", "messages": messages}), encoding="utf-8")
    return path


def test_session_report_handles_duplicates_mixed_providers_and_annotations(tmp_path):
    assistant = {
        "role": "assistant",
        "text": "Paris",
        "provider": "ollama",
        "model": "qwen3:4b",
        "citations": [{"file": "facts.pdf"}],
        "metrics": {"total_latency_ms": 20, "retrieval_ms": 5, "generation_ms": 15},
        "ts": "2026-01-01T00:00:01",
    }
    path = write_session(tmp_path, "s1", [
        {"role": "user", "text": "Capital?", "ts": "2026-01-01T00:00:00"},
        assistant,
        assistant,
        {"role": "user", "text": "Cloud?", "ts": "2026-01-01T00:00:02"},
        {"role": "assistant", "text": "London", "provider": "groq", "model": "model-x", "metrics": {"total_latency_ms": 40}},
        "malformed",
    ])

    report = analyze_session(path, {"Capital?": {"question": "Capital?", "answer": "Paris", "required_citations": ["facts.pdf"]}})

    assert report["status"] == "OK"
    assert report["counts"]["assistant_turns"] == 2
    assert report["counts"]["duplicate_messages_ignored"] == 1
    assert report["counts"]["malformed_messages"] == 1
    assert report["providers"] == {"ollama": 1, "groq": 1}
    assert report["quality"]["answer"]["exact_match"] == 1.0
    assert report["quality"]["citations"]["precision"] == 1.0
    assert report["quality"]["retrieval"]["status"] == "NOT_RUN"


def test_session_report_tolerates_invalid_json_and_empty_directory(tmp_path):
    (tmp_path / "broken.json").write_text("{", encoding="utf-8")
    report = build_report(tmp_path)
    assert report["summary"]["invalid_sessions"] == 1
    assert "INVALID" in render_markdown(report)


def test_session_report_missing_fields_are_not_scored(tmp_path):
    path = write_session(tmp_path, "empty", [{"role": "user", "text": "Question"}])
    report = analyze_session(path, {"Question": {"question": "Question"}})
    assert report["counts"]["assistant_turns"] == 0
    assert report["quality"]["answer"]["status"] == "NOT_RUN"