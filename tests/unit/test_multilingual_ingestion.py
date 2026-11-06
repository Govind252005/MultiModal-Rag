import tempfile
from pathlib import Path
import pytest
import openpyxl
import pptx
from pptx.util import Inches

from backend.ingestion.pdf_docx_parser import (
    parse_document,
    parse_text_file,
    parse_pptx,
    parse_xlsx,
)
from backend.ingestion.doc_safety import (
    validate_pptx_safety,
    validate_xlsx_safety,
    validate_text_safety,
    IngestionSafetyError,
)
from backend.ingestion.file_signature import verify_signature, SignatureMismatchError


def test_parse_text_file_multilingual():
    content = (
        "## परिचय\n"
        "यह एक बहुभाषी दस्तावेज़ है जिसमें कृत्रिम बुद्धिमत्ता के नियम हैं।\n\n"
        "## Section 2: German Specifications\n"
        "Das System erfordert eine hochverfügbare Architektur mit Lastverteilung.\n\n"
        "## Section 3: Spanish Guidelines\n"
        "La confidencialidad de los datos empresariales es obligatoria según las normas.\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(content)
        temp_path = f.name

    try:
        records = parse_text_file(temp_path)
        assert len(records) >= 3

        # Verify language detection in metadata
        langs = [r["metadata"]["lang"] for r in records]
        scripts = [r["metadata"]["script"] for r in records]
        assert "hi" in langs or "Devanagari" in scripts
        assert "de" in langs or "es" in langs or "en" in langs

        # Check section awareness
        sections = [r["metadata"].get("section") for r in records]
        assert any(s and "German Specifications" in s for s in sections)
    finally:
        Path(temp_path).unlink(missing_ok=True)


def test_parse_pptx_slides_and_tables():
    prs = pptx.Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = "Enterprise AI Architecture"
    slide.placeholders[1].text = "Overview of distributed vector retrieval and LLM agents."

    # Add a second slide with a table
    slide2 = prs.slides.add_slide(prs.slide_layouts[5])
    slide2.shapes.title.text = "Model Specifications"
    table_shape = slide2.shapes.add_table(2, 2, Inches(1), Inches(1), Inches(4), Inches(2))
    table = table_shape.table
    table.cell(0, 0).text = "Model"
    table.cell(0, 1).text = "Parameters"
    table.cell(1, 0).text = "qwen3"
    table.cell(1, 1).text = "4B"

    with tempfile.NamedTemporaryFile(suffix=".pptx", delete=False) as f:
        temp_path = f.name
    prs.save(temp_path)

    try:
        # Validate file signature
        verify_signature(temp_path)
        validate_pptx_safety(temp_path)

        records = parse_pptx(temp_path)
        assert len(records) >= 2
        slide_numbers = [r["metadata"]["page"] for r in records]
        assert 1 in slide_numbers
        assert 2 in slide_numbers

        # Verify table record
        table_records = [r for r in records if r["metadata"].get("source_type") == "table"]
        assert len(table_records) >= 1
        assert "qwen3 | 4B" in table_records[0]["text"]
    finally:
        Path(temp_path).unlink(missing_ok=True)


def test_parse_xlsx_spreadsheet():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Q4 Financials"
    ws.append(["Department", "Budget", "Currency"])
    ws.append(["Engineering", "500000", "USD"])
    ws.append(["AI Research", "750000", "USD"])

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        temp_path = f.name
    wb.save(temp_path)

    try:
        verify_signature(temp_path)
        validate_xlsx_safety(temp_path)

        records = parse_xlsx(temp_path)
        assert len(records) >= 1
        assert records[0]["metadata"]["source_type"] == "spreadsheet"
        assert records[0]["metadata"]["section"] == "Q4 Financials"
        assert "AI Research | 750000 | USD" in records[0]["text"]
    finally:
        Path(temp_path).unlink(missing_ok=True)


def test_parse_document_dispatcher_integration():
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write("# Enterprise Policy\nAll data is encrypted in transit and at rest.")
        temp_path = f.name

    try:
        records = parse_document(temp_path)
        assert len(records) >= 1
        assert records[0]["metadata"]["file"] == Path(temp_path).name
        assert "char_count" in records[0]["metadata"]
        assert records[0]["metadata"]["char_count"] > 0
    finally:
        Path(temp_path).unlink(missing_ok=True)


def test_archive_safety_rejection():
    # A fake file with .xlsx extension but containing invalid bytes
    with tempfile.NamedTemporaryFile("w", suffix=".xlsx", delete=False) as f:
        f.write("This is not a zip archive")
        temp_path = f.name

    try:
        with pytest.raises(SignatureMismatchError):
            verify_signature(temp_path)

        with pytest.raises(IngestionSafetyError):
            validate_xlsx_safety(temp_path)
    finally:
        Path(temp_path).unlink(missing_ok=True)
