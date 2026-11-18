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

_EXPERIMENT_HEADING_RE = re.compile(
    r"^(?:EXPERIMENT|EXP\.?|PRACTICAL|LAB|ASSIGNMENT)\s*(?:NO\.?\s*|NUMBER\s*)?[-:#]?\s*([0-9a-zA-Z]+[^\r\n]*)",
    re.IGNORECASE,
)
_STRUCTURAL_HEADING_RE = re.compile(
    r"^(?:UNIT|CHAPTER|SECTION|MODULE|PART)\s*(?:NO\.?\s*|NUMBER\s*)?[-:#]?\s*([0-9a-zA-Z]+[^\r\n]*)",
    re.IGNORECASE,
)
_NUMBERED_HEADING_RE = re.compile(r"^(?:\d+\.|\d+\.\d+)\s+([A-Z][^\r\n]{2,80})$")
_KEY_PHRASE_HEADING_RE = re.compile(
    r"^(?:TEST\s*CASES?|SYSTEM\s*SPECIFICATION|SPECIFICATIONS|THEORY\s*AND\s*SPECIFICATIONS|AIM|OBJECTIVE|PROCEDURE|RESULTS|CONCLUSION)\b[^\r\n]*",
    re.IGNORECASE,
)


def _detect_heading(line: str) -> Optional[str]:
    clean = (line or "").strip()
    if not clean or len(clean) < 3:
        return None
    md_match = re.match(r"^#{1,6}\s+(.+)$", clean)
    if md_match:
        return md_match.group(1).strip()
    if _EXPERIMENT_HEADING_RE.match(clean):
        return clean
    if _STRUCTURAL_HEADING_RE.match(clean):
        return clean
    if _NUMBERED_HEADING_RE.match(clean):
        return clean
    if _KEY_PHRASE_HEADING_RE.match(clean) and len(clean.split()) <= 8:
        return clean
    return _section_heading(clean)


def _section_heading(line: str) -> Optional[str]:
    """Return a normalized section name for a heading-like line."""
    clean = (line or "").strip()
    if not clean:
        return None

    # Support Markdown headings: '# Heading', '## Heading', etc.
    md_match = re.match(r"^#{1,6}\s+(.+)$", clean)
    if md_match:
        return md_match.group(1).strip()

    value = re.sub(r"\s+", " ", clean.lower())
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
            section: Optional[str] = None, extra_meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    from backend.nlp.language_detect import detect_language
    lang_info = detect_language(text)
    record = {
        "target": "text",
        "text": text,
        "metadata": {
            "file": file,
            "modality": "document",
            "source_type": source_type,
            "page": page,
            "lang": lang_info["language"],
            "script": lang_info["script"],
            "char_count": len(text),
        },
    }
    if section:
        record["metadata"]["section"] = section
    if extra_meta:
        record["metadata"].update(extra_meta)
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

    # Embedded document images: caption_images=False prevents slow BLIP generation loops
    return build_image_records(pil_img, file, media_file=media_file, page=page, caption_images=False)


# ------------------------------------------------------------------
# PDF
# ------------------------------------------------------------------
def _mask_text_rects(words: List[Any], masked_rects: Optional[List[Any]]) -> List[Any]:
    """Filter out word tuples that fall within masked table bounding boxes."""
    if not masked_rects or not words:
        return words
    filtered: List[Any] = []
    for w in words:
        x0, y0, x1, y1 = w[:4]
        cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
        in_mask = False
        for r in masked_rects:
            if hasattr(r, "contains"):
                import fitz
                if r.contains(fitz.Point(cx, cy)):
                    in_mask = True
                    break
            elif isinstance(r, (tuple, list)) and len(r) >= 4:
                if r[0] <= cx <= r[2] and r[1] <= cy <= r[3]:
                    in_mask = True
                    break
        if not in_mask:
            filtered.append(w)
    return filtered


