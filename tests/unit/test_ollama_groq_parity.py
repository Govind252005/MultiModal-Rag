import re
import pytest
from backend.generation.answer import answer_query
from backend.generation import prompt_templates
from backend.retrieval.search import _coalesce_and_diversify


def test_hindi_location_retrieval_and_answer():
    """Verify that Hindi location questions prioritize the exact physical destination
    (बरगद के पेड़) over vague general context (पुराने रिकॉर्ड)."""
    distractor_chunk = {
        "id": "c_preamble",
        "text": "गाँव के पुराने रिकॉर्ड और नक्शों से आने वाली जानकारी को सुरक्षित रखा गया था। पुस्तकालय में कई पुरानी पांडुलिपियाँ थीं।",
        "snippet": "गाँव के पुराने रिकॉर्ड और नक्शों से आने वाली जानकारी को सुरक्षित रखा गया था।",
        "file": "the_listening_house_story.pdf",
        "page": 1,
        "score": 0.88,
        "source_type": "text",
        "modality": "document",
    }

    destination_chunk = {
        "id": "c_destination",
        "text": "पुराने नक्शे ने उन्हें गाँव के बाहर स्थित बहुत पुराने बरगद के पेड़ तक पहुँचाया, जहाँ उन्होंने जड़ों के पास आधा दबा हुआ पत्थर देखा।",
        "snippet": "पुराने नक्शे ने उन्हें गाँव के बाहर स्थित बहुत पुराने बरगद के पेड़ तक पहुँचाया",
        "file": "the_listening_house_story.pdf",
        "page": 3,
        "score": 0.87,
        "source_type": "text",
        "modality": "document",
    }

    query = "पुराने नक्शे ने आरव और मीरा को कहाँ पहुँचाया?"
    
    # 1. Retrieval diversification check
    diversified = _coalesce_and_diversify([distractor_chunk, destination_chunk], top_k=5, query=query)
    assert len(diversified) >= 2
    assert diversified[0]["id"] == "c_destination"  # Destination promoted to #1

    # 2. Answer generation check
    res = answer_query(query, [dict(h) for h in diversified])
    ans = res.get("answer", "")
    citations = res.get("citations", [])

    assert prompt_templates.MISSING_CONTEXT_MESSAGE not in ans
    # Must specify banyan tree (बरगद के पेड़)
    assert any(w in ans for w in ["बरगद", "पेड़", "पेड़", "banyan", "tree"])
    assert ans.count("> **Supporting Evidence") == 1
    assert len(citations) >= 1
    ev_body = ans.split("> **Supporting Evidence [1]:**")[-1]
    assert any(w in ev_body for w in ["बरगद", "पेड़", "पेड़", "banyan"])


def test_multi_chapter_synthesis_coverage():
    """Verify that multi-chapter synthesis questions retain cross-page/chapter coverage
    across Chapter 1 (page 2), Chapter 4 (page 4), and Chapter 8 (page 8)."""
    ch1_hit_a = {
        "id": "ch1_a",
        "text": "Chapter 1: The Letter Beneath the Floorboards. The Listening House was established to conceal the hidden records of the 1912 river flood beneath the grandfather's study.",
        "snippet": "The Listening House was established to conceal the hidden records",
        "file": "the_listening_house_story.pdf",
        "page": 2,
        "score": 0.95,
        "source_type": "text",
        "modality": "document",
    }
    ch1_hit_b = {
        "id": "ch1_b",
        "text": "Mira Sen found a letter in the study describing how the water level markings had been altered by town officials.",
        "snippet": "water level markings had been altered",
        "file": "the_listening_house_story.pdf",
        "page": 2,
        "score": 0.93,
        "source_type": "text",
        "modality": "document",
    }
    ch4_hit = {
        "id": "ch4",
        "text": "Chapter 4: The Archive of Voices. The house was created as a sanctuary to preserve eyewitness testimonies and written accounts of residents before the council silenced them.",
        "snippet": "preserve eyewitness testimonies and written accounts",
        "file": "the_listening_house_story.pdf",
        "page": 4,
        "score": 0.90,
        "source_type": "text",
        "modality": "document",
    }
    ch8_hit = {
        "id": "ch8",
        "text": "Chapter 8: The Verdict of Stone. Dev built the Listening House to protect irreplaceable historical evidence and ensure future generations knew the town council's negligence.",
        "snippet": "protect irreplaceable historical evidence and ensure future generations knew",
        "file": "the_listening_house_story.pdf",
        "page": 8,
        "score": 0.89,
        "source_type": "text",
        "modality": "document",
    }

    query = "Why was the Listening House created?"

    # Retrieval diversification check
    candidates = [ch1_hit_a, ch1_hit_b, ch4_hit, ch8_hit]
    diversified = _coalesce_and_diversify(candidates, top_k=7, query=query)
    pages = [h.get("page") for h in diversified]

    # Verify Chapters 1 (page 2), 4 (page 4), and 8 (page 8) are all present in context
    assert 2 in pages
    assert 4 in pages
    assert 8 in pages

    # Answer generation synthesis check
    res = answer_query(query, [dict(h) for h in diversified])
    ans = res.get("answer", "")
    assert prompt_templates.MISSING_CONTEXT_MESSAGE not in ans
    ans_lower = ans.lower()
    # Must mention testimonies or preserving evidence or council negligence
    assert any(term in ans_lower for term in ["testimoni", "preserve", "protect", "evidence", "flood", "council"])


