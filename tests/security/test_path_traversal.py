"""
Path traversal tests (transformation brief §59/§34/§143 — named test file
"test_path_traversal" is explicitly listed in the brief's own §58 minimum
test list).

Two things are tested here, both for real against the actual source:
  1. sessions.py's `_path()` — the character-allowlist sanitization that
     turns a session_id into a filename, tested directly (this module has
     no heavy dependencies, so it imports cleanly).
  2. main.py's `_safe_join()` — the resolve()+prefix-check defense-in-
     depth helper added this pass. main.py itself can't be imported here
     (FastAPI/torch aren't installed in every environment this suite
     might run in), so this loads _safe_join's exact source text out of
     main.py and executes just that function — if main.py's
     implementation of _safe_join ever changes, this test starts running
     against the NEW code automatically (it re-reads the source every
     run), so it can't silently drift into testing a stale copy.
"""

from __future__ import annotations

import ast
import sys
import tempfile
import types
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / "backend"


def _load_safe_join():
    """Extract and exec ONLY the `_safe_join` function from main.py's
    actual source, with a minimal HTTPException stand-in (the real one
    needs `fastapi`, not installed in every environment this runs in;
    the stand-in has the same (status, detail) constructor shape, which
    is all `_safe_join` actually uses)."""
    source = (BACKEND / "main.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_safe_join":
            func_source = ast.get_source_segment(source, node)
            break
    else:
        raise AssertionError("_safe_join not found in main.py — did it get renamed/removed?")

    ns: dict = {"Path": Path}

    class HTTPException(Exception):
        def __init__(self, status_code, detail):
            self.status_code = status_code
            self.detail = detail
    ns["HTTPException"] = HTTPException

    exec(compile(func_source, "main.py::_safe_join", "exec"), ns)
    return ns["_safe_join"], HTTPException


def test_safe_join_allows_normal_paths():
    safe_join, HTTPException = _load_safe_join()
    base = Path(tempfile.mkdtemp())
    result = safe_join(base, "session123", "file.pdf")
    assert result == (base / "session123" / "file.pdf").resolve()


def test_safe_join_rejects_relative_traversal():
    safe_join, HTTPException = _load_safe_join()
    base = Path(tempfile.mkdtemp())
    raised = False
    try:
        safe_join(base, "../../../etc/passwd")
    except HTTPException:
        raised = True
    assert raised, "path traversal via ../../ was NOT rejected"


def test_safe_join_rejects_absolute_path_injection():
    safe_join, HTTPException = _load_safe_join()
    base = Path(tempfile.mkdtemp())
    raised = False
    try:
        safe_join(base, "/etc/passwd")
    except HTTPException:
        raised = True
    assert raised, "absolute-path injection was NOT rejected"


def test_safe_join_rejects_traversal_hidden_in_middle_segment():
    safe_join, HTTPException = _load_safe_join()
    base = Path(tempfile.mkdtemp())
    (base / "legit").mkdir()
    raised = False
    try:
        safe_join(base, "legit", "..", "..", "etc", "passwd")
    except HTTPException:
        raised = True
    assert raised, "traversal hidden after a legitimate-looking first segment was NOT rejected"


def _load_sessions_module(sessions_dir: Path):
    fake_config = types.ModuleType("config")
    fake_config.SESSIONS_DIR = sessions_dir
    backend_pkg = types.ModuleType("backend")
    backend_pkg.__path__ = [str(BACKEND)]
    backend_pkg.config = fake_config
    sys.modules["backend"] = backend_pkg
    sys.modules["backend.config"] = fake_config
    sys.modules["config"] = fake_config
    sys.path.insert(0, str(BACKEND))
    if "sessions" in sys.modules:
        del sys.modules["sessions"]
    import sessions
    return sessions


def test_session_id_sanitization_strips_traversal_characters():
    """sessions.py's own first line of defense: session_id is filtered
    to an alnum/-/_ allowlist before ever touching the filesystem. A
    session_id containing path-traversal characters must resolve to a
    filename INSIDE sessions_dir, never outside it."""
    sessions_dir = Path(tempfile.mkdtemp())
    sessions = _load_sessions_module(sessions_dir)

    malicious_id = "../../../etc/passwd"
    p = sessions._path(malicious_id)
    assert p.parent == sessions_dir, f"sanitized path escaped sessions_dir: {p}"
    assert ".." not in p.name
    assert "/" not in p.name


ALL_TESTS = [
    test_safe_join_allows_normal_paths,
    test_safe_join_rejects_relative_traversal,
    test_safe_join_rejects_absolute_path_injection,
    test_safe_join_rejects_traversal_hidden_in_middle_segment,
    test_session_id_sanitization_strips_traversal_characters,
]

if __name__ == "__main__":
    failed = 0
    for test in ALL_TESTS:
        try:
            test()
            print(f"PASS  {test.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL  {test.__name__}: {exc}")
    print(f"\n{len(ALL_TESTS) - failed}/{len(ALL_TESTS)} passed")
    sys.exit(1 if failed else 0)