def _extract_row_aligned_text(page, masked_rects: Optional[List[Any]] = None) -> str:
    """Extract page text preserving visual row alignment for borderless tables/multi-column forms."""
    try:
        import fitz
        words = page.get_text("words")
        if not words:
            return ""

        if masked_rects:
            words = _mask_text_rects(words, masked_rects)

        if not words:
            return ""

        # Group words by visual horizontal lines using y_bucket = round(y0 / 6.0)
        line_buckets: Dict[int, List[Any]] = {}
        for w in words:
            y_bucket = round(w[1] / 6.0)
            if y_bucket not in line_buckets:
                line_buckets[y_bucket] = []
            line_buckets[y_bucket].append(w)

        sorted_buckets: List[List[Any]] = []
        for b_key in sorted(line_buckets.keys()):
            b_words = sorted(line_buckets[b_key], key=lambda x: x[0])
            sorted_buckets.append(b_words)

        # Check if page has multi-column rows (horizontal gap > 25pt across >= 3 lines)
        multi_col_line_count = 0
        for b_words in sorted_buckets:
            for idx in range(1, len(b_words)):
                gap = b_words[idx][0] - b_words[idx - 1][2]
                if gap > 25.0:
                    multi_col_line_count += 1
                    break

        is_multi_column = multi_col_line_count >= 3

        if not is_multi_column:
            if not masked_rects:
                return page.get_text("text").strip()
            # If masked_rects were excluded, return reconstructed prose lines
            lines_out = []
            for b_words in sorted_buckets:
                line_str = " ".join(w[4] for w in b_words).strip()
                if line_str:
                    lines_out.append(line_str)
            return "\n".join(lines_out).strip()

        # Build row-aligned text joining column gaps (> 18pt) with " | "
        formatted_lines = []
        for b_words in sorted_buckets:
            if not b_words:
                continue
            line_parts = [b_words[0][4]]
            for idx in range(1, len(b_words)):
                gap = b_words[idx][0] - b_words[idx - 1][2]
                sep = " | " if gap > 18.0 else " "
                line_parts.append(sep + b_words[idx][4])
            line_text = "".join(line_parts).strip()
            if line_text:
                formatted_lines.append(line_text)

        return "\n".join(formatted_lines).strip()
    except Exception as exc:
        print(f"[pdf] _extract_row_aligned_text error: {exc}")
        return page.get_text("text").strip()


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
    active_heading: Optional[str] = None
    table_state: Dict[str, Any] = {"last_header": None}
    try:
        for page_index in range(page_limit):
            page = doc[page_index]
            page_no = page_index + 1

            table_bboxes = []
            if extract_tables:
                try:
                    tabs = page.find_tables()
                    for tbl in (tabs.tables if hasattr(tabs, "tables") else []):
                        if hasattr(tbl, "bbox") and tbl.bbox:
                            table_bboxes.append(tbl.bbox)
                except Exception:
                    pass

            text = _extract_row_aligned_text(page, masked_rects=table_bboxes if table_bboxes else None)

            if ocr_fallback:  # brief §44: skippable in FAST mode
                native_clean = text.strip()
                has_images = len(page.get_images(full=True)) > 0
                should_ocr = len(native_clean) < 10 or (len(native_clean) < 140 and has_images)
                if should_ocr:
                    ocr_text = _ocr_pdf_page(page)
                    if ocr_text:
                        if len(native_clean) < 10:
                            text = ocr_text
                        else:
                            if native_clean.lower() not in ocr_text.lower():
                                text = f"{native_clean}\n\n{ocr_text}"
                            else:
                                text = ocr_text

            for ch in ("\u200b", "\u200c", "\u200d", "\ufeff", "\u2060", "\xad"):
                text = text.replace(ch, "")
            text = text.replace("\u00a0", " ")

            if not text.strip():
                try:
                    from backend.observability import metrics as obs_metrics
                    obs_metrics.inc_counter("ingestion_empty_pages_total", {"file": file, "page": str(page_no)})
                except Exception:
                    pass

            # Scan lines on this page for structural headings (e.g. "Experiment 2")
            for line in text.splitlines()[:15]:
                detected = _detect_heading(line)
                if detected:
                    active_heading = detected
                    break

            segments, current_section = _section_segments(text, active_heading)
            for section, segment in segments:
                eff_sec = section or active_heading
                for chunk in chunk_text(segment):
                    prefix = f"[Section Context: {eff_sec} | Page {page_no}]\n" if eff_sec else ""
                    records.append(_record(f"{prefix}{chunk}", file, page_no,
                                           section=eff_sec))

            if extract_tables:  # brief §44: skippable outside MAX_QUALITY
                records.extend(_table_records(page, page_no, file, section=active_heading, state=table_state))

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


