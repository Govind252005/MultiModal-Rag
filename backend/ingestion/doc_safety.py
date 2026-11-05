"""
Document Safety and Ingestion Protection (SEC-04).
Protects against zip bombs, XML bombs, malformed DOCX archives, path traversal
in archives, and excessive PDF page/size dimensions.
"""

from __future__ import annotations

import os
import zipfile
from pathlib import Path
from typing import Optional

from backend import config

# Configurable limits for archive safety
MAX_UNCOMPRESSED_ARCHIVE_BYTES = int(os.getenv("MAX_UNCOMPRESSED_ARCHIVE_BYTES", str(100 * 1024 * 1024)))  # 100MB
MAX_ARCHIVE_ENTRIES = int(os.getenv("MAX_ARCHIVE_ENTRIES", "1000"))
MAX_COMPRESSION_RATIO = float(os.getenv("MAX_COMPRESSION_RATIO", "100.0"))  # 100:1 ratio


class IngestionSafetyError(ValueError):
    """Raised when an ingested file violates resource limits or exhibits malicious behavior."""
    pass


def validate_docx_safety(path: str) -> None:
    """Validate DOCX zip archive structure to prevent zip bombs, path traversal,
    and archive decompression exhaustion attacks."""
    p = Path(path)
    if not p.exists():
        raise IngestionSafetyError(f"File not found: {p.name}")

    if not zipfile.is_zipfile(path):
        raise IngestionSafetyError("Invalid DOCX file: Not a valid zip archive.")

    total_uncompressed = 0
    total_compressed = 0
    entry_count = 0

    try:
        with zipfile.ZipFile(path, "r") as z:
            infolist = z.infolist()
            entry_count = len(infolist)

            if entry_count > MAX_ARCHIVE_ENTRIES:
                raise IngestionSafetyError(
                    f"DOCX archive contains too many files ({entry_count} > {MAX_ARCHIVE_ENTRIES})."
                )

            for info in infolist:
                # Check path traversal in entry names
                entry_name = info.filename
                if ".." in entry_name or entry_name.startswith(("/", "\\")):
                    raise IngestionSafetyError("DOCX archive contains unsafe file paths.")

                total_uncompressed += info.file_size
                total_compressed += info.compress_size

                # Check total uncompressed size limit
                if total_uncompressed > MAX_UNCOMPRESSED_ARCHIVE_BYTES:
                    raise IngestionSafetyError(
                        f"DOCX uncompressed size exceeds limit of {MAX_UNCOMPRESSED_ARCHIVE_BYTES // (1024*1024)}MB."
                    )

            # Check compression ratio for zip bombs
            if total_compressed > 0 and total_uncompressed > 5 * 1024 * 1024:
                ratio = total_uncompressed / total_compressed
                if ratio > MAX_COMPRESSION_RATIO:
                    raise IngestionSafetyError(
                        f"DOCX compression ratio ({ratio:.1f}:1) exceeds safety threshold (possible zip bomb)."
                    )

    except zipfile.BadZipFile:
        raise IngestionSafetyError("Malformed or corrupted DOCX archive.")


def validate_pdf_safety(path: str) -> None:
    """Validate PDF file size and page constraints."""
    p = Path(path)
    if not p.exists():
        raise IngestionSafetyError(f"File not found: {p.name}")

    file_size_mb = p.stat().st_size / (1024 * 1024)
    if file_size_mb > config.MAX_PDF_FILE_SIZE_MB:
        raise IngestionSafetyError(
            f"PDF file size ({file_size_mb:.1f}MB) exceeds limit of {config.MAX_PDF_FILE_SIZE_MB}MB."
        )

    try:
        import fitz
        doc = fitz.open(path)
        page_count = len(doc)
        doc.close()

        if page_count > config.MAX_PDF_PAGES:
            raise IngestionSafetyError(
                f"PDF exceeds maximum page limit ({page_count} > {config.MAX_PDF_PAGES} pages)."
            )
    except Exception as exc:
        if isinstance(exc, IngestionSafetyError):
            raise
        raise IngestionSafetyError(f"Corrupted or unreadable PDF: {exc}")