def test_zero_hallucination_grounding():
    """Verify that unsupported claims (such as 'planned relocation') are never hallucinated
    when asked about historical flood evidence."""
    flood_chunk = {
        "id": "c_flood",
        "text": (
            "In October 1912, the river breached the southern levee after four consecutive days of relentless rainfall. "
            "Town archives recorded that the flood damaged twelve warehouses and the lower mills. "
            "Dev Sen presented measurements showing the levee had cracked months earlier due to neglected masonry repairs. "
            "The town council refused to fund repairs, claiming the budget was exhausted."
        ),
        "snippet": "In October 1912, the river breached the southern levee after four consecutive days of relentless rainfall.",
        "file": "the_listening_house_story.pdf",
        "page": 5,
        "score": 0.95,
        "source_type": "text",
        "modality": "document",
    }

    query = "What does the evidence show behind the 1912 flood?"
    res = answer_query(query, [dict(flood_chunk)])
    ans = res.get("answer", "")

    assert prompt_templates.MISSING_CONTEXT_MESSAGE not in ans
    ans_lower = ans.lower()
    # Grounded facts
    assert any(term in ans_lower for term in ["breach", "rainfall", "levee", "warehouses", "neglect", "masonry", "repair"])
    # Zero hallucination guarantee: ensure ungrounded theories are absent
    assert "planned relocation" not in ans_lower
    assert "deliberate destruction" not in ans_lower


def test_statement_explanation_in_natural_language():
    """Verify that meaning/explanation questions produce a natural language explanation
    with citations rather than repeating only raw quotes."""
    quote_chunk = {
        "id": "c_dev_quote",
        "text": (
            "Dev Sen kept a journal in his clockmaker workshop. In one entry, he wrote: "
            "'A clock that never stops is merely keeping time; a clock that remembers is keeping truth.' "
            "He believed mechanisms should serve human memory rather than abstract hours."
        ),
        "snippet": "'A clock that never stops is merely keeping time; a clock that remembers is keeping truth.'",
        "file": "the_listening_house_story.pdf",
        "page": 6,
        "score": 0.92,
        "source_type": "text",
        "modality": "document",
    }

    query = "What is the meaning of Dev's statement about a clock that remembers?"
    res = answer_query(query, [dict(quote_chunk)])
    ans = res.get("answer", "")

    assert prompt_templates.MISSING_CONTEXT_MESSAGE not in ans
    # Must explain meaning in natural language
    assert any(term in ans.lower() for term in ["meaning", "means", "memory", "truth", "signif", "purpose", "reflect"])
    assert ans.count("> **Supporting Evidence") == 1


