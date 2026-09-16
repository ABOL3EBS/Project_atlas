"""Answer-generation evaluation: loaders, per-case metrics, threshold calibration.

Extends the M4 retrieval harness to the full AtlasAgent turn:
- unsupported-question rejection rate (not-found / unsupported)
- citation resolution (cited documents vs. expected_sources)
- LLM-as-judge faithfulness (in judge.py, consumer side here)
- grounding-threshold calibration via real search scores
- full-turn latency

Every number comes from actual agent or search runs; nothing is estimated.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .dataset import EvaluationError, load_dataset
from .metrics import mean, median, percentile

MIN_ANSWER_QUESTIONS = 20
MAX_ANSWER_QUESTIONS = 60


# ── Data models ────────────────────────────────────────────────────────

@dataclass
class AnswerQuestion:
    question: str
    expected_sources: list[str]
    unsupported: bool


@dataclass
class AnswerCase:
    question: str
    expected_sources: list[str]
    unsupported: bool
    source: str | None = None
    tool: str | None = None
    search_query: str | None = None
    answered: bool = False
    not_found: bool = False
    answer_text: str = ""
    citations: list[str] = field(default_factory=list)
    max_score: float | None = None
    calibration_score: float | None = None
    grounding_status: str | None = None
    latency_ms: float = 0.0
    error: str | None = None
    judge_grounded: bool | None = None

    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "expected_sources": self.expected_sources,
            "unsupported": self.unsupported,
            "source": self.source,
            "tool": self.tool,
            "search_query": self.search_query,
            "answered": self.answered,
            "not_found": self.not_found,
            "answer_text": self.answer_text[:500] if self.answer_text else "",
            "citations": self.citations,
            "max_score": self.max_score,
            "calibration_score": self.calibration_score,
            "grounding_status": self.grounding_status,
            "latency_ms": round(self.latency_ms, 3),
            "error": self.error,
            "judge_grounded": self.judge_grounded,
        }


@dataclass
class ThresholdPoint:
    threshold: float
    true_accept_rate: float
    false_accept_rate: float
    true_accept: int
    false_accept: int
    n_supported: int
    n_unsupported: int

    def to_dict(self) -> dict:
        return {
            "threshold": round(self.threshold, 3),
            "true_accept_rate": round(self.true_accept_rate, 4),
            "false_accept_rate": round(self.false_accept_rate, 4),
            "true_accept": self.true_accept,
            "false_accept": self.false_accept,
            "n_supported": self.n_supported,
            "n_unsupported": self.n_unsupported,
        }


@dataclass
class AnswerSummary:
    n_supported: int
    n_unsupported: int
    n_total: int
    unsupported_rejection_rate: float
    unsupported_answered_rate: float
    supported_answer_rate: float
    supported_direct_rate: float
    citation_precision: float
    citation_coverage: float
    faithfulness: float
    n_faithfulness_judged: int
    mean_latency_ms: float
    median_latency_ms: float
    p90_latency_ms: float
    per_case: list[AnswerCase] = field(default_factory=list)
    calibration: list[ThresholdPoint] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "n_supported": self.n_supported,
            "n_unsupported": self.n_unsupported,
            "n_total": self.n_total,
            "unsupported_rejection_rate": round(self.unsupported_rejection_rate, 4),
            "unsupported_answered_rate": round(self.unsupported_answered_rate, 4),
            "supported_answer_rate": round(self.supported_answer_rate, 4),
            "supported_direct_rate": round(self.supported_direct_rate, 4),
            "citation_precision": round(self.citation_precision, 4),
            "citation_coverage": round(self.citation_coverage, 4),
            "faithfulness": round(self.faithfulness, 4),
            "n_faithfulness_judged": self.n_faithfulness_judged,
            "mean_latency_ms": round(self.mean_latency_ms, 3),
            "median_latency_ms": round(self.median_latency_ms, 3),
            "p90_latency_ms": round(self.p90_latency_ms, 3),
            "calibration": [p.to_dict() for p in self.calibration],
        }


# ── Loaders ────────────────────────────────────────────────────────────

def load_answer_dataset(path: str | Path) -> list[AnswerQuestion]:
    """Load answer.json (unsupported-question augmentation set)."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise EvaluationError("Answer dataset must be a JSON list of questions")
    questions: list[AnswerQuestion] = []
    for index, entry in enumerate(raw):
        question = entry.get("question")
        expected = entry.get("expected_sources")
        unsupported = entry.get("unsupported")
        if not isinstance(question, str) or not question.strip():
            raise EvaluationError(f"Answer dataset entry {index} is missing a question")
        if not isinstance(expected, list) or not all(isinstance(x, str) for x in expected):
            raise EvaluationError(f"Answer dataset entry {index} has invalid expected_sources")
        if not isinstance(unsupported, bool) or (unsupported and expected):
            raise EvaluationError(
                f"Answer dataset entry {index}: unsupported questions must have "
                "empty expected_sources"
            )
        questions.append(
            AnswerQuestion(
                question=question.strip(),
                expected_sources=list(expected),
                unsupported=unsupported,
            )
        )
    if not (MIN_ANSWER_QUESTIONS <= len(questions) <= MAX_ANSWER_QUESTIONS):
        raise EvaluationError(
            f"Answer dataset must contain {MIN_ANSWER_QUESTIONS}-{MAX_ANSWER_QUESTIONS} questions, "
            f"found {len(questions)}"
        )
    return questions


