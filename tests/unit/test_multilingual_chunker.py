"""
Unit Test Suite: Multilingual Sentence Segmentation and Chunking (Phase 4.2).
Tests Hindi Devanagari punctuation (।, ॥), Arabic (؟, ۔), English abbreviations,
Markdown tables, and overlap preservation.
"""

import pytest
from backend.ingestion import chunker


def test_hindi_devanagari_sentence_segmentation():
    """Verify that Hindi sentences ending with Danda (।) and Double Danda (॥) are accurately split."""
    hindi_text = (
        "कृत्रिम बुद्धिमत्ता आधुनिक युग की सबसे शक्तिशाली तकनीक है। "
        "यह चिकित्सा, शिक्षा और कृषि में क्रांतिकारी परिवर्तन ला रही है। "
        "क्या हम इसके सभी पहलुओं को समझते हैं? "
        "सत्यमेव जयते नानृतम्॥"
    )
    sentences = chunker._split_unicode_sentences(hindi_text)

    assert len(sentences) == 4
    assert sentences[0] == "कृत्रिम बुद्धिमत्ता आधुनिक युग की सबसे शक्तिशाली तकनीक है।"
    assert sentences[1] == "यह चिकित्सा, शिक्षा और कृषि में क्रांतिकारी परिवर्तन ला रही है।"
    assert sentences[2] == "क्या हम इसके सभी पहलुओं को समझते हैं?"
    assert sentences[3] == "सत्यमेव जयते नानृतम्॥"


def test_arabic_sentence_segmentation():
    """Verify Arabic sentence segmentation on question mark (؟) and full stop (۔)."""
    arabic_text = "هل يمكن للذكاء الاصطناعي معالجة اللغة العربية؟ نعم، بالتأكيد۔ هذا نظام متعدد اللغات."
    sentences = chunker._split_unicode_sentences(arabic_text)

    assert len(sentences) == 3
    assert "؟" in sentences[0]
    assert "۔" in sentences[1]


def test_english_abbreviations_and_numbers_not_split():
    """Verify abbreviations like Dr., e.g., and decimals 3.14 are not mistaken for sentence ends."""
    text = "Dr. Smith met with Mr. Jones at approx. 3.14 p.m. in the U.S. office. They discussed project Titan."
    sentences = chunker._split_unicode_sentences(text)

    assert len(sentences) == 2
    assert "Dr. Smith met with Mr. Jones" in sentences[0]
    assert sentences[1] == "They discussed project Titan."


def test_unicode_closing_quotations_preserved():
    """Verify closing quotes and brackets stay with the preceding sentence."""
    text = 'He shouted, "Stop!" Then he ran. She agreed: “It is done.” Next chapter begins.'
    sentences = chunker._split_unicode_sentences(text)

    assert len(sentences) == 4
    assert sentences[0] == 'He shouted, "Stop!"'
    assert sentences[1] == "Then he ran."
    assert sentences[2] == "She agreed: “It is done.”"
    assert sentences[3] == "Next chapter begins."


def test_markdown_tables_preserved_intact():
    """Verify that table blocks are not fragmented into disjoint chunks."""
    table_text = (
        "| Metric | Score | Status |\n"
        "| --- | --- | --- |\n"
        "| Recall@5 | 0.95 | Passed |\n"
        "| MRR | 0.88 | Passed |"
    )
    chunks = chunker.chunk_text(table_text, size=100, overlap=10)

    assert len(chunks) == 1
    assert "| Recall@5 | 0.95 | Passed |" in chunks[0]
    assert "| MRR | 0.88 | Passed |" in chunks[0]


def test_chunking_with_overlap():
    """Verify sentences pack into chunks with configurable overlap."""
    text = (
        "Sentence one is here. "
        "Sentence two is also here. "
        "Sentence three provides more detail. "
        "Sentence four concludes the section."
    )
    chunks = chunker.chunk_text(text, size=10, overlap=4)

    assert len(chunks) >= 2
    # Second chunk should retain overlap from previous sentence
    assert any("Sentence" in c for c in chunks)

