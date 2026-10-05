"""
Result schemas for per-question outputs, aggregate metrics, and experiment records.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class QuestionResult:
    """Individual question evaluation result."""
    question_id: str
    question: str
    category: str
    modality: str
    answerable: bool
    ground_truth_answer: str
    generated_answer: Optional[str] = None
    retrieved_chunk_ids: List[str] = field(default_factory=list)
    relevant_chunk_ids: List[str] = field(default_factory=list)
    required_citations: List[str] = field(default_factory=list)
    cited_files: List[str] = field(default_factory=list)
    retrieval_hit: Optional[bool] = None
    reciprocal_rank: Optional[float] = None
    average_precision: Optional[float] = None
    precision_at_k: Dict[int, float] = field(default_factory=dict)
    recall_at_k: Dict[int, float] = field(default_factory=dict)
    f1_at_k: Dict[int, float] = field(default_factory=dict)
    ndcg_at_k: Dict[int, float] = field(default_factory=dict)
    answer_correctness: Optional[float] = None
    answer_relevance: Optional[float] = None
    faithfulness: Optional[float] = None
    faithfulness_warning: bool = False
    citation_present: bool = False
    citation_precision: Optional[float] = None
    claim_accuracy: Optional[float] = None
    citation_completeness: Optional[float] = None
    correctly_abstained: Optional[bool] = None
    latency_ms: Optional[float] = None
    stage_latencies_ms: Dict[str, float] = field(default_factory=dict)
    used_llm: bool = False
    error: Optional[str] = None
    error_type: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AggregateMetrics:
    """Consolidated aggregate metrics for a run."""
    retrieval: Dict[str, Any] = field(default_factory=dict)
    generation: Dict[str, Any] = field(default_factory=dict)
    citations: Dict[str, Any] = field(default_factory=dict)
    performance: Dict[str, Any] = field(default_factory=dict)
    resources: Dict[str, Any] = field(default_factory=dict)
    modality: Dict[str, Any] = field(default_factory=dict)
    ocr: Dict[str, Any] = field(default_factory=dict)
    audio: Dict[str, Any] = field(default_factory=dict)
    ablation: Dict[str, Any] = field(default_factory=dict)
    ingestion: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RunSummary:
    """Full execution summary containing metadata, config, results, and metrics."""
    run_id: str
    timestamp: str
    provider: str
    model: str
    dataset_path: str
    dataset_hash: str
    num_questions: int
    num_errors: int
    config: Dict[str, Any]
    environment: Dict[str, Any]
    metrics: AggregateMetrics
    failures: List[Dict[str, Any]] = field(default_factory=list)
    raw_results: List[Dict[str, Any]] = field(default_factory=list)
    report_dir: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d
