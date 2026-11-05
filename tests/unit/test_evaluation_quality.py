from evaluation.judges.citation_judge import CitationJudge
from evaluation.metrics.retrieval_metrics import compute_roc_pr_auc


def test_inline_citation_presence_does_not_count_uncited_retrieved_sources():
    judge = CitationJudge()
    result = judge.judge_citations(
        generated_answer="The target is four hours [1].",
        cited_files=["policy.pdf", "unrelated.pdf"],
        required_citations=["policy.pdf"],
        retrieved_items=[
            {"file": "policy.pdf", "text": "The target is four hours."},
            {"file": "unrelated.pdf", "text": "Unrelated content."},
        ],
        available_citations=[
            {"index": 1, "file": "policy.pdf"},
            {"index": 2, "file": "unrelated.pdf"},
        ],
    )
    assert result["citation_present"] is True
    assert result["cited_files"] == ["policy.pdf"]
    assert result["source_level_precision"] == 1.0


def test_uncited_answer_is_not_marked_as_citation_present():
    judge = CitationJudge()
    result = judge.judge_citations(
        generated_answer="The target is four hours.",
        cited_files=["policy.pdf"],
        required_citations=["policy.pdf"],
        retrieved_items=[{"file": "policy.pdf", "text": "The target is four hours."}],
        available_citations=[{"index": 1, "file": "policy.pdf"}],
    )
    assert result["citation_present"] is False
    assert result["citation_completeness"] == 0.0


def test_roc_auc_ties_are_order_invariant():
    a = compute_roc_pr_auc([0.8, 0.8, 0.2, 0.1], [1, 0, 0, 1])
    b = compute_roc_pr_auc([0.8, 0.8, 0.2, 0.1], [0, 1, 0, 1])
    assert a["roc_auc"] == b["roc_auc"]
