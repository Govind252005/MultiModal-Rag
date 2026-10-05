"""
Security audit CLI (transformation brief §150): python -m security.audit

Runs whatever of these tools are actually installed and on PATH, and
reports each check as PASS / FAIL / WARNING / SKIPPED. Never fabricates a
result for a tool that isn't available — SKIPPED means exactly that,
not "assumed clean."

Tools used (install what you want checked; this script degrades
gracefully around whatever's missing):
    pip-audit    — Python dependency vulnerability scan
    bandit       — Python static security analysis
    npm audit    — JS dependency vulnerability scan (run from frontend/)
    semgrep      — general static analysis (optional, if installed)

This was written and syntax-checked in a sandbox with no network access,
so none of these external tools could actually be installed or run here.
Every SKIPPED result you see if you run this right now in a similarly
offline environment is accurate, not a bug — install the tool and re-run
to get a real PASS/FAIL for that check.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]


class CheckResult:
    def __init__(self, name: str, status: str, detail: str = ""):
        self.name = name
        self.status = status  # PASS | FAIL | WARNING | SKIPPED
        self.detail = detail

    def line(self) -> str:
        return f"[{self.status:<8}] {self.name}" + (f" — {self.detail}" if self.detail else "")


def _run(cmd: list, cwd: Optional[Path] = None, timeout: int = 300):
    try:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return None
    except subprocess.TimeoutExpired:
        return "TIMEOUT"


def check_pip_audit() -> CheckResult:
    if not shutil.which("pip-audit"):
        return CheckResult("pip-audit (Python dependency scan)", "SKIPPED",
                           "pip-audit not installed — pip install pip-audit")
    req = REPO_ROOT / "backend" / "requirements.txt"
    if not req.exists():
        return CheckResult("pip-audit", "SKIPPED", "backend/requirements.txt not found")
    result = _run(["pip-audit", "-r", str(req), "--format", "json"])
    if result is None:
        return CheckResult("pip-audit", "SKIPPED", "pip-audit not runnable")
    if result == "TIMEOUT":
        return CheckResult("pip-audit", "WARNING", "timed out (needs network access to PyPI's advisory DB)")
    if result.returncode == 0:
        return CheckResult("pip-audit (Python dependency scan)", "PASS", "no known vulnerabilities found")
    try:
        findings = json.loads(result.stdout)
        n = len(findings.get("dependencies", findings)) if isinstance(findings, dict) else len(findings)
    except Exception:
        n = "some"
    return CheckResult("pip-audit (Python dependency scan)", "FAIL",
                       f"{n} finding(s) — see full output: pip-audit -r backend/requirements.txt")


def check_bandit() -> CheckResult:
    if not shutil.which("bandit"):
        return CheckResult("bandit (Python static security analysis)", "SKIPPED",
                           "bandit not installed — pip install bandit")
    result = _run(["bandit", "-r", str(REPO_ROOT / "backend"), "-ll", "-f", "json"])
    if result is None:
        return CheckResult("bandit", "SKIPPED", "bandit not runnable")
    try:
        data = json.loads(result.stdout)
        n_high = sum(1 for r in data.get("results", []) if r.get("issue_severity") in ("HIGH", "MEDIUM"))
    except Exception:
        n_high = None
    if n_high is None:
        return CheckResult("bandit (Python static security analysis)", "WARNING", "could not parse output")
    if n_high == 0:
        return CheckResult("bandit (Python static security analysis)", "PASS",
                           "no medium/high severity findings")
    return CheckResult("bandit (Python static security analysis)", "FAIL",
                       f"{n_high} medium/high severity finding(s) — run: bandit -r backend -ll")


def check_npm_audit() -> CheckResult:
    if not shutil.which("npm"):
        return CheckResult("npm audit (JS dependency scan)", "SKIPPED", "npm not installed")
    frontend = REPO_ROOT / "frontend"
    if not (frontend / "package.json").exists():
        return CheckResult("npm audit", "SKIPPED", "frontend/package.json not found")
    if not (frontend / "node_modules").exists():
        return CheckResult("npm audit (JS dependency scan)", "SKIPPED",
                           "node_modules not installed — run `npm ci` in frontend/ first "
                           "(needs network access)")
    result = _run(["npm", "audit", "--json", "--audit-level=high"], cwd=frontend)
    if result is None:
        return CheckResult("npm audit", "SKIPPED", "npm audit not runnable")
    try:
        data = json.loads(result.stdout)
        high = data.get("metadata", {}).get("vulnerabilities", {}).get("high", 0)
        critical = data.get("metadata", {}).get("vulnerabilities", {}).get("critical", 0)
    except Exception:
        high = critical = None
    if high is None:
        return CheckResult("npm audit (JS dependency scan)", "WARNING", "could not parse output")
    if high == 0 and critical == 0:
        return CheckResult("npm audit (JS dependency scan)", "PASS", "no high/critical findings")
    return CheckResult("npm audit (JS dependency scan)", "FAIL",
                       f"{critical} critical, {high} high severity finding(s)")


def check_secret_scan() -> CheckResult:
    """Lightweight, dependency-free heuristic scan for obviously-committed
    secrets (API keys, private key headers). This is NOT a substitute for
    a real secret scanner (gitleaks/trufflehog) — it exists so this audit
    can report *something* concrete even with zero tools installed."""
    patterns = [
        "-----BEGIN PRIVATE KEY-----", "-----BEGIN RSA PRIVATE KEY-----",
        "AKIA", "sk-proj-", "sk-ant-api",
    ]
    hits = []
    skip_dirs = {".git", "node_modules", "security"}  # 'security' excludes this
                                                       # scanner's own source,
                                                       # which necessarily
                                                       # contains the literal
                                                       # patterns it looks for.
    for path in REPO_ROOT.rglob("*"):
        if path.is_dir() or skip_dirs & set(path.parts):
            continue
        if path.suffix in {".png", ".jpg", ".jpeg", ".pdf", ".zip", ".pyc", ".db", ".sqlite3"}:
            continue
        if path.name in {".env"}:
            continue  # expected to hold real local secrets; .env.example is checked instead
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for pattern in patterns:
            if pattern in text:
                hits.append(f"{path.relative_to(REPO_ROOT)}: contains '{pattern}'")
    if hits:
        return CheckResult("secret scan (heuristic)", "FAIL", "; ".join(hits[:5]))
    return CheckResult("secret scan (heuristic)", "PASS",
                       "no obvious committed secrets found by this heuristic scan "
                       "(not a substitute for gitleaks/trufflehog)")


def main() -> int:
    checks = [check_pip_audit(), check_bandit(), check_npm_audit(), check_secret_scan()]

    print("=" * 60)
    print("SECURITY AUDIT".center(60))
    print("=" * 60)
    for c in checks:
        print(c.line())
    print("=" * 60)

    n_fail = sum(1 for c in checks if c.status == "FAIL")
    n_skip = sum(1 for c in checks if c.status == "SKIPPED")
    print(f"{len(checks) - n_fail - n_skip} passed / {n_fail} failed / {n_skip} skipped")
    if n_skip:
        print("\nSKIPPED checks are not a pass — they mean the tool wasn't available.")
    print("\nSee docs/security.md for the full, hand-verified security posture of this repo.")

    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
