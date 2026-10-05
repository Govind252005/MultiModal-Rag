"""Install the unified evaluation ZIP as the project's canonical corpus.

The migration is intentionally explicit and reversible: existing corpus files
and root dataset JSON files are copied to a timestamped backup before the
replacement happens. Only formats supported by the current ingestion design
(PDF, DOCX, images, and audio clips) are copied into the ingest corpus.
"""

from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List


EXTRA_QUESTIONS: List[Dict[str, Any]] = [
    {"question_id": "EXTRA-001", "question": "What was the Q1 2026 operating cost?", "answer": "$278,000", "category": "numerical", "modality": "text", "source_file": "01_quarterly_finance_summary.pdf"},
    {"question_id": "EXTRA-002", "question": "What was the Q3 2026 operating cost?", "answer": "$316,000", "category": "numerical", "modality": "text", "source_file": "01_quarterly_finance_summary.pdf"},
    {"question_id": "EXTRA-003", "question": "By how much did revenue increase from Q1 to Q2 2026?", "answer": "$48,000", "category": "comparison", "modality": "tabular", "source_file": "01_quarterly_finance_summary.pdf"},
    {"question_id": "EXTRA-004", "question": "By how much did operating cost increase from Q2 to Q3 2026?", "answer": "$15,000", "category": "comparison", "modality": "tabular", "source_file": "01_quarterly_finance_summary.pdf"},
    {"question_id": "EXTRA-005", "question": "How many support tickets were resolved from July through September combined?", "answer": "3,955 tickets", "category": "numerical", "modality": "tabular", "source_file": "02_operations_service_targets.pdf"},
    {"question_id": "EXTRA-006", "question": "How many inventory units were lost between the start and end of September?", "answer": "48 units", "category": "numerical", "modality": "tabular", "source_file": "02_operations_service_targets.pdf"},
    {"question_id": "EXTRA-007", "question": "How many onboarding sessions did not result in a completed onboarding?", "answer": "54 sessions", "category": "numerical", "modality": "text", "source_file": "01_product_release_brief.docx"},
    {"question_id": "EXTRA-008", "question": "How much did customer satisfaction improve from August to September?", "answer": "It improved by 0.2 points, from 4.2 to 4.4 out of 5.", "category": "comparison", "modality": "tabular", "source_file": "01_product_release_brief.docx"},
    {"question_id": "EXTRA-009", "question": "How many accessibility issues were found in total?", "answer": "10 issues: 7 keyboard-navigation issues and 3 contrast issues.", "category": "numerical", "modality": "text", "source_file": "01_product_release_brief.docx"},
    {"question_id": "EXTRA-010", "question": "How much higher was September training attendance than August attendance?", "answer": "7 employees", "category": "comparison", "modality": "tabular", "source_file": "02_people_and_training_update.docx"},
    {"question_id": "EXTRA-011", "question": "How many fewer defects were recorded in Sprint 15 than Sprint 14?", "answer": "9 fewer defects", "category": "comparison", "modality": "tabular", "source_file": "03_engineering_sprint_report.docx"},
    {"question_id": "EXTRA-012", "question": "How long is the database backup retention window?", "answer": "30 days", "category": "factual", "modality": "text", "source_file": "04_security_and_reliability_standard.docx"},
    {"question_id": "EXTRA-013", "question": "How many controls are required before a production release?", "answer": "Three: a passing smoke test, an approved change ticket, and a rollback plan.", "category": "multi-hop", "modality": "text", "source_file": "03_data_governance_rules.pdf"},
    {"question_id": "EXTRA-014", "question": "What two actions are required for a data export request?", "answer": "Workspace-owner approval and logging in the audit register.", "category": "factual", "modality": "text", "source_file": "03_data_governance_rules.pdf"},
    {"question_id": "EXTRA-015", "question": "What metric is reported as secondary to macro-F1?", "answer": "Accuracy", "category": "factual", "modality": "text", "source_file": "04_evaluation_benchmark_notes.pdf"},
    {"question_id": "EXTRA-016", "question": "Which image contains the daily summary refresh time?", "answer": "The backup schedule card image, refreshed at 06:30 IST.", "category": "image", "modality": "image", "source_file": "03_backup_schedule_card.png"},
    {"question_id": "EXTRA-017", "question": "What revenue and operating cost are written on OCR page 1?", "answer": "Q1 revenue was $420,000 and operating cost was $278,000.", "category": "factual", "modality": "ocr", "source_file": "ocr_page_01.png"},
    {"question_id": "EXTRA-018", "question": "How many users completed onboarding according to OCR page 8?", "answer": "186 users", "category": "numerical", "modality": "ocr", "source_file": "ocr_page_08.png"},
    {"question_id": "EXTRA-019", "question": "What Q1 revenue is stated in audio clip 01?", "answer": "$420,000", "category": "numerical", "modality": "audio", "source_file": "audio_01.wav"},
    {"question_id": "EXTRA-020", "question": "What backup schedule is stated in audio clip 07?", "answer": "Daily at 02:00 IST", "category": "factual", "modality": "audio", "source_file": "audio_07.wav"},
    {"question_id": "EXTRA-021", "question": "Which classification metric is stated in audio clip 08?", "answer": "Macro-F1", "category": "factual", "modality": "audio", "source_file": "audio_08.wav"},
    {"question_id": "EXTRA-022", "question": "What monthly availability target is stated in audio clip 12?", "answer": "99.5% per calendar month", "category": "factual", "modality": "audio", "source_file": "audio_12.wav"},
    {"question_id": "EXTRA-023", "question": "Which quarter had both the highest revenue and the highest operating cost?", "answer": "Q3 2026, with $492,000 revenue and $316,000 operating cost.", "category": "multi-hop", "modality": "tabular", "source_file": "01_quarterly_finance_summary.pdf"},
    {"question_id": "EXTRA-024", "question": "What support target applies to the month with 1,405 resolved tickets?", "answer": "First response within 4 business hours.", "category": "multi-hop", "modality": "text", "source_file": "02_operations_service_targets.pdf"},
    {"question_id": "EXTRA-025", "question": "How does September training attendance compare with the 186 completed onboardings?", "answer": "September training attendance was 41 employees, which is 145 fewer than completed onboardings.", "category": "comparison", "modality": "cross-modal", "source_file": "02_people_and_training_update.docx"},
    {"question_id": "EXTRA-026", "question": "What is the combined number of defects across Sprint 14 and Sprint 15?", "answer": "47 defects", "category": "numerical", "modality": "tabular", "source_file": "03_engineering_sprint_report.docx"},
    {"question_id": "EXTRA-027", "question": "What was Northstar's exact Q4 2026 net profit?", "answer": "The available Northstar corpus does not provide the exact Q4 2026 net profit.", "category": "unanswerable", "modality": "text", "source_file": None},
    {"question_id": "EXTRA-028", "question": "Which employee received the highest individual salary in September?", "answer": "The available Northstar corpus does not provide individual salary information.", "category": "unanswerable", "modality": "text", "source_file": None},
]


