"""
Document parsing -> text + image records with citation metadata.

  * PDF  : PyMuPDF (fitz) gives us text PER PAGE, so every chunk keeps its
           page number -> "[1] report.pdf, p.3". If a page has no text
           layer (scanned), we fall back to OCR on a rendered image.
           Embedded images are extracted, saved to image_dir, and pushed
           through the image pipeline (CLIP + BLIP + OCR).
  * DOCX : python-docx reads paragraphs + table cells in document order.
           Embedded images are extracted via document relationships.

Each returned record is a dict the ingest orchestrator knows how to store:
  {"target": "text",  "text": <chunk>, "metadata": {...}}
  {"target": "image", "text": <caption>, "image": <PIL>, "metadata": {...}}
"""

from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend import config
from backend.ingestion.chunker import chunk_text
from backend.ingestion.image_safety import enforce_image_limits
# Ignore tiny decorative images (icons, bullets, dividers).
_MIN_W = int(getattr(config, "EMBED_IMAGE_MIN_WIDTH", 80))
_MIN_H = int(getattr(config, "EMBED_IMAGE_MIN_HEIGHT", 80))
_MAX_IMGS = config.MAX_EXTRACTED_IMAGES_PER_DOC


_SECTION_NAMES = (
    "abstract", "introduction", "background", "related work", "methods",
    "methodology", "results", "discussion", "conclusion", "references",
    "acknowledgments", "appendix",
)


def _section_heading(line: str) -> Optional[str]:
    """Return a normalized section name for a heading-like line."""
    value = re.sub(r"\s+", " ", (line or "").strip().lower())
    value = re.sub(r"^[\d.\s)]+", "", value)
    value = value.replace("–", "-").replace("—", "-")
    value = re.split(r"\s*[-:|]\s*", value, maxsplit=1)[0].strip()
    for name in _SECTION_NAMES:
        if value == name or value.startswith(name + " "):
            return name
    return None


def _section_segments(text: str, current: Optional[str] = None):
    """Split text at recognizable headings while carrying section state."""
    segments = []
    active = current
    body: List[str] = []
    for line in (text or "").splitlines():
        heading = _section_heading(line)
        if heading:
            if body and " ".join(body).strip():
                segments.append((active, "\n".join(body).strip()))
            body = []
            active = heading
        else:
            body.append(line)
    if body and " ".join(body).strip():
        segments.append((active, "\n".join(body).strip()))
    return segments, active


def _record(text: str, file: str, page, source_type: str = "text",
            section: Optional[str] = None) -> Dict[str, Any]:
    record = {
        "target": "text",
        "text": text,
        "metadata": {
            "file": file,
            "modality": "document",
            "source_type": source_type,
            "page": page,
        },
    }
    if section:
        record["metadata"]["section"] = section
    return record


def _safe_stem(name: str) -> str:
    return "".join(c if (c.isalnum() or c in "-_") else "_"
                   for c in Path(name).stem) or "doc"


def _image_records(pil_img, file: str, image_dir: Optional[Path],
                   page: Optional[int], seq: int) -> List[Dict[str, Any]]:
    """Save an extracted PIL image and build its 3-part ingest records."""
    from backend.ingestion.image_pipeline import build_image_records
    media_file: Optional[str] = None
    if image_dir is not None:
        try:
            image_dir.mkdir(parents=True, exist_ok=True)
            media_file = f"{_safe_stem(file)}__p{page or 0}_img{seq}.png"
            pil_img.save(image_dir / media_file, format="PNG")
        except Exception as exc:
            print(f"[doc-image] save failed: {exc}")
            media_file = None

    return build_image_records(pil_img, file, media_file=media_file, page=page)


