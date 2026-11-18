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


def test_submitted_by_question_extracts_author_name():
    text = (
        "SOFTWARE VERIFICATION, VALIDATION AND TESTING\n"
        "SVVT PRACTICAL FILE\n"
        "Submitted by\n"
        "GOVIND SHREELOCHAN (00720802723)\n"
        "CSE-A | Batch 2023-2027"
    )
    result = _answer("who submitted this document?", text)
    assert "GOVIND SHREELOCHAN (00720802723)" in result
    assert "[1]" in result


def test_audio_inquiry_extracts_transcript_and_summary():
    hit = {
        "id": "aud1",
        "file": "Recording.m4a",
        "modality": "audio",
        "source_type": "transcript",
        "timestamp": "0:00",
        "text": "This document is submitted by Govind Shilajan under the supervision of Nisha Madan.",
        "score": 0.95,
    }
    citations = [{"index": 1, "file": "Recording.m4a"}]
    res = _direct_field_answer("what is in this audio?", [hit], citations)
    assert res is not None
    assert "Govind Shilajan" in res
    assert "Nisha Madan" in res
    assert "[1]" in res


def test_common_name_between_audio_and_doc():
    aud_hit = {
        "id": "aud1",
        "file": "Recording.m4a",
        "modality": "audio",
        "source_type": "transcript",
        "text": "This document is submitted by Govind Shilajan under the supervision of Nisha Madan.",
        "score": 0.99,
    }
    doc_hit = {
        "id": "doc1",
        "file": "SVVT_Practical_File.pdf",
        "modality": "document",
        "source_type": "text",
        "page": 1,
        "text": "Submitted by\nGOVIND SHREELOCHAN (00720802723)\nUnder the supervision of\nTANISHA MADAN",
        "score": 0.98,
    }
    citations = [
        {"index": 1, "file": "Recording.m4a", "modality": "audio"},
        {"index": 2, "file": "SVVT_Practical_File.pdf", "modality": "document"},
    ]
    res = _direct_field_answer("is there any common name between these two ?", [aud_hit, doc_hit], citations)
    assert res is not None
    assert "Govind" in res
    assert "Madan" in res
    assert "[1]" in res
    assert "[2]" in res


def test_cpp_code_extraction_experiment_4():
    sample_code_chunk = (
        "[Section Context: EXPERIMENT 4: Non-Functional Testing of Triangle | Page 11]\n"
        "C++ Program: triangle_quality.cpp \n"
        "#include <iostream>\n"
        "using namespace std;\n"
        "string classify(long long x,long long y,long long z){\n"
        " if(x<=0||y<=0||z<=0)return \"Not a Triangle\";\n"
        " if(x+y<=z||x+z<=y||y+z<=x)return \"Not a Triangle\";\n"
        " if(x==y&&y==z)return \"Equilateral\";\n"
        " if(x==y||y==z||x==z)return \"Isosceles\";\n"
        " return \"Scalene\";\n"
        "}\n"
        "int main(){\n"
        " long long x,y,z;cout<<\"Enter sides (1..100): \";\n"
        " if(!(cin>>x>>y>>z)){cout<<\"Invalid input format\\n\";return 0;}\n"
        " if(x<1||x>100||y<1||y>100||z<1||z>100){cout<<\"Invalid input: sides must be in [1,100]\\n\";return 0;}\n"
        " cout<<classify(x,y,z)<<\"\\n\";\n"
        "} \n"
        "Performance Testing \n"
        "Performance checks response time, execution time, repeated runs and workload behaviour."
    )
    hit = {"text": sample_code_chunk, "file": "SVVT_Practical_File.pdf", "page": 11, "section": "EXPERIMENT 4"}
    cits = [{"index": 1, "file": "SVVT_Practical_File.pdf"}]
    res = _direct_field_answer("Give me the C++ code from experiment 4.", [hit], cits)
    assert res is not None
    assert "triangle_quality.cpp" in res
    assert "string classify" in res
    assert "Enter sides (1..100)" in res
    assert "Performance Testing" not in res
    assert res.endswith("[1]")


