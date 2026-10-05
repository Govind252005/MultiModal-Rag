"""
Schemas for evaluation datasets (QA, OCR, Audio, Modality).
Provides strict validation and serialization for research reproducibility.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class QADatasetItem:
    """Represents a single question in the RAG evaluation dataset."""
    id: str
    question: str
    answer: str
    answerable: bool = True
    difficulty: str = "basic"
    category: str = "factual"
    modality: str = "text"
    source_file: Optional[str] = None
    source_locator: Optional[str] = None
    relevant_document_ids: List[str] = field(default_factory=list)
    relevant_chunk_ids: List[str] = field(default_factory=list)
    required_citations: List[str] = field(default_factory=list)
    sensitive: bool = False
    notes: Optional[str] = None
    ground_truth_status: str = "confident"
    question_id: Optional[str] = None

    def __post_init__(self):
        if not self.question_id:
            self.question_id = self.id
        if not self.id:
            self.id = self.question_id

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> QADatasetItem:
        return cls(
            id=data.get("id") or data.get("question_id", ""),
            question=data["question"],
            answer=data.get("answer", ""),
            answerable=bool(data.get("answerable", True)),
            difficulty=data.get("difficulty", "basic"),
            category=data.get("category", "factual"),
            modality=data.get("modality", "text"),
            source_file=data.get("source_file"),
            source_locator=data.get("source_locator"),
            relevant_document_ids=list(data.get("relevant_document_ids") or []),
            relevant_chunk_ids=list(data.get("relevant_chunk_ids") or []),
            required_citations=list(data.get("required_citations") or []),
            sensitive=bool(data.get("sensitive", False)),
            notes=data.get("notes"),
            ground_truth_status=data.get("ground_truth_status", "confident"),
            question_id=data.get("question_id") or data.get("id"),
        )


@dataclass
class OCRBenchmarkItem:
    """Represents an item in an OCR evaluation benchmark."""
    sample_id: str
    image_path: str
    ground_truth_transcription: str
    document_type: str = "document"  # document, scanned, receipt, handwritten, chart
    language: str = "en"
    verified_by_human: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> OCRBenchmarkItem:
        return cls(
            sample_id=data["sample_id"],
            image_path=data["image_path"],
            ground_truth_transcription=data["ground_truth_transcription"],
            document_type=data.get("document_type", "document"),
            language=data.get("language", "en"),
            verified_by_human=bool(data.get("verified_by_human", True)),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass
class AudioBenchmarkItem:
    """Represents an item in an Audio ASR evaluation benchmark."""
    sample_id: str
    audio_path: str
    ground_truth_transcript: str
    condition: str = "clean"  # clean, noisy, overlapping
    duration_seconds: float = 0.0
    language: str = "en"
    verified_by_human: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AudioBenchmarkItem:
        return cls(
            sample_id=data["sample_id"],
            audio_path=data["audio_path"],
            ground_truth_transcript=data["ground_truth_transcript"],
            condition=data.get("condition", "clean"),
            duration_seconds=float(data.get("duration_seconds", 0.0)),
            language=data.get("language", "en"),
            verified_by_human=bool(data.get("verified_by_human", True)),
            metadata=dict(data.get("metadata") or {}),
        )


def load_qa_dataset(path: str | Path) -> List[QADatasetItem]:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"QA dataset not found: {p}")
    with p.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, list):
        raise ValueError(f"Expected a JSON list of items, got {type(raw)}")
    return [QADatasetItem.from_dict(item) for item in raw]
