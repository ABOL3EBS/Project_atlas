import asyncio
import json
from pathlib import Path

import pytest

from app.evaluation.answer_eval import (
    AnswerCase,
    EvaluationError,
    build_summary,
    calibrate_thresholds,
    citation_coverage,
    citation_precision,
    faithfulness_score,
    load_answer_dataset,
    load_eval_questions,
    recommend_threshold,
    supported_answer_rate,
    supported_direct_rate,
    unsupported_answered_rate,
    unsupported_rejection_rate,
)
from app.evaluation.judge import GroundednessJudge, _extract_json_object

ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = ROOT / "evaluation" / "datasets" / "retrieval.json"
ANSWER_DATASET_PATH = ROOT / "evaluation" / "datasets" / "answer.json"
CORPUS_DIR = ROOT / "knowledge" / "eval"


def _case(**kwargs) -> AnswerCase:
    defaults = dict(
        question="q",
        expected_sources=["solar_panels.md"],
        unsupported=False,
        source="tool",
        tool="search_knowledge_base",
        answered=False,
        not_found=False,
        answer_text="",
        citations=[],
        max_score=None,
        grounding_status=None,
        latency_ms=10.0,
        error=None,
        judge_grounded=None,
    )
    defaults.update(kwargs)
    return AnswerCase(**defaults)


# ── Dataset loading ────────────────────────────────────────────────────

def test_answer_dataset_has_expected_unsupported_schema():
    questions = load_answer_dataset(ANSWER_DATASET_PATH)
    assert len(questions) == 20
    assert all(q.unsupported for q in questions)
    assert all(q.expected_sources == [] for q in questions)


def test_load_eval_questions_combines_sources():
    questions = load_eval_questions(DATASET_PATH, ANSWER_DATASET_PATH)
    assert len(questions) == 68
    assert sum(not q.unsupported for q in questions) == 48
    assert sum(q.unsupported for q in questions) == 20
    supported = [q for q in questions if not q.unsupported]
    assert all(q.expected_sources for q in supported)


