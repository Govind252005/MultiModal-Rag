"""
Security Test Suite: File Ingestion Protection (SEC-04).
Validates zip bomb protection, DOCX traversal rejection, PDF page constraints,
and sanitized error responses.
"""

import io
import zipfile
import pytest
from backend import config
from backend.ingestion.doc_safety import (
    validate_docx_safety,
    validate_pdf_safety,
    IngestionSafetyError,
)


def test_docx_zip_bomb_prevention(tmp_path):
    """Test that an archive exceeding uncompressed size limits is blocked."""
    bomb_path = tmp_path / "zip_bomb.docx"
    with zipfile.ZipFile(bomb_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        # Create a compressed file with high expansion ratio
        # 10MB of zeros compressed is only a few KB
        z.writestr("word/document.xml", b"0" * (15 * 1024 * 1024))
        z.writestr("[Content_Types].xml", b"<Types/>")

    # Should detect high ratio or uncompressed limit
    with pytest.raises(IngestionSafetyError) as exc_info:
        validate_docx_safety(str(bomb_path))
    assert "safety" in str(exc_info.value).lower() or "limit" in str(exc_info.value).lower()


def test_docx_path_traversal_rejection(tmp_path):
    """Test that a malicious DOCX with path traversal in internal entries is rejected."""
    traversal_path = tmp_path / "traversal.docx"
    with zipfile.ZipFile(traversal_path, "w") as z:
        z.writestr("../../../etc/passwd", b"malicious content")
        z.writestr("word/document.xml", b"normal content")

    with pytest.raises(IngestionSafetyError) as exc_info:
        validate_docx_safety(str(traversal_path))
    assert "unsafe file path" in str(exc_info.value).lower()


def test_valid_docx_passes_safety(tmp_path):
    """Test that a valid benign DOCX archive passes checks."""
    valid_path = tmp_path / "valid.docx"
    with zipfile.ZipFile(valid_path, "w") as z:
        z.writestr("[Content_Types].xml", b"<Types/>")
        z.writestr("word/document.xml", b"<w:document><w:body><w:p/></w:body></w:document>")

    # Should pass without exception
    validate_docx_safety(str(valid_path))


def test_pdf_page_limit_enforcement(tmp_path, monkeypatch):
    """Test that a PDF exceeding MAX_PDF_PAGES is rejected."""
    import fitz

    # Set temporary low limit
    monkeypatch.setattr(config, "MAX_PDF_PAGES", 5)

    pdf_path = tmp_path / "too_many_pages.pdf"
    doc = fitz.open()
    for _ in range(10):  # 10 pages > limit of 5
        doc.new_page()
    doc.save(str(pdf_path))
    doc.close()

    with pytest.raises(IngestionSafetyError) as exc_info:
        validate_pdf_safety(str(pdf_path))
    assert "maximum page limit" in str(exc_info.value).lower()
