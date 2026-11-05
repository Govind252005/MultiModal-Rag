"""
IDOR / broken access control tests (transformation brief §59, listed
alongside "test_path_traversal" in the brief's own §58 minimum test
list; also directly exercises §22's multi-tenant isolation test matrix:
"User A -> own session -> success; User B -> User A's session -> deny").

Tests the REAL sessions.py::owns() function — this module has no heavy
dependencies, so it imports directly rather than needing the
extract-and-exec technique test_path_traversal.py uses for main.py.
"""

from __future__ import annotations

import sys
import tempfile
import types
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / "backend"


def _load_sessions_module():
    sessions_dir = Path(tempfile.mkdtemp())
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


def test_owner_can_access_own_session():
    sessions = _load_sessions_module()
    s = sessions.create_session("userA", "My chat")
    assert sessions.owns(s["id"], "userA") is True


def test_other_user_cannot_access_someone_elses_session():
    """The core IDOR check: User B must never be recognized as the
    owner of User A's session, however User B came by the session_id
    (a leaked link, a guessed sequential-looking id, etc.)."""
    sessions = _load_sessions_module()
    s = sessions.create_session("userA", "My private chat")
    assert sessions.owns(s["id"], "userB") is False


def test_nonexistent_session_denies_everyone():
    """A session_id that doesn't exist at all must deny ownership, not
    raise or (worse) default-allow."""
    sessions = _load_sessions_module()
    assert sessions.owns("totally-made-up-id-12345", "userA") is False


def test_owns_check_survives_many_other_sessions_existing():
    """Not a security property by itself, but a regression guard: make
    sure owns() actually reads the specific session_id given, rather
    than e.g. matching on owner_id against ANY session (which would
    make every session "owned" by anyone who has ever created one)."""
    sessions = _load_sessions_module()
    s_a = sessions.create_session("userA", "Chat 1")
    s_a2 = sessions.create_session("userA", "Chat 2")
    s_b = sessions.create_session("userB", "Chat 3")

    assert sessions.owns(s_a["id"], "userA") is True
    assert sessions.owns(s_a2["id"], "userA") is True
    assert sessions.owns(s_b["id"], "userA") is False
    assert sessions.owns(s_a["id"], "userB") is False


def test_list_sessions_never_returns_another_users_sessions():
    """The listing endpoint's own filter (brief §22: 'never rely solely
    on frontend filtering' — this is the server-side filter that backs
    it) must never leak another user's session into a listing.

    Note: list_sessions() returns a trimmed summary (id/title/timestamps/
    counts) that deliberately does NOT include owner_id in the output —
    filtering happens before that point, so checking session IDENTITY
    (which ids came back) is the correct assertion here, not checking
    an owner_id field that was never meant to be in the response."""
    sessions = _load_sessions_module()
    a1 = sessions.create_session("userA", "A's chat 1")
    a2 = sessions.create_session("userA", "A's chat 2")
    b1 = sessions.create_session("userB", "B's chat")

    a_ids = {s["id"] for s in sessions.list_sessions("userA")}
    b_ids = {s["id"] for s in sessions.list_sessions("userB")}

    assert a_ids == {a1["id"], a2["id"]}, f"userA's listing was wrong: {a_ids}"
    assert b_ids == {b1["id"]}, f"userB's listing was wrong: {b_ids}"
    assert a_ids.isdisjoint(b_ids), "userA and userB's listings overlapped — IDOR leak!"


ALL_TESTS = [
    test_owner_can_access_own_session,
    test_other_user_cannot_access_someone_elses_session,
    test_nonexistent_session_denies_everyone,
    test_owns_check_survives_many_other_sessions_existing,
    test_list_sessions_never_returns_another_users_sessions,
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