def test_answer_dataset_rejects_unsupported_with_sources(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps(
            [
                {"question": "x", "expected_sources": ["a.md"], "unsupported": True}
                for _ in range(20)
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(EvaluationError):
        load_answer_dataset(path)


def test_answer_dataset_rejects_non_bool_flag(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps(
            [
                {"question": f"q{i}", "expected_sources": [], "unsupported": "yes"}
                for i in range(20)
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(EvaluationError):
        load_answer_dataset(path)


def test_answer_dataset_size_bound(tmp_path):
    path = tmp_path / "tiny.json"
    path.write_text(
        json.dumps(
            [
                {"question": f"q{i}", "expected_sources": [], "unsupported": True}
                for i in range(5)
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(EvaluationError):
        load_answer_dataset(path)


def test_every_unsupported_question_is_out_of_domain():
    questions = load_answer_dataset(ANSWER_DATASET_PATH)
    corpus_topics = {
        path.stem for path in CORPUS_DIR.glob("*.md") if path.is_file()
    }
    question = [q.question.lower() for q in questions][0]
    assert question  # dataset non-empty
    for q in questions:
        lowered = q.question.lower()
        assert not any(topic in lowered for topic in corpus_topics), q.question


# ── Pure metrics ───────────────────────────────────────────────────────

def test_unsupported_rejection_and_false_accept():
    cases = [
        _case(unsupported=True, not_found=True, answered=False),
        _case(unsupported=True, not_found=True, answered=False),
        _case(unsupported=True, not_found=False, answered=True, answer_text="yes"),
    ]
    assert unsupported_rejection_rate(cases) == pytest.approx(2 / 3)
    assert unsupported_answered_rate(cases) == pytest.approx(1 / 3)


def test_supported_answer_and_direct_rates():
    cases = [
        _case(answered=True, source="tool", answer_text="a"),
        _case(answered=True, source="direct", answer_text="b"),
        _case(answered=False, not_found=True),
    ]
    assert supported_answer_rate(cases) == pytest.approx(2 / 3)
    assert supported_direct_rate(cases) == pytest.approx(1 / 3)


def test_citation_precision_only_over_cited_tool_answers():
    cases = [
        _case(
            expected_sources=["a.md"],
            answered=True,
            citations=["a.md", "b.md"],
            source="tool",
        ),
        _case(
            expected_sources=["a.md"],
            answered=True,
            citations=["a.md"],
            source="tool",
        ),
        _case(
            expected_sources=[],
            answered=True,
            citations=["b.md"],
            source="tool",
        ),  # no expected_sources
        _case(answered=True, citations=["a.md"], source="direct"),  # direct excluded
    ]
    assert citation_precision(cases) == pytest.approx((0.5 + 1.0) / 2)


def test_citation_coverage():
    cases = [
        _case(expected_sources=["a.md"], answered=True, citations=["a.md"], source="tool"),
        _case(expected_sources=["a.md"], answered=True, citations=["b.md"], source="tool"),
        _case(answered=True, citations=[], source="tool"),
    ]
    assert citation_coverage(cases) == pytest.approx(1 / 3)


def test_faithfulness_skips_unjudged():
    cases = [
        _case(answered=True, judge_grounded=True),
        _case(answered=True, judge_grounded=False),
        _case(answered=True, judge_grounded=None),
    ]
    truth, n = faithfulness_score(cases)
    assert truth == pytest.approx(0.5)
    assert n == 2


def test_summary_aggregates_latencies():
    cases = [
        _case(latency_ms=100.0),
        _case(latency_ms=200.0),
        _case(unsupported=True, not_found=True, latency_ms=300.0),
    ]
    summary = build_summary(cases)
    assert summary.n_supported == 2
    assert summary.n_unsupported == 1
    assert summary.mean_latency_ms == pytest.approx(200.0)
    assert summary.median_latency_ms == pytest.approx(200.0)


# ── Threshold calibration ──────────────────────────────────────────────

def test_calibrate_thresholds_trade_off():
    supported = [0.62, 0.58, None, 0.36]
    unsupported = [0.44, 0.47, 0.31, None]
    points = calibrate_thresholds(supported, unsupported, [0.30, 0.50, 0.60])
    by_t = {p.threshold: p for p in points}
    assert by_t[0.30].true_accept_rate == pytest.approx(3 / 4)
    assert by_t[0.50].true_accept_rate == pytest.approx(2 / 4)
    assert by_t[0.60].true_accept_rate == pytest.approx(1 / 4)
    assert by_t[0.30].false_accept_rate == pytest.approx(3 / 4)
    assert by_t[0.50].false_accept_rate == pytest.approx(0.0)
    assert by_t[0.60].false_accept_rate == pytest.approx(0.0)


def test_recommend_threshold_prefers_low_false_accept():
    points = calibrate_thresholds(
        [0.62, 0.58, None, 0.36], [0.44, 0.47], [0.35, 0.45, 0.55]
    )
    recommended, rationale = recommend_threshold(points)
    assert recommended == pytest.approx(0.55)
    assert "false_accept" in rationale


# ── Judge parsing ──────────────────────────────────────────────────────

def test_extract_json_object_plain():
    assert _extract_json_object('{"grounded": true}') == {"grounded": True}


def test_extract_json_object_fenced():
    assert _extract_json_object('```json\n{"grounded": false}\n```') == {"grounded": False}


def test_extract_json_object_embedded_in_prose():
    raw = "Sure! Here you go:\n{\"grounded\": true}\nHope that helps."
    assert _extract_json_object(raw) == {"grounded": True}


def test_extract_json_object_malformed_returns_none():
    assert _extract_json_object("not json at all") is None
    assert _extract_json_object('{"grounded": ') is None


class _ScriptedJudgeLLM:
    def __init__(self, responses):
        self._responses = list(responses)

    async def generate(self, prompt, *, system=None, json_mode=False):
        return self._responses.pop(0)

    def stream(self, prompt, *, system=None):
        raise NotImplementedError

    def check(self):
        return True


def test_judge_parses_grounded_and_not():
    llm = _ScriptedJudgeLLM(['{"grounded": true}', '{"grounded": false}'])
    judge = GroundednessJudge(llm)
    assert asyncio.run(judge.is_grounded("q", ["evidence"], "answer")) is True
    assert asyncio.run(judge.is_grounded("q", ["evidence"], "answer")) is False


def test_judge_returns_none_on_unparseable_or_error():
    llm = _ScriptedJudgeLLM(["gibberish"])

    class _Boom(_ScriptedJudgeLLM):
        async def generate(self, prompt, *, system=None, json_mode=False):
            raise RuntimeError("provider down")

    judge = GroundednessJudge(llm)
    assert asyncio.run(judge.is_grounded("q", ["evidence"], "answer")) is None
    assert asyncio.run(judge.is_grounded("q", ["evidence"], "answer")) is None
    judge2 = GroundednessJudge(_Boom([]))
    assert asyncio.run(judge2.is_grounded("q", ["evidence"], "answer")) is None


def test_judge_evidence_truncation():
    llm = _ScriptedJudgeLLM(['{"grounded": true}'])
    judge = GroundednessJudge(llm)
    long_evidence = ["x" * 2000]
    long_answer = "y" * 5000
    assert asyncio.run(judge.is_grounded("q", long_evidence, long_answer)) is True