def test_hindi_supervisor_query_extracts_supervisor_not_submitter():
    cover_page_text = (
        "SOFTWARE VERIFICATION, VALIDATION AND TESTING\n"
        "SVVT PRACTICAL FILE\n"
        "Submitted by\n"
        "GOVIND SHREELOCHAN (00720802723)\n"
        "CSE-A | Batch 2023-2027\n"
        "Under the supervision of\n"
        "TANISHA MADAN\n"
        "Faculty / Subject Instructor"
    )
    hit = {"text": cover_page_text, "file": "SVVT_Practical_File.pdf", "page": 1}
    cits = [{"index": 1, "file": "SVVT_Practical_File.pdf"}]
    res = _direct_field_answer("यह दस्तावेज़ किसकी देखरेख में जमा किया गया है?", [hit], cits)
    assert res is not None
    # Must identify Tanisha Madan, NOT Govind Shreelochan
    assert "तनीषा" in res or "TANISHA" in res
    assert "मदान" in res or "MADAN" in res
    assert "देखरेख" in res
    assert "> **Supporting Evidence [1]:**" in res
    assert "Under the supervision of" in res
    # Ensure answer sentence does not state Govind was the supervisor
    answer_lead = res.split("\n\n")[0]
    assert "गोविंद" not in answer_lead
    assert "GOVIND" not in answer_lead


def test_universal_supporting_evidence_appended_to_llm_answer():
    story_text = (
        "During the stormy autumn evening in Ravenswood Manor, "
        "Mira Sen found a letter beneath the loose floorboard in her grandfather's study. "
        "The parchment bore an ornate wax seal with the initials V.R."
    )
    llm_answer = "Mira Sen discovered the mysterious letter beneath the floorboard [1]."
    hit = {"text": story_text, "file": "mystery_story.pdf", "page": 3}
    enhanced = answer._append_universal_supporting_evidence(
        llm_answer,
        [hit],
        query="Who discovered the mysterious letter beneath the floorboard?",
    )
    assert "> **Supporting Evidence [1]:**" in enhanced
    assert "Mira Sen" in enhanced
    assert "floorboard" in enhanced
    assert "grandfather's study" in enhanced


def test_split_multi_chunk_tables_retain_headers():
    from backend.ingestion.chunker import chunk_text
    table_rows = ["| Experiment | Name | Date | Status | Score |", "| --- | --- | --- | --- | --- |"]
    for i in range(1, 45):
        table_rows.append(f"| Exp {i} | Test Case {i} Implementation | 2026-11-13 | PASS | 100/100 |")
    large_table = "\n".join(table_rows)

    chunks = chunk_text(large_table)
    assert len(chunks) >= 2
    for c in chunks:
        assert "| Experiment | Name | Date | Status | Score |" in c
        assert "| --- | --- | --- | --- | --- |" in c


def test_cpp_code_block_remains_intact_across_helper_and_main():
    from backend.ingestion.chunker import chunk_text
    cpp_code = (
        "#include <iostream>\n"
        "using namespace std;\n\n"
        "string classify(long long x, long long y, long long z) {\n"
        "    if (x <= 0 || y <= 0 || z <= 0) return \"Not a Triangle\";\n"
        "    if (x + y <= z || x + z <= y || y + z <= x) return \"Not a Triangle\";\n"
        "    if (x == y && y == z) return \"Equilateral\";\n"
        "    if (x == y || y == z || x == z) return \"Isosceles\";\n"
        "    return \"Scalene\";\n"
        "}\n\n"
        "int main() {\n"
        "    long long x, y, z;\n"
        "    if (!(cin >> x >> y >> z)) return 0;\n"
        "    cout << classify(x, y, z) << endl;\n"
        "    return 0;\n"
        "}"
    )
    chunks = chunk_text(cpp_code)
    # Both helper function and main must remain in the same chunk
    assert len(chunks) == 1
    assert "string classify" in chunks[0]
    assert "int main()" in chunks[0]