def load_eval_questions(
    retrieval_dataset: str | Path,
    answer_dataset: str | Path,
) -> list[AnswerQuestion]:
    """Load supported (retrieval.json) + unsupported (answer.json) into AnswerQuestion list."""
    supported = load_dataset(retrieval_dataset)
    unsupported = load_answer_dataset(answer_dataset)
    combined: list[AnswerQuestion] = []
    for q in supported:
        combined.append(AnswerQuestion(q.question, q.expected_sources, False))
    for q in unsupported:
        combined.append(q)
    return combined


# ── Pure metrics ───────────────────────────────────────────────────────

def unsupported_rejection_rate(cases: list[AnswerCase]) -> float:
    unsupported = [c for c in cases if c.unsupported]
    if not unsupported:
        return 0.0
    return len([c for c in unsupported if c.not_found]) / len(unsupported)


def unsupported_answered_rate(cases: list[AnswerCase]) -> float:
    unsupported = [c for c in cases if c.unsupported]
    if not unsupported:
        return 0.0
    return len([c for c in unsupported if c.answered]) / len(unsupported)


def supported_answer_rate(cases: list[AnswerCase]) -> float:
    supported = [c for c in cases if not c.unsupported]
    if not supported:
        return 0.0
    return len([c for c in supported if c.answered]) / len(supported)


def supported_direct_rate(cases: list[AnswerCase]) -> float:
    supported = [c for c in cases if not c.unsupported]
    if not supported:
        return 0.0
    return len([c for c in supported if c.answered and c.source == "direct"]) / len(supported)


def citation_precision(cases: list[AnswerCase]) -> float:
    eligible = [
        c for c in cases
        if not c.unsupported
        and c.answered
        and c.source == "tool"
        and c.citations
        and c.expected_sources
    ]
    if not eligible:
        return 0.0
    precisions = []
    for c in eligible:
        expected_set = set(c.expected_sources)
        hits = sum(1 for cite in c.citations if cite in expected_set)
        precisions.append(hits / len(c.citations))
    return mean(precisions)


def citation_coverage(cases: list[AnswerCase]) -> float:
    eligible = [c for c in cases if not c.unsupported and c.answered and c.source == "tool"]
    if not eligible:
        return 0.0
    covered = sum(1 for c in eligible if any(cite in c.expected_sources for cite in c.citations))
    return covered / len(eligible)


def faithfulness_score(cases: list[AnswerCase]) -> tuple[float, int]:
    judged = [c for c in cases if c.judge_grounded is not None]
    if not judged:
        return 0.0, 0
    return mean([1.0 if c.judge_grounded else 0.0 for c in judged]), len(judged)


# ── Threshold calibration ──────────────────────────────────────────────

def calibrate_thresholds(
    supported_scores: list[float | None],
    unsupported_scores: list[float | None],
    thresholds: list[float],
) -> list[ThresholdPoint]:
    """Compute the grounding-gate accept curve over real search scores.

    Returns one ThresholdPoint per grid value.
    """
    n_supported = len(supported_scores)
    n_unsupported = len(unsupported_scores)
    points: list[ThresholdPoint] = []
    for t in thresholds:
        true_accept = sum(1 for s in supported_scores if s is not None and s >= t)
        false_accept = sum(1 for s in unsupported_scores if s is not None and s >= t)
        points.append(
            ThresholdPoint(
                threshold=t,
                true_accept_rate=true_accept / n_supported if n_supported else 0.0,
                false_accept_rate=false_accept / n_unsupported if n_unsupported else 0.0,
                true_accept=true_accept,
                false_accept=false_accept,
                n_supported=n_supported,
                n_unsupported=n_unsupported,
            )
        )
    return points


def recommend_threshold(points: list[ThresholdPoint]) -> tuple[float, str]:
    """Choose a threshold at the minimum false_accept_rate with highest true_accept.

    Returns (recommended_threshold, rationale).
    """
    if not points:
        return 0.45, "no calibration points available"
    min_false = min(p.false_accept_rate for p in points)
    candidates = [p for p in points if p.false_accept_rate == min_false]
    best = max(candidates, key=lambda p: (p.true_accept_rate, -p.threshold))
    rationale = (
        f"false_accept_rate={best.false_accept_rate:.4f} (minimum), "
        f"true_accept_rate={best.true_accept_rate:.4f} at threshold={best.threshold:.3f}"
    )
    return best.threshold, rationale


# ── Summary builder ────────────────────────────────────────────────────

def build_summary(
    cases: list[AnswerCase],
    calibration: list[ThresholdPoint] | None = None,
) -> AnswerSummary:
    faith, n_judged = faithfulness_score(cases)
    latencies = [c.latency_ms for c in cases]
    return AnswerSummary(
        n_supported=sum(1 for c in cases if not c.unsupported),
        n_unsupported=sum(1 for c in cases if c.unsupported),
        n_total=len(cases),
        unsupported_rejection_rate=unsupported_rejection_rate(cases),
        unsupported_answered_rate=unsupported_answered_rate(cases),
        supported_answer_rate=supported_answer_rate(cases),
        supported_direct_rate=supported_direct_rate(cases),
        citation_precision=citation_precision(cases),
        citation_coverage=citation_coverage(cases),
        faithfulness=faith,
        n_faithfulness_judged=n_judged,
        mean_latency_ms=mean(latencies),
        median_latency_ms=median(latencies),
        p90_latency_ms=percentile(latencies, 90),
        per_case=cases,
        calibration=calibration or [],
    )
