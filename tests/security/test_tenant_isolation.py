"""
Security Test Suite: Tenant Isolation (SEC-02).
Verifies that organizations/tenants cannot access, retrieve, or manipulate
vectors, lexical entries, sessions, or files across tenant boundaries.
"""

import pytest
from backend import auth, config, sessions as session_store
from backend.retrieval import lexical_index, vector_store, search


def test_session_tenant_isolation(tmp_path, monkeypatch):
    # Configure user store to temporary file
    test_user_file = tmp_path / "users_tenant_test.json"
    monkeypatch.setattr(config, "USERS_FILE", test_user_file)
    
    # 1. Register User 1 in org_alpha, User 2 in org_beta
    u1 = auth.create_user("u1@alpha.com", "Password123!", org_id="org_alpha")
    u2 = auth.create_user("u2@beta.com", "Password123!", org_id="org_beta")

    assert u1["org_id"] == "org_alpha"
    assert u2["org_id"] == "org_beta"

    # 2. User 1 creates a session in org_alpha
    s1 = session_store.create_session(u1["id"], "Alpha Confidential Project", org_id="org_alpha")
    s1_id = s1["id"]

    # User 1 owns it in org_alpha
    assert session_store.owns(s1_id, u1["id"], org_id="org_alpha") is True

    # User 2 in org_beta does NOT own it
    assert session_store.owns(s1_id, u2["id"], org_id="org_beta") is False
    assert session_store.owns(s1_id, u2["id"], org_id="org_alpha") is False

    # Getting session with wrong org_id returns None
    assert session_store.get_session(s1_id, org_id="org_beta") is None
    assert session_store.get_session(s1_id, org_id="org_alpha") is not None

    # Listing sessions for User 2 in org_beta returns empty
    u2_sessions = session_store.list_sessions(u2["id"], org_id="org_beta")
    assert not any(s["id"] == s1_id for s in u2_sessions)


def test_vector_and_lexical_tenant_isolation():
    # Ingest chunks tagged with org_alpha
    doc_alpha = "Alpha secret strategic acquisition targets for 2027: Project Titan and Apollo."
    meta_alpha = {
        "file": "alpha_targets.txt",
        "session_id": "sess_alpha_1",
        "user_id": "u_alpha_1",
        "org_id": "org_alpha",
        "modality": "document",
    }
    
    try:
        vector_store.add_text_chunks(
            ids=["chunk_alpha_sec_1"],
            embeddings=[[0.05] * 384],
            documents=[doc_alpha],
            metadatas=[meta_alpha],
        )

        # Ingest chunks tagged with org_beta
        doc_beta = "Beta secret financial roadmap: Launching Quantum compute in Q3."
        meta_beta = {
            "file": "beta_finances.txt",
            "session_id": "sess_beta_1",
            "user_id": "u_beta_1",
            "org_id": "org_beta",
            "modality": "document",
        }
        
        vector_store.add_text_chunks(
            ids=["chunk_beta_sec_1"],
            embeddings=[[0.05] * 384],
            documents=[doc_beta],
            metadatas=[meta_beta],
        )

        # 1. Test vector search where filter
        where_alpha = vector_store.build_where(org_id="org_alpha")
        hits_alpha = vector_store.query_text([0.05] * 384, top_k=10, where=where_alpha)
        hit_ids_alpha = [h["id"] for h in hits_alpha]
        assert "chunk_alpha_sec_1" in hit_ids_alpha
        assert "chunk_beta_sec_1" not in hit_ids_alpha

        where_beta = vector_store.build_where(org_id="org_beta")
        hits_beta = vector_store.query_text([0.05] * 384, top_k=10, where=where_beta)
        hit_ids_beta = [h["id"] for h in hits_beta]
        assert "chunk_beta_sec_1" in hit_ids_beta
        assert "chunk_alpha_sec_1" not in hit_ids_beta

        # 2. Test lexical search filter
        lex_alpha = lexical_index.search("secret", top_n=10, org_id="org_alpha")
        lex_alpha_files = [h["metadata"].get("file") for h in lex_alpha]
        assert "alpha_targets.txt" in lex_alpha_files
        assert "beta_finances.txt" not in lex_alpha_files

        lex_beta = lexical_index.search("secret", top_n=10, org_id="org_beta")
        lex_beta_files = [h["metadata"].get("file") for h in lex_beta]
        assert "beta_finances.txt" in lex_beta_files
        assert "alpha_targets.txt" not in lex_beta_files

        # 3. Test list_files isolation
        files_alpha = [f["file"] for f in vector_store.list_files(org_id="org_alpha")]
        assert "alpha_targets.txt" in files_alpha
        assert "beta_finances.txt" not in files_alpha

        files_beta = [f["file"] for f in vector_store.list_files(org_id="org_beta")]
        assert "beta_finances.txt" in files_beta
        assert "alpha_targets.txt" not in files_beta
    finally:
        vector_store.delete_session("sess_alpha_1")
        vector_store.delete_session("sess_beta_1")
