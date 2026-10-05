"""
Unit tests for evaluation/metrics/retrieval_metrics.py.

Every expected value below was computed by hand (see the comments) and
cross-checked by running this exact test against the implementation before
committing it — not asserted blindly. Run with: pytest evaluation/metrics/
"""

import math

from evaluation.metrics import retrieval_metrics as rm

RETRIEVED = ["a", "b", "c", "d", "e"]
RELEVANT = {"b", "d", "f"}  # note: 'f' is never retrieved


def test_recall_at_k():
    assert abs(rm.recall_at_k(RETRIEVED, RELEVANT, 5) - 2 / 3) < 1e-9
    assert rm.recall_at_k(RETRIEVED, set(), 5) == 1.0  # nothing to miss


def test_precision_at_k():
    assert abs(rm.precision_at_k(RETRIEVED, RELEVANT, 5) - 2 / 5) < 1e-9
    assert rm.precision_at_k([], RELEVANT, 5) == 0.0


def test_duplicate_results_do_not_count_as_extra_ranks():
    assert rm.precision_at_k(["b", "b", "x"], {"b"}, 3) == 0.5
    assert rm.reciprocal_rank(["x", "b", "b"], {"b"}) == 0.5


def test_hit_rate_at_k():
    assert rm.hit_rate_at_k(RETRIEVED, RELEVANT, 1) == 0.0  # 'a' not relevant
    assert rm.hit_rate_at_k(RETRIEVED, RELEVANT, 3) == 1.0  # 'b' is relevant


def test_reciprocal_rank():
    # first relevant item ('b') is at rank 2 -> RR = 1/2
    assert abs(rm.reciprocal_rank(RETRIEVED, RELEVANT) - 0.5) < 1e-9
    assert rm.reciprocal_rank(RETRIEVED, {"z"}) == 0.0


def test_average_precision():
    # hits at rank 2 ('b'): precision 1/2; rank 4 ('d'): precision 2/4
    # AP = (0.5 + 0.5) / |relevant|(3) = 1/3
    assert abs(rm.average_precision(RETRIEVED, RELEVANT) - 1 / 3) < 1e-9


def test_ndcg_at_k():
    rel_by_id = {i: 1.0 for i in RELEVANT}
    expected_dcg = 1 / math.log2(3) + 1 / math.log2(5)  # b@rank2, d@rank4
    ideal_dcg = 1 / math.log2(2) + 1 / math.log2(3) + 1 / math.log2(4)
    expected = expected_dcg / ideal_dcg
    assert abs(rm.ndcg_at_k(RETRIEVED, rel_by_id, 5) - expected) < 1e-9


def test_precision_recall_f1():
    out = rm.precision_recall_f1(true_positive=8, false_positive=2, false_negative=4)
    assert abs(out["precision"] - 0.8) < 1e-9
    assert abs(out["recall"] - 2 / 3) < 1e-9
    assert abs(out["f1"] - 2 * 0.8 * (2 / 3) / (0.8 + 2 / 3)) < 1e-9


def test_token_f1():
    out = rm.token_f1("the cat sat on the mat", "the cat sat on a mat")
    # predicted has 6 tokens, all but none... overlap: 'the','cat','sat','on','mat' each
    # matched against reference multiset {the:1,cat:1,sat:1,on:1,a:1,mat:1}
    # predicted: the,cat,sat,on,the,mat -> matches: the(1),cat(1),sat(1),on(1),the(0 - already consumed),mat(1) = 5
    assert out["precision"] == 5 / 6
    assert out["recall"] == 5 / 6


def test_exact_match():
    assert rm.exact_match("Paris", "paris") == 1.0
    assert rm.exact_match("Paris", "London") == 0.0


def test_roc_auc_perfect_separation():
    roc = rm.roc_curve([0.9, 0.8, 0.3, 0.1], [1, 1, 0, 0])
    assert roc["applicable"] is True
    assert abs(roc["auc"] - 1.0) < 1e-9


def test_roc_auc_undefined_when_one_class():
    roc = rm.roc_curve([0.5, 0.6], [1, 1])
    assert roc["applicable"] is False


def test_roc_auc_is_invariant_to_tie_order():
    first = rm.compute_roc_pr_auc([0.8, 0.8, 0.2, 0.1], [1, 0, 0, 1])
    second = rm.compute_roc_pr_auc([0.8, 0.8, 0.2, 0.1], [0, 1, 0, 1])
    assert first["roc_auc"] == second["roc_auc"]


def test_mrr_rejects_mismatched_query_counts():
    try:
        rm.mrr([["a"]], [])
    except ValueError as exc:
        assert "equal length" in str(exc)
    else:
        raise AssertionError("mrr should reject mismatched query collections")


def test_mrr_and_map_aggregate_correctly():
    mrr_val = rm.mrr([RETRIEVED, ["x", "y"]], [RELEVANT, {"z"}])
    assert abs(mrr_val - (0.5 + 0.0) / 2) < 1e-9
    map_val = rm.mean_average_precision([RETRIEVED], [RELEVANT])
    assert abs(map_val - rm.average_precision(RETRIEVED, RELEVANT)) < 1e-9