def test_listening_house_story_pdf_answers_and_evidence_banner():
    """Verify that narrative questions with synonyms (discovered/found) and hypernyms (profession/clockmaker)
    extract the exact factual answers with > **Supporting Evidence [1]:** on the_listening_house_story.pdf text."""
    import re
    from backend.generation.answer import answer_query, _semantic_extractive_rescue
    from backend.generation import prompt_templates

    distractor_chunk_0 = (
        "Dev had tried to reveal it once, but the town council had refused to listen. "
        "The archive doors were locked every evening at dusk."
    )

    story_chunk_1 = (
        "[Section Context: Chapter 1: The Letter Beneath the Floorboards | Page 2]\n"
        "THE LISTENING HOUSE\n"
        "Page 2\n"
        "Chapter 1: The Letter Beneath the Floorboards\n"
        "On the morning the river changed direction, Mira Sen found a letter beneath the loose floorboard in\n"
        "her grandfather’s study. "
        "The river did not truly reverse, of course. It only appeared to flow uphill because a storm had pushed a wall of water into the narrow channel. "
        "But in the town of Bellwether, people preferred the stranger explanation. They had always believed the river listened to secrets.\n"
        "Mira was sixteen and had spent most of her life asking questions that adults answered with stories. "
        "Her grandfather, Dev Sen, had been the town’s clockmaker. He had died the previous winter, leaving behind a workshop full of clocks that all showed different times."
    )

    hits = [
        {
            "id": "c0",
            "text": distractor_chunk_0,
            "snippet": distractor_chunk_0,
            "file": "the_listening_house_story.pdf",
            "page": 1,
            "score": 0.96,
            "source_type": "text",
            "modality": "document",
        },
        {
            "id": "c1",
            "text": story_chunk_1,
            "snippet": story_chunk_1[:300],
            "file": "the_listening_house_story.pdf",
            "page": 2,
            "score": 0.95,
            "source_type": "text",
            "modality": "document",
        },
    ]

    # Query A: Who discovered the mysterious letter beneath the floorboard?
    q_a = "Who discovered the mysterious letter beneath the floorboard?"
    res_a = answer_query(q_a, [dict(h) for h in hits])
    ans_a = res_a.get("answer", "")
    citations_a = res_a.get("citations", [])

    assert prompt_templates.MISSING_CONTEXT_MESSAGE not in ans_a
    assert ans_a.count("> **Supporting Evidence") == 1
    assert "[Section Context:" not in ans_a
    assert "Dev had tried to reveal it once" not in ans_a
    assert "On the morning the river changed direction" in ans_a
    # Ensure "On the morning the river changed direction" IS inside the blockquote
    ev_match_a = re.search(r">\s*\*\*Supporting Evidence \[1\]:\*\*\n([\s\S]+)", ans_a)
    assert ev_match_a is not None
    assert "On the morning the river changed direction" in ev_match_a.group(1)
    assert len(citations_a) >= 1
    assert "Mira Sen found a letter" in (citations_a[0].get("snippet") or "")

    # Query B: What was Mira's grandfather's profession?
    q_b = "What was Mira's grandfather's profession?"
    res_b = answer_query(q_b, [dict(h) for h in hits])
    ans_b = res_b.get("answer", "")
    citations_b = res_b.get("citations", [])

    assert prompt_templates.MISSING_CONTEXT_MESSAGE not in ans_b
    assert "clockmaker" in ans_b.lower()
    assert ans_b.count("> **Supporting Evidence") == 1
    assert "[Section Context:" not in ans_b
    assert "clockmaker" in (citations_b[0].get("snippet") or "").lower()

    # Query C: What was Mira's grandfather's name?
    q_c = "What was Mira's grandfather's name?"
    res_c = answer_query(q_c, [dict(h) for h in hits])
    ans_c = res_c.get("answer", "")
    citations_c = res_c.get("citations", [])

    assert prompt_templates.MISSING_CONTEXT_MESSAGE not in ans_c
    assert "Dev Sen" in ans_c
    # Critical: Ensure "Mira was sixteen..." is NOT selected as the answer!
    assert "Mira was sixteen" not in ans_c.split("> **Supporting Evidence")[0]
    assert ans_c.count("> **Supporting Evidence") == 1
    assert "[Section Context:" not in ans_c
    assert "Dev Sen" in ans_c.split("> **Supporting Evidence [1]:**")[1]
    assert "Dev Sen" in (citations_c[0].get("snippet") or "")

    # Verify unanswerable query correctly returns None from semantic rescue (no false positives)
    q_unanswerable = "What was the name of the captain of the spaceship?"
    res_unanswerable_rescue = _semantic_extractive_rescue(q_unanswerable, [dict(h) for h in hits])
    assert res_unanswerable_rescue is None