def _basename(path: str | None) -> str | None:
    if not path or str(path).strip().lower() in {"none", "null"}:
        return None
    basename = Path(path).name
    return None if basename.lower() in {"none", "null"} else basename


def _normalise(item: Dict[str, Any], source_file: str | None = None) -> Dict[str, Any]:
    answer = item.get("answer", item.get("expected_answer"))
    source = _basename(source_file if source_file is not None else item.get("source_file"))
    return {
        "id": item.get("id", item["question_id"]),
        "question_id": item["question_id"],
        "question": item["question"],
        "answer": answer or "",
        "expected_answer": answer,
        "answerable": bool(item.get("answerable", item.get("category") != "unanswerable")),
        "difficulty": item.get("difficulty", "basic"),
        "category": item.get("category", "factual"),
        "modality": item.get("modality", "text"),
        "source_file": source,
        "source_locator": item.get("source_locator"),
        "relevant_document_ids": [source] if source else [],
        "relevant_chunk_ids": list(item.get("relevant_chunk_ids") or []),
        "required_citations": [source] if source else [],
        "sensitive": bool(item.get("sensitive", False)),
        "notes": item.get("notes"),
        "ground_truth_status": item.get("ground_truth_status", "candidate_reference"),
    }


def _copy_members(z: zipfile.ZipFile, names: Iterable[str], source_prefix: str, target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    for name in names:
        if not name.startswith(source_prefix) or name.endswith("/"):
            continue
        relative = Path(name).relative_to(source_prefix)
        if len(relative.parts) != 1:
            continue
        destination = target_dir / relative.name
        with z.open(name) as source, destination.open("wb") as target:
            shutil.copyfileobj(source, target)


def migrate(zip_path: Path, project_root: Path) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = project_root / "backups" / f"unified_evaluation_migration_{timestamp}"
    backup.mkdir(parents=True, exist_ok=False)
    corpus_dir = project_root / "evaluation" / "corpus"
    datasets_dir = project_root / "evaluation" / "datasets"
    if corpus_dir.exists():
        shutil.copytree(corpus_dir, backup / "corpus")
    for path in datasets_dir.glob("*.json"):
        shutil.copy2(path, backup / path.name)

    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
        canonical = json.loads(archive.read("ground_truth/primary_190q/real_rag_eval_dataset_v1_190q_eval(1).json"))
        addon = json.loads(archive.read("ground_truth/addon_northstar/addon_qa_ground_truth.json"))["questions"]
        supported = (".pdf", ".docx", ".png", ".jpg", ".jpeg", ".wav", ".mp3", ".m4a")
        if corpus_dir.exists():
            shutil.rmtree(corpus_dir)
        for folder in ("pdf", "docx", "images", "audio"):
            (corpus_dir / folder).mkdir(parents=True, exist_ok=True)
        _copy_members(archive, names, "corpus/existing_corpus/pdf/", corpus_dir / "pdf")
        _copy_members(archive, names, "corpus/existing_corpus/docx/", corpus_dir / "docx")
        _copy_members(archive, names, "corpus/existing_corpus/images/", corpus_dir / "images")
        _copy_members(archive, names, "corpus/addon_northstar/pdf/", corpus_dir / "pdf")
        _copy_members(archive, names, "corpus/addon_northstar/docx/", corpus_dir / "docx")
        _copy_members(archive, names, "corpus/addon_northstar/images/", corpus_dir / "images")
        _copy_members(archive, names, "audio/clips/", corpus_dir / "audio")
        _copy_members(archive, names, "ocr/images/", corpus_dir / "images")

        questions = [_normalise(item) for item in canonical]
        questions.extend(_normalise(item, item.get("source_file")) for item in addon)
        questions.extend(_normalise(item) for item in EXTRA_QUESTIONS)
        if len(questions) != 250:
            raise RuntimeError(f"Expected 250 questions, built {len(questions)}")
        if len({item["question_id"] for item in questions}) != 250:
            raise RuntimeError("Question IDs are not unique")
        valid_categories = {"factual", "multi-hop", "comparison", "numerical", "table", "summarization", "image", "audio", "cross-modal", "unanswerable", "adversarial"}
        invalid = sorted({item["category"] for item in questions} - valid_categories)
        if invalid:
            raise RuntimeError(f"Invalid categories: {invalid}")
        corpus_files = {p.name for p in corpus_dir.rglob("*") if p.is_file()}
        missing = sorted({item["source_file"] for item in questions if item["source_file"] and item["source_file"] not in corpus_files})
        if missing:
            raise RuntimeError(f"Dataset sources missing from corpus: {missing}")

        for old in ("real_rag_eval_dataset_v1_190q.json", "real_rag_eval_dataset_v1_190q_eval.json", "real_rag_eval_dataset_v1_190q_eval.backup.json", "real_rag_eval_dataset_v1_190q_groundtruth.json", "real_rag_eval_groundtruth_report.json", "rag_test_dataset.json"):
            path = datasets_dir / old
            if path.exists():
                path.unlink()
        (datasets_dir / "rag_test_dataset.json").write_text(json.dumps(questions, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        ocr_dir = datasets_dir / "ocr"
        audio_dir = datasets_dir / "audio"
        ocr_dir.mkdir(exist_ok=True)
        audio_dir.mkdir(exist_ok=True)
        ocr_cases = []
        for index in range(1, 13):
            image = f"ocr_page_{index:02d}.png"
            reference = archive.read(f"ocr/reference_text/ocr_page_{index:02d}.txt").decode("utf-8").strip()
            ocr_cases.append({"sample_id": f"ocr-{index:03d}", "image_path": f"evaluation/corpus/images/{image}", "ground_truth_transcription": reference, "document_type": "scanned", "language": "en", "verified_by_human": False, "metadata": {"source": "unified_rag_metrics_testing_package", "verification_required": True}})
        audio_cases = []
        for index in range(1, 13):
            clip = f"audio_{index:02d}.wav"
            reference = archive.read(f"audio/transcripts/audio_{index:02d}.txt").decode("utf-8").strip()
            audio_cases.append({"sample_id": f"audio-{index:03d}", "audio_path": f"evaluation/corpus/audio/{clip}", "ground_truth_transcript": reference, "condition": "clean", "duration_seconds": 0.0, "language": "en", "verified_by_human": False, "metadata": {"source": "unified_rag_metrics_testing_package", "verification_required": True}})
        (ocr_dir / "ocr_eval_benchmark.json").write_text(json.dumps(ocr_cases, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        (audio_dir / "audio_eval_benchmark.json").write_text(json.dumps(audio_cases, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        (datasets_dir / "unified_corpus_manifest.json").write_text(archive.read("evaluation/manifests/unified_corpus_manifest.json").decode("utf-8"), encoding="utf-8")
        (datasets_dir / "modality_test_cases.json").write_text(archive.read("evaluation/modality/modality_test_cases.json").decode("utf-8"), encoding="utf-8")
        (datasets_dir / "ablation_paired_cases.json").write_text(archive.read("evaluation/ablation/cases/paired_ablation_cases.json").decode("utf-8"), encoding="utf-8")
    return backup


def main() -> int:
    parser = argparse.ArgumentParser(description="Replace the project evaluation corpus with the unified ZIP package.")
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    backup = migrate(args.zip, args.project_root)
    print(json.dumps({"status": "completed", "backup": str(backup), "corpus": str(args.project_root / 'evaluation' / 'corpus'), "dataset": str(args.project_root / 'evaluation' / 'datasets' / 'rag_test_dataset.json'), "question_count": 250}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())