# ------------------------------------------------------------------
# PDF
# ------------------------------------------------------------------
def parse_pdf(path: str, image_dir: Optional[Path] = None,
             ocr_fallback: bool = True, extract_tables: bool = True,
             extract_embedded_images: bool = True) -> List[Dict[str, Any]]:
    import fitz  # PyMuPDF
    from PIL import Image

    file = Path(path).name
    records: List[Dict[str, Any]] = []
    doc = fitz.open(path)
    # brief §31: cap resource usage per document instead of processing an
    # arbitrarily large PDF in full. Truncate rather than reject outright —
    # a partial index is more useful than none, and this is logged so it's
    # never a silent data loss.
    total_pages = len(doc)
    page_limit = min(total_pages, config.MAX_PDF_PAGES)
    if total_pages > config.MAX_PDF_PAGES:
        print(f"[pdf] '{file}' has {total_pages} pages, exceeding "
              f"MAX_PDF_PAGES={config.MAX_PDF_PAGES}; only the first "
              f"{page_limit} pages will be ingested.")
    seen_xrefs: set = set()
    extracted = 0
    current_section: Optional[str] = None
    try:
        for page_index in range(page_limit):
            page = doc[page_index]
            page_no = page_index + 1
            text = page.get_text("text").strip()

            if len(text) < 10 and ocr_fallback:  # brief §44: skippable in FAST mode
                text = _ocr_pdf_page(page)

            segments, current_section = _section_segments(text, current_section)
            for section, segment in segments:
                for chunk in chunk_text(segment):
                    records.append(_record(chunk, file, page_no,
                                           section=section))

            if extract_tables:  # brief §44: skippable outside MAX_QUALITY
                records.extend(_table_records(page, page_no, file))

            if not extract_embedded_images:  # brief §44: skippable outside MAX_QUALITY
                continue
            if extracted >= _MAX_IMGS:
                continue
            try:
                for img_info in page.get_images(full=True):
                    if extracted >= _MAX_IMGS:
                        break
                    xref = img_info[0]
                    if xref in seen_xrefs:
                        continue
                    seen_xrefs.add(xref)
                    try:
                        base = doc.extract_image(xref)
                        pil = enforce_image_limits(
                            Image.open(io.BytesIO(base["image"])).convert("RGB"),
                            context=f"{file} p.{page_no} embedded image",
                        )
                    except Exception:
                        continue
                    if pil.width < _MIN_W or pil.height < _MIN_H:
                        continue
                    extracted += 1
                    records.extend(_image_records(pil, file, image_dir, page_no, extracted))
            except Exception as exc:
                print(f"[pdf] image extraction p.{page_no}: {exc}")
    finally:
        doc.close()
    return records


def _table_records(page, page_no: int, file: str) -> List[Dict[str, Any]]:
    """Extract tables from a PDF page via PyMuPDF find_tables()."""
    records: List[Dict[str, Any]] = []
    try:
        tabs = page.find_tables()
        for tbl in (tabs.tables if hasattr(tabs, "tables") else []):
            rows = tbl.extract()
            if not rows:
                continue
            lines = []
            for row in rows:
                cells = [str(c).strip() if c is not None else "" for c in row]
                lines.append(" | ".join(cells))
            text = "\n".join(lines).strip()
            if not text:
                continue
            records.append({
                "target": "text",
                "text": text,
                "metadata": {
                    "file": file,
                    "modality": "document",
                    "source_type": "table",
                    "page": page_no,
                    "section": current_section,
                },
            })
    except Exception as exc:
        print(f"[pdf] table extraction p.{page_no}: {exc}")
    return records


def _ocr_pdf_page(page) -> str:
    """OCR a scanned PDF page using PaddleOCR first, Tesseract as fallback."""
    try:
        from PIL import Image
        from backend.ingestion.image_pipeline import ocr_image
        pix = page.get_pixmap(dpi=200)
        img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")

        return ocr_image(img).strip()

    except Exception:
        return ""

# ------------------------------------------------------------------
# DOCX
# ------------------------------------------------------------------
def parse_docx(path: str, image_dir: Optional[Path] = None,
               extract_embedded_images: bool = True) -> List[Dict[str, Any]]:
    import docx  # python-docx
    from PIL import Image

    file = Path(path).name
    document = docx.Document(path)

    parts: List[str] = [p.text for p in document.paragraphs if p.text.strip()]
    for table in document.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                parts.append(" | ".join(cells))

    full_text = "\n".join(parts)
    records: List[Dict[str, Any]] = []
    segments, _ = _section_segments(full_text)
    for section, segment in segments:
        for chunk in chunk_text(segment):
            records.append(_record(chunk, file, None, section=section))

    if not extract_embedded_images:  # brief §44: skippable outside MAX_QUALITY
        return records

    extracted = 0
    try:
        for rel in document.part.rels.values():
            if extracted >= _MAX_IMGS:
                break
            if "image" not in rel.reltype:
                continue
            try:
                pil = enforce_image_limits(
                    Image.open(io.BytesIO(rel.target_part.blob)).convert("RGB"),
                    context=f"{file} embedded image",
                )
            except Exception:
                continue
            if pil.width < _MIN_W or pil.height < _MIN_H:
                continue
            extracted += 1
            records.extend(_image_records(pil, file, image_dir, None, extracted))
    except Exception as exc:
        print(f"[docx] image extraction: {exc}")

    return records


# ------------------------------------------------------------------
# Dispatcher
# ------------------------------------------------------------------
def parse_document(path: str, image_dir: Optional[Path] = None,
                   ocr_fallback: bool = True, extract_tables: bool = True,
                   extract_embedded_images: bool = True) -> List[Dict[str, Any]]:
    ext = Path(path).suffix.lower()
    if ext == ".pdf":
        return parse_pdf(path, image_dir=image_dir, ocr_fallback=ocr_fallback,
                         extract_tables=extract_tables,
                         extract_embedded_images=extract_embedded_images)
    if ext in (".docx", ".doc"):
        return parse_docx(path, image_dir=image_dir,
                          extract_embedded_images=extract_embedded_images)
    raise ValueError(f"Unsupported document type: {ext}")
