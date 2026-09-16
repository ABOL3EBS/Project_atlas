"""LLM-as-judge groundedness evaluator.

Determines whether a generated answer is fully supported by retrieved evidence.
Uses the local LLMProvider; never emits the judge prompt or evidence into any
trace. Returns None when the provider is unavailable or the response cannot be
parsed, so the caller can exclude the question from faithfulness aggregation.
"""

from __future__ import annotations

import json
import re

from app.llm.base import LLMProvider

_JUDGE_SYSTEM_PROMPT = (
    "You are a strict factuality evaluator. Given a QUESTION, EVIDENCE retrieved "
    "from a knowledge base, and an ANSWER produced from that evidence, decide "
    "whether the ANSWER is fully supported by the EVIDENCE.\n"
    "- grounded = true only if every factual claim in the ANSWER can be traced "
    "to information present in the EVIDENCE.\n"
    "- grounded = false if the ANSWER invents numbers, names, or facts not "
    "present in the EVIDENCE, or if the EVIDENCE is empty or irrelevant.\n"
    "Respond with ONLY a JSON object of the form {\"grounded\": true} or "
    "{\"grounded\": false}. No other text."
)

_MAX_EVIDENCE_CHARS = 1500
_MAX_ANSWER_CHARS = 2000


def _truncate(text: str, limit: int) -> str:
    return text[:limit] if len(text) <= limit else text[: limit - 3] + "..."


def _extract_json_object(raw: str) -> dict | None:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", cleaned, flags=re.DOTALL)
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _build_judge_prompt(
    question: str,
    evidence_texts: list[str],
    answer: str,
) -> str:
    evidence_lines = [
        f"[{i + 1}] {_truncate(text, 500)}" for i, text in enumerate(evidence_texts[:3])
    ]
    evidence_block = "\n".join(evidence_lines) if evidence_lines else "(no evidence provided)"
    answer_text = _truncate(answer, _MAX_ANSWER_CHARS)
    return (
        f"QUESTION:\n{question}\n\n"
        f"EVIDENCE:\n{evidence_block}\n\n"
        f"ANSWER:\n{answer_text}\n\n"
        "Is the answer grounded in the evidence? Reply ONLY with JSON: "
        '{"grounded": true} or {"grounded": false}.'
    )


class GroundednessJudge:
    """Thin wrapper around the local LLM provider for groundedness evaluation."""

    def __init__(self, llm_provider: LLMProvider) -> None:
        self._llm = llm_provider

    async def is_grounded(
        self,
        question: str,
        evidence_texts: list[str],
        answer: str,
    ) -> bool | None:
        """Return True if grounded, False if not, or None on parse/execution failure."""
        prompt = _build_judge_prompt(question, evidence_texts, answer)
        try:
            raw = await self._llm.generate(
                prompt, system=_JUDGE_SYSTEM_PROMPT, json_mode=True
            )
        except Exception:
            return None
        parsed = _extract_json_object(raw)
        if parsed is None:
            return None
        grounded = parsed.get("grounded")
        if isinstance(grounded, bool):
            return grounded
        if isinstance(grounded, str):
            lower = grounded.strip().lower()
            if lower in ("true", "1", "yes"):
                return True
            if lower in ("false", "0", "no"):
                return False
        return None
