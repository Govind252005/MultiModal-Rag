"""
File signature (magic bytes) verification (transformation brief §28):
"Do not trust filename, extension, Content-Type alone. Validate actual
file signatures/magic bytes."

This does NOT replace the existing extension allowlist in
`ingestion/ingest.py::_modality_for()` — it's an additional, earlier layer:
the extension says what the file CLAIMS to be, this checks whether its
first bytes are actually consistent with that claim. A `.pdf` that's
secretly something else gets rejected here, before it ever reaches a
parser.

Honesty note on scope: PDF, DOCX/DOC, and the common image/lossless-audio
formats have well-defined, unambiguous magic bytes and are checked
strictly. Raw MP3/AAC streams do not have a single reliable universal
signature (a bare MPEG frame sync is only 11 bits and legitimately
variable), so those two are checked permissively — this is a real,
documented limitation, not silently glossed over.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

# How many bytes we need to read to make a determination. WEBP/M4A need to
# look a little past the first few bytes.
_SNIFF_LEN = 32


def _read_header(path: str, n: int = _SNIFF_LEN) -> bytes:
    with open(path, "rb") as f:
        return f.read(n)


def _is_pdf(h: bytes) -> bool:
    return h.startswith(b"%PDF-")


def _is_zip_based(h: bytes) -> bool:
    # DOCX (and XLSX/PPTX) are ZIP containers.
    return h.startswith(b"PK\x03\x04") or h.startswith(b"PK\x05\x06") or h.startswith(b"PK\x07\x08")


def _is_ole2(h: bytes) -> bool:
    # Legacy .doc (pre-2007 binary Word format).
    return h.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")


def _is_png(h: bytes) -> bool:
    return h.startswith(b"\x89PNG\r\n\x1a\n")


def _is_jpeg(h: bytes) -> bool:
    return h.startswith(b"\xff\xd8\xff")


def _is_gif(h: bytes) -> bool:
    return h.startswith(b"GIF87a") or h.startswith(b"GIF89a")


def _is_bmp(h: bytes) -> bool:
    return h.startswith(b"BM")


def _is_webp(h: bytes) -> bool:
    return h[0:4] == b"RIFF" and h[8:12] == b"WEBP"


def _is_tiff(h: bytes) -> bool:
    return h.startswith(b"II*\x00") or h.startswith(b"MM\x00*")


def _is_wav(h: bytes) -> bool:
    return h[0:4] == b"RIFF" and h[8:12] == b"WAVE"


def _is_flac(h: bytes) -> bool:
    return h.startswith(b"fLaC")


def _is_ogg(h: bytes) -> bool:
    return h.startswith(b"OggS")


def _is_m4a(h: bytes) -> bool:
    return h[4:8] == b"ftyp"


def _is_mp3_permissive(h: bytes) -> bool:
    # ID3-tagged files are unambiguous. Bare MPEG frame sync (11 set bits)
    # is inherently loose — accept it rather than reject a huge fraction
    # of real-world MP3s over an under-specified format.
    if h.startswith(b"ID3"):
        return True
    return len(h) >= 2 and h[0] == 0xFF and (h[1] & 0xE0) == 0xE0


def _is_aac_permissive(h: bytes) -> bool:
    # ADTS sync word, same looseness caveat as MP3.
    return len(h) >= 2 and h[0] == 0xFF and (h[1] & 0xF0) == 0xF0


_CHECKS = {
    ".pdf": (_is_pdf,),
    ".docx": (_is_zip_based,),
    ".doc": (_is_ole2, _is_zip_based),  # some ".doc" uploads are actually docx-renamed
    ".png": (_is_png,),
    ".jpg": (_is_jpeg,),
    ".jpeg": (_is_jpeg,),
    ".bmp": (_is_bmp,),
    ".gif": (_is_gif,),
    ".webp": (_is_webp,),
    ".tif": (_is_tiff,),
    ".tiff": (_is_tiff,),
    ".wav": (_is_wav,),
    ".flac": (_is_flac,),
    ".ogg": (_is_ogg,),
    ".m4a": (_is_m4a,),
    ".mp3": (_is_mp3_permissive,),
    ".aac": (_is_aac_permissive,),
}


class SignatureMismatchError(ValueError):
    pass


def verify_signature(path: str, filename: Optional[str] = None) -> None:
    """Raise SignatureMismatchError if the file's magic bytes don't match
    what its extension claims. No-op (passes) for extensions we don't have
    a signature check for — the existing extension allowlist in
    ingest.py is the backstop for those, not this function."""
    ext = Path(filename or path).suffix.lower()
    checks = _CHECKS.get(ext)
    if not checks:
        return
    header = _read_header(path)
    if not any(check(header) for check in checks):
        raise SignatureMismatchError(
            f"File content does not match its '{ext}' extension "
            f"(magic-byte check failed). Refusing to ingest — this often "
            f"means the file was renamed/mislabeled or is corrupted."
        )