def test_medical_lab_report_hba1c_and_evidence_banner():
    """Verify numeric values and laboratory diagnostic metrics extract accurately across domains."""
    from backend.generation.answer import answer_query
    from backend.generation import prompt_templates

    med_chunk = (
        "[Section Context: Comprehensive Metabolic & Glycemic Panel | Page 1]\n"
        "METROPOLIS DIAGNOSTICS LABORATORY\n"
        "Patient Name: John Doe    Age: 48    Gender: Male\n"
        "Test Name: Glycated Hemoglobin (HbA1c)\n"
        "Result: 7.2 %\n"
        "Reference Range: Normal < 5.7 %, Prediabetes 5.7 - 6.4 %, Diabetes >= 6.5 %\n"
        "Interpretation: Glycemic control indicates elevated average blood glucose over past 3 months."
    )
    hits = [{
        "id": "med_1",
        "text": med_chunk,
        "snippet": med_chunk[:200],
        "file": "lab_report_john_doe.pdf",
        "page": 1,
        "score": 0.95,
        "source_type": "text",
        "modality": "document",
    }]

    res = answer_query("What is the patient's HbA1c level?", hits)
    ans = res.get("answer", "")
    assert prompt_templates.MISSING_CONTEXT_MESSAGE not in ans
    assert "7.2" in ans
    assert ans.count("> **Supporting Evidence") == 1
    assert "[Section Context:" not in ans


def test_police_fir_legal_section_and_evidence_banner():
    """Verify legal/police FIR section code retrieval and clean supporting evidence banner."""
    from backend.generation.answer import answer_query
    from backend.generation import prompt_templates

    legal_chunk = (
        "[Section Context: First Information Report | Station: Vasant Kunj]\n"
        "DELHI POLICE DEPARTMENT - FIRST INFORMATION REPORT (FIR)\n"
        "FIR No: 0214/2026    Date: 04-10-2026\n"
        "Acts and Sections: Section 379 IPC (Theft), Section 411 IPC (Dishonestly receiving stolen property).\n"
        "Place of Occurrence: Sector C Pocket 2 Vasant Kunj.\n"
        "Brief Description: The complainant reported theft of a two-wheeler vehicle from parking area."
    )
    hits = [{
        "id": "fir_1",
        "text": legal_chunk,
        "snippet": legal_chunk[:200],
        "file": "delhi_police_fir_0214.pdf",
        "page": 1,
        "score": 0.92,
        "source_type": "text",
        "modality": "document",
    }]

    res = answer_query("Under which IPC sections was the FIR registered?", hits)
    ans = res.get("answer", "")
    assert prompt_templates.MISSING_CONTEXT_MESSAGE not in ans
    assert "379" in ans
    assert ans.count("> **Supporting Evidence") == 1
    assert "[Section Context:" not in ans




