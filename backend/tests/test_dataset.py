from pathlib import Path

import pytest

from app.evaluation.corpus import EVAL_CHUNKING, chunk_corpus
from app.evaluation.dataset import EvaluationError, load_dataset

ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIR = ROOT / "knowledge" / "eval"
DATASET_PATH = ROOT / "evaluation" / "datasets" / "retrieval.json"

_chunks_per_document = chunk_corpus(CORPUS_DIR, EVAL_CHUNKING)


def test_dataset_size_within_spec_range():
    questions = load_dataset(DATASET_PATH)
    assert 20 <= len(questions) <= 50
    assert all(question.question.strip() for question in questions)
    assert all(question.expected_sources for question in questions)


def test_every_expected_source_exists_in_corpus():
    questions = load_dataset(DATASET_PATH)
    available = {path.name for path in CORPUS_DIR.glob("*.md")}
    for question in questions:
        for source in question.expected_sources:
            assert source in available, f"{source} for '{question.question}' not in corpus"


def test_corpus_parses_into_chunks_for_every_document():
    assert len(_chunks_per_document) >= 5
    for name, chunks in _chunks_per_document.items():
        assert chunks, f"{name} produced no chunks"
    total = sum(len(chunks) for chunks in _chunks_per_document.values())
    assert total >= 24, "corpus too small for discriminating top-k experiments"


def test_dataset_rejects_malformed_entries(tmp_path):
    malformed = tmp_path / "bad.json"
    malformed.write_text(
        '[{"question": "no sources here"}, {"expected_sources": ["a.md"]}]',
        encoding="utf-8",
    )
    with pytest.raises(EvaluationError):
        load_dataset(malformed)