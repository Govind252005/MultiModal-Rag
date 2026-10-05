"""
Experiment schemas for ablations, modality configurations, and provider evaluations.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AblationConfig:
    """Configuration for an ablation experiment variant."""
    experiment_id: str
    name: str
    description: str
    use_dense: bool = True
    use_bm25: bool = True
    use_clip: bool = True
    use_rrf: bool = True
    use_cross_encoder: bool = True
    use_semantic_chunking: bool = True
    use_ocr: bool = True
    use_audio_transcription: bool = True
    top_k: int = 5
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExperimentResult:
    """Result of an experiment (e.g. baseline or ablation)."""
    experiment_id: str
    name: str
    status: str  # "COMPLETED", "FAILED", "NOT_RUN"
    reason: Optional[str] = None
    config: Dict[str, Any] = field(default_factory=dict)
    retrieval_metrics: Dict[str, Any] = field(default_factory=dict)
    generation_metrics: Dict[str, Any] = field(default_factory=dict)
    latency_metrics: Dict[str, Any] = field(default_factory=dict)
    num_samples: int = 0
    duration_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