def test_hindi_library_two_items_no_scene_conflation():
    """Verify that Hindi library questions extract the items actually found in the library scene
    (लकड़ी की डिबिया... चिट्ठी और पीतल की छोटी चाबी) without conflating with subsequent scenes
    (सुंदरपुर का पुराना नक्शा or डायरी)."""
    chunk_1 = {
        "id": "c_library",
        "text": (
            "आरव को पुरानी चीज़ों के बारे में जानना बहुत पसंद था। एक दिन बारिश से बचने के लिए वह पुस्तकालय में चला गया। "
            "अंदर धूल से ढकी अलमारियाँ, पुराने नक्शे और पीले पड़ चुके कागज़ रखे थे। "
            "तभी उसकी नज़र एक छोटी मेज़ पर रखी लकड़ी की डिबिया पर पड़ी। डिबिया के भीतर एक चिट्ठी और पीतल की छोटी चाबी थी।"
        ),
        "snippet": "तभी उसकी नज़र एक छोटी मेज़ पर रखी लकड़ी की डिबिया पर पड़ी। डिबिया के भीतर एक चिट्ठी और पीतल की छोटी चाबी थी।",
        "file": "hindi_story_only.pdf",
        "page": 1,
        "score": 0.86,
        "source_type": "text",
        "modality": "document",
    }
    chunk_2 = {
        "id": "c_book_map",
        "text": (
            "अगली सुबह आरव अपने मित्र मीरा के साथ पुस्तकालय पहुँचा। दोनों ने अलमारियों में रखे कागज़ ध्यान से देखने शुरू किए। "
            "एक मोटी किताब के बीच उन्हें सुंदरपुर का पुराना नक्शा मिला। "
            "नक्शे पर नदी के पास एक छोटा-सा निशान बना था और उसके नीचे लिखा था—“जहाँ बरगद की छाया दोपहर में पत्थर को छूती है।”"
        ),
        "snippet": "एक मोटी किताब के बीच उन्हें सुंदरपुर का पुराना नक्शा मिला।",
        "file": "hindi_story_only.pdf",
        "page": 2,
        "score": 0.88,
        "source_type": "text",
        "modality": "document",
    }
    chunk_3 = {
        "id": "c_banyan_chest",
        "text": (
            "गाँव के बाहर एक बहुत पुराना बरगद का पेड़ था। आरव और मीरा वहाँ पहुँचे तो उन्हें जड़ों के पास आधा दबा हुआ पत्थर दिखाई दिया। "
            "नीचे लोहे का एक छोटा संदूक रखा था, लेकिन उस पर ताला लगा था। आरव ने जेब से पीतल की वही चाबी निकाली जो डिबिया में मिली थी। "
            "ताला खुल गया। संदूक के भीतर कुछ पुरानी तस्वीरें, एक डायरी और कागज़ों का बंडल था।"
        ),
        "snippet": "गाँव के बाहर एक बहुत पुराना बरगद का पेड़ था। आरव और मीरा वहाँ पहुँचे तो उन्हें जड़ों के पास आधा दबा हुआ पत्थर दिखाई दिया।",
        "file": "hindi_story_only.pdf",
        "page": 3,
        "score": 0.87,
        "source_type": "text",
        "modality": "document",
    }

    # Query 1: Which two things did Aarav find in the library?
    q1 = "आरव को पुस्तकालय में कौन-सी दो चीज़ें मिलीं?"
    diversified_1 = _coalesce_and_diversify([chunk_2, chunk_1, chunk_3], top_k=5, query=q1)
    
    # Assert Chunk 1 (library) is ranked #1 (hits[0]), NOT Chunk 2 (map)
    assert diversified_1[0]["id"] == "c_library"

    res_1 = answer_query(q1, [dict(h) for h in diversified_1])
    ans_1 = res_1.get("answer", "")
    citations_1 = res_1.get("citations", [])

    assert prompt_templates.MISSING_CONTEXT_MESSAGE not in ans_1
    # Must include चिट्ठी and चाबी (and/or डिबिया)
    assert ("चिट्ठी" in ans_1 and "चाबी" in ans_1) or "डिबिया" in ans_1
    # Must NOT conflate with items from other scenes or background scenery
    lead_part_1 = ans_1.split("> **Supporting Evidence")[0]
    assert "सुंदरपुर का पुराना नक्शा" not in lead_part_1
    assert "डायरी" not in lead_part_1
    assert "अलमारियों में रखे कागज़" not in lead_part_1
    # Supporting evidence must cite Chunk 1 (not Chunk 2 map)
    assert ans_1.count("> **Supporting Evidence") == 1
    ev_body_1 = ans_1.split("> **Supporting Evidence [1]:**")[-1]
    assert any(term in ev_body_1 for term in ["डिबिया", "चिट्ठी", "चाबी"])
    assert "सुंदरपुर का पुराना नक्शा" not in ev_body_1
    assert len(citations_1) >= 1

    # Query 2: Where did the old map lead Aarav and Mira?
    q2 = "पुराने नक्शे ने आरव और मीरा को कहाँ पहुँचाया?"
    diversified_2 = _coalesce_and_diversify([chunk_1, chunk_2, chunk_3], top_k=5, query=q2)
    # STILL ranks Chunk 3 (बरगद के पेड़) at #1
    assert diversified_2[0]["id"] == "c_banyan_chest"
    res_2 = answer_query(q2, [dict(h) for h in diversified_2])
    ans_2 = res_2.get("answer", "")
    assert prompt_templates.MISSING_CONTEXT_MESSAGE not in ans_2
    assert any(term in ans_2 for term in ["बरगद", "पेड़", "पेड़", "banyan"])

    # Query C: What was found in the iron chest?
    qc = "लोहे के संदूक में क्या मिला?"
    diversified_c = _coalesce_and_diversify([chunk_1, chunk_2, chunk_3], top_k=5, query=qc)
    # MUST rank Chunk 3 at #1 (locative anchor "संदूक")
    assert diversified_c[0]["id"] == "c_banyan_chest"
    res_c = answer_query(qc, [dict(h) for h in diversified_c])
    ans_c = res_c.get("answer", "")
    assert prompt_templates.MISSING_CONTEXT_MESSAGE not in ans_c
    assert "डायरी" in ans_c

    # Query D: What was written on the map near the river?
    qd = "नक्शे पर नदी के पास क्या लिखा था?"
    diversified_d = _coalesce_and_diversify([chunk_1, chunk_3, chunk_2], top_k=5, query=qd)
    # MUST rank Chunk 2 at #1 (locative anchor "नक्शे" / "नदी")
    assert diversified_d[0]["id"] == "c_book_map"
    res_d = answer_query(qd, [dict(h) for h in diversified_d])
    ans_d = res_d.get("answer", "")
    assert prompt_templates.MISSING_CONTEXT_MESSAGE not in ans_d
    assert "जहाँ बरगद की छाया दोपहर में पत्थर को छूती है" in ans_d


