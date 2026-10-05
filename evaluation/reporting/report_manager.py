"""
Report Manager: manages output directories, file paths, and report lifecycle.
Ensures standard structure:
reports/evaluation/<provider>/<timestamp>/
reports/evaluation/comparison/<timestamp>/
reports/evaluation/ablation/<timestamp>/
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional
from evaluation.utils.reproducibility import generate_run_id


class ReportManager:
    """Handles report directory creation and artifact routing."""

    def __init__(
        self,
        base_reports_dir: str | Path = "reports/evaluation",
        category: str = "ollama",
        timestamp: Optional[str] = None,
    ):
        self.base_dir = Path(base_reports_dir)
        self.category = category.lower()
        self.timestamp = timestamp or generate_run_id()
        self.run_dir = self.base_dir / self.category / self.timestamp
        self.graphs_dir = self.run_dir / "graphs"
        self.tables_dir = self.run_dir / "paper_tables"

    def initialize_directories(self) -> Path:
        """Creates the required directory tree."""
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.graphs_dir.mkdir(parents=True, exist_ok=True)
        self.tables_dir.mkdir(parents=True, exist_ok=True)
        return self.run_dir

    def get_path(self, filename: str) -> Path:
        return self.run_dir / filename

    def get_graph_path(self, filename: str) -> Path:
        return self.graphs_dir / filename

    def get_table_path(self, filename: str) -> Path:
        return self.tables_dir / filename
