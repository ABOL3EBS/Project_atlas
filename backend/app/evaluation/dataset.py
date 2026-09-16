"""Evaluation dataset loading and per-query metric evaluation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.retrieval.retriever import RetrievedChunk

from .metrics import mean, median, mrr_documents, percentile, recall_at_documents

MIN_QUESTIONS = 20
MAX_QUESTIONS = 50


@dataclass
class EvalQuestion:
    question: str
    expected_sources: list[str]


class EvaluationError(ValueError):
    pass


def load_dataset(path: str | Path) -> list[EvalQuestion]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise EvaluationError("Dataset must be a JSON list of questions")
    questions: list[EvalQuestion] = []
    for index, entry in enumerate(raw):
        question = entry.get("question")
        expected = entry.get("expected_sources")
        if not isinstance(question, str) or not question.strip():
            raise EvaluationError(f"Dataset entry {index} is missing a question")
        if not isinstance(expected, list) or not all(isinstance(item, str) for item in expected):
            raise EvaluationError(f"Dataset entry {index} has invalid expected_sources")
        questions.append(EvalQuestion(question=question.strip(), expected_sources=list(expected)))
    if not (MIN_QUESTIONS <= len(questions) <= MAX_QUESTIONS):
        raise EvaluationError(
            f"Dataset must contain {MIN_QUESTIONS}-{MAX_QUESTIONS} questions, "
            f"found {len(questions)}"
        )
    return questions


@dataclass
class QueryMetrics:
    question: str
    expected_sources: list[str]
    ranked_documents: list[str]
    recall_at_5: float
    mrr: float
    latency_ms: float

    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "expected_sources": self.expected_sources,
            "ranked_documents": self.ranked_documents,
            "recall_at_5": self.recall_at_5,
            "mrr": self.mrr,
            "latency_ms": round(self.latency_ms, 3),
        }


def rank_documents(results: list[RetrievedChunk]) -> list[str]:
    document_names: list[str] = []
    seen: set[str] = set()
    for chunk in results:
        if chunk.document_name not in seen:
            seen.add(chunk.document_name)
            document_names.append(chunk.document_name)
    return document_names


def evaluate_question(
    question: str,
    expected_sources: list[str],
    results: list[RetrievedChunk],
    latency_ms: float,
) -> QueryMetrics:
    ranked = rank_documents(results)
    return QueryMetrics(
        question=question,
        expected_sources=expected_sources,
        ranked_documents=ranked,
        recall_at_5=recall_at_documents(ranked, expected_sources, k=5),
        mrr=mrr_documents(ranked, expected_sources),
        latency_ms=latency_ms,
    )


@dataclass
class ExperimentSummary:
    pipeline: str
    n_questions: int
    recall_at_5: float
    mrr: float
    mean_latency_ms: float
    median_latency_ms: float
    p90_latency_ms: float
    per_query: list[QueryMetrics]

    def to_dict(self) -> dict:
        return {
            "pipeline": self.pipeline,
            "n_questions": self.n_questions,
            "recall_at_5": round(self.recall_at_5, 4),
            "mrr": round(self.mrr, 4),
            "mean_latency_ms": round(self.mean_latency_ms, 3),
            "median_latency_ms": round(self.median_latency_ms, 3),
            "p90_latency_ms": round(self.p90_latency_ms, 3),
            "per_query": [item.to_dict() for item in self.per_query],
        }


def summarize(pipeline: str, per_query: list[QueryMetrics]) -> ExperimentSummary:
    return ExperimentSummary(
        pipeline=pipeline,
        n_questions=len(per_query),
        recall_at_5=mean([item.recall_at_5 for item in per_query]),
        mrr=mean([item.mrr for item in per_query]),
        mean_latency_ms=mean([item.latency_ms for item in per_query]),
        median_latency_ms=median([item.latency_ms for item in per_query]),
        p90_latency_ms=percentile([item.latency_ms for item in per_query], 90),
        per_query=per_query,
    )