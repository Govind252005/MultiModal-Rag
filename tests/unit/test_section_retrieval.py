from backend.ingestion.pdf_docx_parser import _section_segments
from backend.retrieval.search import _requested_section, _visual_query


def test_section_segments_assigns_content_without_page_assumptions():
    segments, _ = _section_segments(
        "Title\n\nIntroduction\nintro text\n\nAbstract\nterms and findings"
    )

    assert ("introduction", "intro text") in segments
    assert ("abstract", "terms and findings") in segments


def test_requested_section_detects_abstract():
    assert _requested_section("what are the terminologies mentioned in the abstract") == "abstract"


def test_visual_retrieval_is_query_sensitive():
    assert _visual_query("what does the figure show")
    assert not _visual_query("what are the terminologies in the abstract")
