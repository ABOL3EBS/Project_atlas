from app.evaluation.metrics import (
    mean,
    median,
    mrr,
    mrr_documents,
    percentile,
    recall_at_documents,
    recall_at_k,
)


def test_recall_at_k_counts_expected_documents_in_top_k():
    ranked = ["a.md", "b.md", "c.md", "d.md"]
    expected = ["a.md", "d.md"]
    assert recall_at_k(ranked, expected, k=5) == 1.0
    assert recall_at_k(ranked, expected, k=1) == 0.5
    assert recall_at_k(ranked, expected, k=2) == 0.5
    assert recall_at_k(ranked, expected, k=3) == 0.5


def test_recall_at_k_no_overlap():
    assert recall_at_k(["x.md"], ["y.md"], k=5) == 0.0


def test_recall_at_k_empty_expected_counts_as_hit():
    assert recall_at_k([], [], k=5) == 1.0


def test_recall_at_documents_deduplicates_ranks():
    ranked = ["a.md", "a.md", "b.md"]
    assert recall_at_documents(ranked, ["a.md", "b.md"], k=3) == 1.0
    assert recall_at_documents(ranked, ["a.md"], k=2) == 1.0


def test_mrr_uses_first_relevant_rank():
    assert mrr(["c.md", "a.md", "b.md"], ["a.md", "b.md"]) == 0.5
    assert mrr(["c.md", "d.md"], ["a.md"]) == 0.0
    assert mrr(["a.md"], ["a.md"]) == 1.0


def test_mrr_documents_deduplicates_ranks():
    ranked = ["b.md", "a.md", "b.md"]
    assert mrr_documents(ranked, ["b.md"]) == 1.0
    assert mrr_documents(ranked, ["a.md"]) == 0.5


def test_mean_median_percentile():
    values = [10.0, 20.0, 30.0, 40.0]
    assert mean(values) == 25.0
    assert mean([]) == 0.0
    assert median(values) == 25.0
    assert median([1.0]) == 1.0
    assert median([]) == 0.0
    assert percentile(values, 50) == 25.0
    assert percentile(values, 0) == 10.0
    assert percentile(values, 100) == 40.0
    assert percentile([], 90) == 0.0