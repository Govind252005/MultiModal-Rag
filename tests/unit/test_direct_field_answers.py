from backend.generation import answer
from backend.generation.answer import _direct_field_answer


def _answer(query, text):
    return _direct_field_answer(query, [{"text": text}], [{"index": 1}])


def test_pan_question_returns_only_value_and_citation():
    assert _answer("what's the PAN NO. mentioned in the document?",
                   "PAN NO.: CICPS3913E") == "CICPS3913E [1]"


def test_invoice_question_returns_only_value_and_citation():
    assert _answer("what's the invoice no mentioned in the document?",
                   "Invoice No: 02") == "02 [1]"


def test_total_amount_returns_only_amount_and_citation():
    assert _answer("what's the total amount mentioned?",
                   "TOTAL Rs 10000 /-") == "Rs 10000 /- [1]"


def test_invoice_reason_returns_only_reason_and_citation():
    assert _answer("what's the reason for this invoice?",
                   "Reasoning SSC") == "Reasoning SSC [1]"


def test_resume_key_expertise_returns_only_that_section():
    text = (
        "KEY EXPERTISE\n"
        "Javascript TypeScript Python C++ SQL HTML5 CSS React.js Tailwind CSS "
        "Node.js Express.js FastAPI REST APIs MySQL PostgreSQL Docker Git Github\n"
        "EDUCATION\nBhagwan Parshuram Institute of Technology"
    )
    result = _answer("which KEY EXPERTISE are mentioned in the document?", text)
    assert result.startswith("Javascript TypeScript Python")
    assert "EDUCATION" not in result
    assert result.endswith("[1]")


def test_resume_achievements_returns_only_that_section():
    text = (
        "ACHIEVEMENTS\n"
        "Won MAIT Hackathon\n"
        "Smart India Hackathon (SIH) 2024 & 2025- College Finalist\n"
        "PERSONAL INTERESTS / HOBBIES\nPlaying Cricket"
    )
    result = _answer("achievements in the document", text)
    assert "Won MAIT Hackathon" in result
    assert "Smart India Hackathon" in result
    assert "PERSONAL INTERESTS" not in result
    assert result.endswith("[1]")


def test_invoice_recipient_returns_only_value_and_citation():
    assert _answer("to whom this invoice is issued?",
                   "Issued To: Spectrum Books Pvt. Ltd.") == "Spectrum Books Pvt. Ltd. [1]"


def test_supervisor_question_returns_only_value_and_citation():
    assert _answer("what is the faculty supervisor?",
                   "Faculty Supervisor: Dr. Charu Gupta") == "Dr. Charu Gupta [1]"


def test_ambiguous_address_question_returns_both_addresses():
    text = (
        "Address: J-112, Gali no.-7, ramapark, Mohan Garden, NEW DELHI 110059\n"
        "Bill To: Spectrum Books Pvt. Ltd. A-1/291, 1st floor, Janak puri, New Delhi 110058"
    )
    result = _answer("what's the address mentioned in the document?", text)
    assert "Address: J-112" in result
    assert "Bill To: A-1/291" in result


def test_unrelated_question_stays_on_generation_path():
    assert _answer("what is this document about?", "An invoice for services") is None


def test_pan_answer_bypasses_llm_and_returns_grounded_value(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("LLM must not be called for an exact PAN field")

    monkeypatch.setattr(answer.router, "generate", fail_if_called)
    result = answer.answer_query(
        "what's the PAN NO. mentioned in the document?",
        [{"id": "1", "file": "invoice.pdf", "text": "PAN NO.: CICPS3913E", "score": 1.0}],
    )

    assert result["answer"] == "CICPS3913E [1]"
    assert result["used_llm"] is False


def test_only_answer_cited_sources_are_returned():
    result = answer.answer_query(
        "what's the total amount mentioned?",
        [
            {"id": "image", "file": "signature.png", "modality": "image",
             "text": "signature", "score": 0.9},
            {"id": "invoice", "file": "invoice.pdf", "modality": "document",
             "text": "TOTAL Rs 10000 /-", "score": 0.8},
        ],
    )

    assert result["answer"] == "Rs 10000 /- [1]"
    assert len(result["citations"]) == 1
    assert result["citations"][0]["file"] == "invoice.pdf"
