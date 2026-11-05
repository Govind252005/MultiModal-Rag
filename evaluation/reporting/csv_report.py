"""
CSV report generation for all evaluation dimensions (Requirement 21).
Generates:
- retrieval_metrics.csv
- generation_metrics.csv
- citation_metrics.csv
- performance_metrics.csv
- resource_metrics.csv
- modality_metrics.csv
- ingestion_metrics.csv
- ocr_metrics.csv
- audio_metrics.csv
- ablation_results.csv

Never creates empty fake files; clearly writes status = NOT_RUN with exact reason when an experiment wasn't executed.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List, Sequence


def write_csv_rows(rows: Sequence[Dict[str, Any]], out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        out_path.write_text("status,reason\nNOT_RUN,No data collected\n", encoding="utf-8")
        return out_path

    # Extract all distinct fieldnames preserving order
    fieldnames: List[str] = []
    seen = set()
    for row in rows:
        for k in row.keys():
            if k not in seen:
                seen.add(k)
                fieldnames.append(k)

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, restval="")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return out_path


def save_csv_suite(report_data: Dict[str, Any], out_dir: Path) -> None:
    metrics = report_data.get("metrics") or {}
    if hasattr(metrics, "to_dict"):
        metrics = metrics.to_dict()

    # 1. Retrieval
    ret = metrics.get("retrieval") or {}
    ret_rows = [{"metric": k, "value": v} for k, v in ret.items() if not isinstance(v, (dict, list))]
    write_csv_rows(ret_rows if ret_rows else [{"status": "NOT_RUN", "reason": "No retrieval data"}], out_dir / "retrieval_metrics.csv")

    # 2. Generation
    gen = metrics.get("generation") or {}
    gen_rows = [{"metric": k, "value": v} for k, v in gen.items() if not isinstance(v, (dict, list))]
    write_csv_rows(gen_rows if gen_rows else [{"status": "NOT_RUN", "reason": "No generation data"}], out_dir / "generation_metrics.csv")

    # 3. Citations
    cit = metrics.get("citations") or {}
    cit_rows = [{"metric": k, "value": v} for k, v in cit.items() if not isinstance(v, (dict, list))]
    write_csv_rows(cit_rows if cit_rows else [{"status": "NOT_RUN", "reason": "No citation data"}], out_dir / "citation_metrics.csv")

    # 4. Performance
    perf = metrics.get("performance") or {}
    stages = perf.get("stages", {})
    perf_rows = []
    if stages:
        for stage, p_data in stages.items():
            perf_rows.append({"stage": stage, **p_data})
    elif perf:
        for k, v in perf.items():
            if not isinstance(v, dict):
                perf_rows.append({"metric": k, "value": v})
    write_csv_rows(perf_rows if perf_rows else [{"status": "NOT_RUN", "reason": "No latency data"}], out_dir / "performance_metrics.csv")

    # 5. Resources
    res = metrics.get("resources") or {}
    res_rows = [{"metric": k, "value": v} for k, v in res.items() if not isinstance(v, (dict, list))]
    write_csv_rows(res_rows if res_rows else [{"status": "NOT_RUN", "reason": "No resource data"}], out_dir / "resource_metrics.csv")

    # 6. Modality
    mod = metrics.get("modality") or {}
    mod_items = mod.get("modalities", {})
    mod_rows = []
    if mod_items:
        for m_name, m_data in mod_items.items():
            mod_rows.append({"modality": m_name, **m_data})
    else:
        mod_rows = [{"status": mod.get("status", "NOT_RUN"), "reason": mod.get("reason", "Dataset lacks multi-modality balance")}]
    write_csv_rows(mod_rows, out_dir / "modality_metrics.csv")

    # 7. Ingestion
    ingest = metrics.get("ingestion") or {}
    ingest_rows = ingest.get("samples") or [{"status": ingest.get("status", "NOT_RUN"), "reason": ingest.get("reason", "Ingestion benchmark not executed in query evaluation run")}]
    write_csv_rows(ingest_rows, out_dir / "ingestion_metrics.csv")

    # 8. OCR
    ocr = metrics.get("ocr") or {}
    ocr_rows = ocr.get("results") or [{"status": ocr.get("status", "NOT_RUN"), "reason": ocr.get("reason", "OCR benchmark dataset pending ground-truth transcriptions")}]
    write_csv_rows(ocr_rows, out_dir / "ocr_metrics.csv")

    # 9. Audio
    audio = metrics.get("audio") or {}
    audio_rows = audio.get("results") or [{"status": audio.get("status", "NOT_RUN"), "reason": audio.get("reason", "Audio benchmark dataset pending human-verified recordings")}]
    write_csv_rows(audio_rows, out_dir / "audio_metrics.csv")

    # 10. Ablation
    ablation = metrics.get("ablation") or {}
    ablation_rows = ablation.get("experiments") or [{"status": ablation.get("status", "NOT_RUN"), "reason": ablation.get("reason", "Ablation experiments not requested in this run")}]
    write_csv_rows(ablation_rows, out_dir / "ablation_results.csv")