def _table_records(page, page_no: int, file: str, section: Optional[str] = None,
                   state: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Extract tables from a PDF page via PyMuPDF find_tables() with header preservation across chunks."""
    records: List[Dict[str, Any]] = []
    try:
        import fitz
        tabs = page.find_tables()
        for idx, tbl in enumerate(tabs.tables if hasattr(tabs, "tables") else []):
            rows = tbl.extract()
            if not rows or len(rows) == 0:
                continue

            # Capture preceding caption lines above table if available
            table_caption = ""
            try:
                if hasattr(tbl, "bbox") and tbl.bbox:
                    y0 = tbl.bbox[1]
                    rect_above = fitz.Rect(0, max(0, y0 - 70), page.rect.width, y0)
                    above_txt = page.get_text("text", clip=rect_above).strip()
                    if above_txt:
                        table_caption = " ".join(above_txt.splitlines()[-2:]).strip()
            except Exception:
                pass

            eff_sec = section or "General"
            if table_caption:
                context_tag = f"[Table {idx + 1} | Section: {eff_sec} | Caption: {table_caption} | Page {page_no} | {file}]\n"
            else:
                context_tag = f"[Table {idx + 1} | Section: {eff_sec} | Page {page_no} | {file}]\n"

            # Clean rows
            cleaned_rows = [
                [str(c).strip().replace("\n", " ") if c is not None else "" for c in r]
                for r in rows
            ]

            # Continuation table check: if first row is pure data and matches column count of previous page table
            if state is not None and state.get("last_header") and cleaned_rows:
                prev_hdr = state["last_header"]
                if len(cleaned_rows[0]) == len(prev_hdr):
                    first_cell = cleaned_rows[0][0].strip()
                    if first_cell.isdigit() or not any(w in cleaned_rows[0] for w in ["Name", "ID", "No", "Title", "Date", "Description", "Result", "Parameter", "Test Case"]):
                        cleaned_rows.insert(0, prev_hdr)

            header_cells = cleaned_rows[0]
            if state is not None and header_cells:
                state["last_header"] = header_cells

            col_count = len(header_cells)
            header_line = "| " + " | ".join(header_cells) + " |"
            sep_line = "| " + " | ".join(["---"] * max(1, col_count)) + " |"

            data_rows = cleaned_rows[1:]
            if not data_rows:
                records.append(_record(f"{context_tag}{header_line}\n{sep_line}", file, page_no, source_type="table", section=section))
                continue

            # Format data rows into chunks while always prepending header row + delimiter
            current_data_lines: List[str] = []
            current_words = len(context_tag.split()) + len(header_line.split()) + len(sep_line.split())
            max_words = getattr(config, "CHUNK_SIZE_WORDS", 130)

            for d_row in data_rows:
                row_line = "| " + " | ".join(d_row) + " |"
                row_words = len(row_line.split())

                if current_data_lines and (current_words + row_words > max_words):
                    chunk_text = context_tag + header_line + "\n" + sep_line + "\n" + "\n".join(current_data_lines)
                    records.append(_record(chunk_text, file, page_no, source_type="table", section=section))
                    current_data_lines = [row_line]
                    current_words = len(context_tag.split()) + len(header_line.split()) + len(sep_line.split()) + row_words
                else:
                    current_data_lines.append(row_line)
                    current_words += row_words

            if current_data_lines:
                chunk_text = context_tag + header_line + "\n" + sep_line + "\n" + "\n".join(current_data_lines)
                records.append(_record(chunk_text, file, page_no, source_type="table", section=section))

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
# PPTX
# ------------------------------------------------------------------
def parse_pptx(path: str, image_dir: Optional[Path] = None,
               extract_tables: bool = True,
               extract_embedded_images: bool = True) -> List[Dict[str, Any]]:
    """Parse PowerPoint presentation slides, tables, and images."""
    import pptx
    from PIL import Image

    file = Path(path).name
    records: List[Dict[str, Any]] = []
    prs = pptx.Presentation(path)
    extracted_imgs = 0

    for slide_idx, slide in enumerate(prs.slides):
        slide_no = slide_idx + 1
        slide_texts: List[str] = []
        slide_title = None

        if slide.shapes.title and slide.shapes.title.text.strip():
            slide_title = slide.shapes.title.text.strip()
            slide_texts.append(slide_title)

        for shape in slide.shapes:
            if shape == slide.shapes.title:
                continue
            if shape.has_text_frame:
                txt = shape.text_frame.text.strip()
                if txt:
                    slide_texts.append(txt)
            elif shape.has_table and extract_tables:
                rows_text = []
                for row in shape.table.rows:
                    row_cells = [c.text.strip() for c in row.cells]
                    if any(row_cells):
                        rows_text.append(" | ".join(row_cells))
                if rows_text:
                    table_content = "\n".join(rows_text)
                    records.append(_record(table_content, file, slide_no,
                                           source_type="table", section=slide_title))
            elif extract_embedded_images and shape.shape_type == 13:  # 13 is PICTURE
                if extracted_imgs < _MAX_IMGS:
                    try:
                        img_bytes = shape.image.blob
                        pil = enforce_image_limits(
                            Image.open(io.BytesIO(img_bytes)).convert("RGB"),
                            context=f"{file} slide {slide_no} image",
                        )
                        if pil.width >= _MIN_W and pil.height >= _MIN_H:
                            extracted_imgs += 1
                            records.extend(_image_records(pil, file, image_dir, slide_no, extracted_imgs))
                    except Exception as exc:
                        print(f"[pptx] image extraction slide {slide_no}: {exc}")

        combined_text = "\n\n".join(slide_texts).strip()
        if combined_text:
            for chunk in chunk_text(combined_text):
                records.append(_record(chunk, file, slide_no, section=slide_title))

    return records


# ------------------------------------------------------------------
# XLSX
# ------------------------------------------------------------------
def parse_xlsx(path: str, max_rows_per_sheet: int = 5000) -> List[Dict[str, Any]]:
    """Parse Excel spreadsheet sheets into row blocks with table structure."""
    import openpyxl

    file = Path(path).name
    records: List[Dict[str, Any]] = []
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)

    try:
        for sheet_idx, sheet_name in enumerate(wb.sheetnames):
            sheet = wb[sheet_name]
            sheet_no = sheet_idx + 1
            rows_data: List[str] = []

            for r_idx, row in enumerate(sheet.iter_rows(values_only=True)):
                if r_idx >= max_rows_per_sheet:
                    break
                row_vals = [str(c).strip() for c in row if c is not None and str(c).strip()]
                if row_vals:
                    rows_data.append(" | ".join(row_vals))

            if not rows_data:
                continue

            batch_size = 20
            for b_idx in range(0, len(rows_data), batch_size):
                block_text = f"Sheet: {sheet_name}\n" + "\n".join(rows_data[b_idx:b_idx+batch_size])
                records.append(_record(block_text, file, sheet_no,
                                       source_type="spreadsheet", section=sheet_name))
    finally:
        wb.close()

    return records


# ------------------------------------------------------------------
# Plain Text / Markdown / CSV
# ------------------------------------------------------------------
def parse_text_file(path: str) -> List[Dict[str, Any]]:
    """Parse plain text, Markdown, or CSV files."""
    file = Path(path).name
    records: List[Dict[str, Any]] = []

    content = ""
    for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            with open(path, "r", encoding=enc) as f:
                content = f.read()
            break
        except UnicodeDecodeError:
            continue

    if not content.strip():
        return records

    segments, _ = _section_segments(content)
    page = 1
    for section, segment in segments:
        for chunk in chunk_text(segment):
            records.append(_record(chunk, file, page, section=section))

    return records


# ------------------------------------------------------------------
# Dispatcher
# ------------------------------------------------------------------
def parse_document(path: str, image_dir: Optional[Path] = None,
                   ocr_fallback: bool = True, extract_tables: bool = True,
                   extract_embedded_images: bool = True) -> List[Dict[str, Any]]:
    ext = Path(path).suffix.lower()
    if ext == ".pdf":
        from backend.ingestion.doc_safety import validate_pdf_safety
        validate_pdf_safety(path)
        return parse_pdf(path, image_dir=image_dir, ocr_fallback=ocr_fallback,
                         extract_tables=extract_tables,
                         extract_embedded_images=extract_embedded_images)
    if ext in (".docx", ".doc"):
        from backend.ingestion.doc_safety import validate_docx_safety
        if ext == ".docx":
            validate_docx_safety(path)
        return parse_docx(path, image_dir=image_dir,
                          extract_embedded_images=extract_embedded_images)
    if ext in (".pptx", ".ppt"):
        from backend.ingestion.doc_safety import validate_pptx_safety
        if ext == ".pptx":
            validate_pptx_safety(path)
        return parse_pptx(path, image_dir=image_dir,
                          extract_tables=extract_tables,
                          extract_embedded_images=extract_embedded_images)
    if ext in (".xlsx", ".xls"):
        from backend.ingestion.doc_safety import validate_xlsx_safety
        if ext == ".xlsx":
            validate_xlsx_safety(path)
        return parse_xlsx(path)
    if ext in (".txt", ".md", ".csv", ".json", ".log"):
        from backend.ingestion.doc_safety import validate_text_safety
        validate_text_safety(path)
        return parse_text_file(path)
    raise ValueError(f"Unsupported document type: {ext}")
