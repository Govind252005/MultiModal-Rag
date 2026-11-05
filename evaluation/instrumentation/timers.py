"""
High-resolution instrumentation timers for pipeline stages and ingestion benchmarking.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional


class PipelineTimer:
    """Instruments stage-wise latencies during query processing."""

    def __init__(self):
        self.stage_timings: Dict[str, float] = {}
        self._start_total: float = 0.0
        self.total_ms: float = 0.0

    def start_total(self) -> None:
        self._start_total = time.perf_counter()

    def stop_total(self) -> float:
        if self._start_total > 0:
            self.total_ms = (time.perf_counter() - self._start_total) * 1000.0
        return self.total_ms

    @contextmanager
    def measure_stage(self, stage_name: str) -> Iterator[None]:
        t0 = time.perf_counter()
        try:
            yield
        finally:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            self.stage_timings[stage_name] = round(elapsed_ms, 2)

    def record_stage(self, stage_name: str, elapsed_ms: float) -> None:
        self.stage_timings[stage_name] = round(elapsed_ms, 2)

    def get_summary(self) -> Dict[str, float]:
        summary = dict(self.stage_timings)
        if "total_query_latency" not in summary and self.total_ms > 0:
            summary["total_query_latency"] = round(self.total_ms, 2)
        return summary


@dataclass
class IngestionTimings:
    """Stores granular ingestion timings for PDF, DOCX, Image, and Audio."""
    doc_id: str
    modality: str
    total_time_ms: float
    page_count: Optional[int] = None
    time_per_page_ms: Optional[float] = None
    ocr_time_ms: Optional[float] = None
    blip_time_ms: Optional[float] = None
    clip_time_ms: Optional[float] = None
    asr_time_ms: Optional[float] = None
    audio_duration_seconds: Optional[float] = None
    real_time_factor: Optional[float] = None  # asr_time / audio_duration

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v is not None}
