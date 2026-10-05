import json

from evaluation.regenerate_report import regenerate


def test_regenerate_report_preserves_saved_evidence_without_inference(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    summary = {
        "run_id": "run-1",
        "provider": "ollama",
        "model": "qwen3:4b",
        "num_questions": 1,
        "num_errors": 0,
        "metrics": {"retrieval": {"mrr": 1.0}},
        "failures": [],
    }
    raw = [{"question_id": "q1", "generated_answer": "answer"}]
    (source / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    (source / "raw_results.json").write_text(json.dumps(raw), encoding="utf-8")

    output = tmp_path / "regenerated"
    report = regenerate(source, output)

    assert report["regeneration"]["providers_called"] is False
    assert report["regeneration"]["inference_rerun"] is False
    assert json.loads((output / "raw_results.json").read_text(encoding="utf-8")) == raw
    assert (output / "summary.json").is_file()
    assert (output / "summary.md").is_file()