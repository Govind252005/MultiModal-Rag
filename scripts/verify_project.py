"""Run the repository's safe verification checks with explicit statuses.

The default run performs local compile/tests/build/self-test checks only. Live
provider checks are opt-in and require the caller to provide the relevant
service/user prerequisites.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


ROOT = Path(__file__).resolve().parents[1]


def run_step(name: str, command: List[str], cwd: Path = ROOT, timeout: int = 900) -> Dict[str, object]:
    print(f"[{name}] RUNNING: {' '.join(command)}", flush=True)
    try:
        proc = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        result = {"name": name, "status": "FAILED", "returncode": None, "error": "timeout", "command": command}
        print(f"[{name}] FAILED: timeout", flush=True)
        return result
    status = "PASSED" if proc.returncode == 0 else "FAILED"
    if status == "FAILED":
        print(proc.stdout[-2000:], end="")
        print(proc.stderr[-2000:], end="")
    print(f"[{name}] {status}", flush=True)
    return {"name": name, "status": status, "returncode": proc.returncode, "command": command, "stdout_tail": proc.stdout[-2000:], "stderr_tail": proc.stderr[-2000:]}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run safe local verification checks for Multimodal RAG.")
    parser.add_argument("--live-ollama", action="store_true", help="Also run the live Ollama smoke test")
    parser.add_argument("--live-groq-user-id", help="Also run Groq smoke test for this local user ID")
    parser.add_argument("--session-id", action="append", dest="session_ids", help="Generate a session report for selected IDs")
    parser.add_argument("--sessions-dir", help="Session directory for session reporting")
    parser.add_argument("--regenerate", help="Existing evaluation run directory or summary.json to regenerate")
    parser.add_argument("--output", default="reports/verification/latest.json", help="Verification manifest output path")
    args = parser.parse_args(argv)

    python = sys.executable
    npm = "npm.cmd" if os.name == "nt" else "npm"
    results: List[Dict[str, object]] = []
    results.append(run_step("compile", [python, "-m", "compileall", "-q", "backend", "evaluation", "tests", "scripts"]))
    results.append(run_step("backend-verification", [python, "-m", "backend.verify_backend"]))
    results.append(run_step("python-tests", [python, "-m", "pytest", "-q", "--basetemp=.pytest-tmp/verification"]))
    results.append(run_step("frontend-build", [npm, "run", "build"], cwd=ROOT / "frontend"))
    results.append(run_step("frontend-e2e", [npm, "run", "e2e"], cwd=ROOT / "frontend", timeout=600))
    results.append(run_step("evaluation-self-test", [python, "-m", "evaluation.runner.run_eval", "--self-test"]))

    if args.session_ids or args.sessions_dir:
        command = [python, "-m", "evaluation.session_report", "--output", "reports/verification/session_report.json"]
        if args.sessions_dir:
            command += ["--sessions-dir", args.sessions_dir]
        for session_id in args.session_ids or []:
            command += ["--session-id", session_id]
        results.append(run_step("session-report", command))

    if args.regenerate:
        results.append(run_step("report-regeneration", [python, "-m", "evaluation.regenerate_report", "--input", args.regenerate, "--output", "reports/verification/regenerated"]))

    if args.live_ollama:
        results.append(run_step("ollama-live", [python, "scripts/provider_smoke.py", "--provider", "ollama"], timeout=180))
    if args.live_groq_user_id:
        results.append(run_step("groq-live", [python, "scripts/provider_smoke.py", "--provider", "groq", "--user-id", args.live_groq_user_id], timeout=180))

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "root": str(ROOT),
        "results": results,
        "status_counts": {status: sum(1 for item in results if item["status"] == status) for status in ("PASSED", "FAILED", "BLOCKED", "SKIPPED")},
    }
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    failed = [item for item in results if item["status"] == "FAILED"]
    print(f"Verification manifest: {output}")
    print(f"Result: {'FAILED' if failed else 'PASSED'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())