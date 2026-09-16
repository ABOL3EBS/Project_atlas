"""Run the M6 answer-evaluation experiment and report measured results.

Usage (from anywhere):

    uv run python evaluation/runners/run_answer_eval.py

Runs the full `AtlasAgent` turn over the labelled question set (the M4
retrieval.json supported questions plus the answer.json unsupported questions),
measures unsupported-question rejection, citation resolution, LLM-as-judge
faithfulness, and full-turn latency, and calibrates `grounding_threshold`
over a real score grid. Every number in the printed table and the JSON files
under evaluation/results/ is produced by running the actual system against the
actual dataset; nothing is estimated or fabricated.

The E2E pass uses the current grounding threshold (settings default 0.45) and
the real production retrieval path. The calibration table separately measures
the grounding *gate* conditioned on search, using real embedding scores, so its
accept/reject predictions are exact for any numeric threshold (search scores do
not depend on the threshold; only the accept decision does).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.agent.agent import AtlasAgent  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.embeddings.ollama_provider import OllamaEmbeddingProvider  # noqa: E402
from app.evaluation.answer_eval import (  # noqa: E402
    AnswerCase,
    build_summary,
    calibrate_thresholds,
    load_eval_questions,
    recommend_threshold,
)
from app.evaluation.corpus import EVAL_CHUNKING  # noqa: E402
from app.evaluation.judge import GroundednessJudge  # noqa: E402
from app.ingestion import ChunkingConfig, chunk_document, parse_document  # noqa: E402
from app.llm.ollama_provider import OllamaProvider  # noqa: E402
from app.retrieval.chroma_store import ChromaVectorStore  # noqa: E402
from app.retrieval.retriever import Retriever  # noqa: E402
from app.services.ingestion_service import sanitize_filename  # noqa: E402

SEARCH_TOP_K = 4


class EvalDocumentStore:
    """Roster of the eval-corpus documents for the planner.

    The eval corpus is read straight from knowledge/eval/ (like run_retrieval.py)
    rather than through the upload pipeline, so the agent needs an equivalent of
    the persisted document store: just the indexed-document list the planner uses
    to decide between search/retrieve/compare.
    """

    def __init__(self, documents: dict[str, dict]):
        self._rows = sorted(
            (
                {"id": meta["id"], "name": name, "status": "indexed"}
                for name, meta in documents.items()
            ),
            key=lambda row: row["name"],
        )

    def list(self, knowledge_base_id: str) -> list[dict]:
        return list(self._rows)


def build_index(
    corpus_dir: Path,
    data_dir: Path,
    embedding_provider: OllamaEmbeddingProvider,
    chunking_config: ChunkingConfig,
) -> tuple[ChromaVectorStore, str, dict[str, dict]]:
    knowledge_base_id = "eval"
    if data_dir.exists():
        shutil.rmtree(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    vector_store = ChromaVectorStore(str(data_dir))

    documents: dict[str, dict] = {}
    for path in sorted(corpus_dir.glob("*.md")):
        document_id = f"eval_{sanitize_filename(path.stem)}"
        content = path.read_bytes()
        pages = parse_document(path.name, content)
        chunks = chunk_document(document_id, path.name, pages, chunking_config)
        documents[path.name] = {"id": document_id, "chunks": chunks}
        embeddings = embedding_provider.embed_documents([chunk.text for chunk in chunks])
        vector_store.add_chunks(knowledge_base_id, chunks, embeddings)
        print(f"[index] {path.name}: {len(chunks)} chunks")
    total = sum(len(meta["chunks"]) for meta in documents.values())
    print(f"[index] total {total} chunks in knowledge base '{knowledge_base_id}'")
    return vector_store, knowledge_base_id, documents


def fetch_evidence_texts(chunks: list) -> list[str]:
    if not chunks:
        return []
    return [f"({chunk.document_name}) {chunk.text}" for chunk in chunks][:3]


async def run_case(
    agent: AtlasAgent, knowledge_base_id: str, query: str
) -> AnswerCase:
    answer_text = ""
    case = AnswerCase(question=query, expected_sources=[], unsupported=False)
    started = time.perf_counter()
    try:
        async for event in agent.run(knowledge_base_id, query):
            kind = event.get("type")
            if kind == "decision":
                case.source = event.get("source")
                case.tool = event.get("tool")
                case.search_query = event.get("arguments", {}).get("query")
            elif kind == "grounding":
                case.grounding_status = event.get("status")
                case.max_score = event.get("score")
            elif kind == "answer":
                case.not_found = True
            elif kind == "citation":
                case.citations = [
                    citation.get("document_name")
                    for citation in event.get("citations", [])
                    if citation.get("document_name")
                ]
            elif kind == "done":
                case.citations = [
                    citation.get("document_name")
                    for citation in event.get("citations", [])
                    if citation.get("document_name")
                ]
            elif kind == "token":
                answer_text += event.get("text", "")
            elif kind == "error":
                case.error = event.get("message")
    except Exception as error:  # pragma: no cover - defensive
        case.error = f"{type(error).__name__}: {error}"
    case.latency_ms = (time.perf_counter() - started) * 1000.0
    case.answer_text = answer_text
    case.answered = not case.not_found and bool(answer_text.strip())
    return case


async def run_eval(args: argparse.Namespace) -> None:
    chunking_config = ChunkingConfig(
        chunk_size=args.chunk_size, chunk_overlap=args.chunk_overlap
    )
    embedding_provider = OllamaEmbeddingProvider(args.base_url, args.embedding_model)
    if not embedding_provider.check():
        raise SystemExit(f"Embedding provider unreachable at {args.base_url}")
    llm_provider = OllamaProvider(args.base_url, args.llm_model)
    if not llm_provider.check():
        raise SystemExit(f"LLM provider unreachable at {args.base_url}")

    vector_store, knowledge_base_id, documents = build_index(
        args.corpus, args.data_dir, embedding_provider, chunking_config
    )
    retriever = Retriever(vector_store, embedding_provider, top_k=SEARCH_TOP_K)
    agent = AtlasAgent(
        retriever=retriever,
        llm_provider=llm_provider,
        vector_store=vector_store,
        document_store=EvalDocumentStore(documents),
        grounding_threshold=args.threshold,
    )
    judge = GroundednessJudge(llm_provider)

    questions = load_eval_questions(args.dataset, args.answer_dataset)
    print(f"[dataset] {len(questions)} questions "
          f"({sum(not q.unsupported for q in questions)} supported / "
          f"{sum(q.unsupported for q in questions)} unsupported)")

    selected = questions[: args.limit] if args.limit else questions
    cases: list[AnswerCase] = []
    supported_scores: list[float | None] = []
    unsupported_scores: list[float | None] = []

    for question in selected:
        case = await run_case(agent, knowledge_base_id, question.question)
        case.question = question.question
        case.expected_sources = list(question.expected_sources)
        case.unsupported = question.unsupported

        searched = retriever.search(
            knowledge_base_id, question.question, top_k=SEARCH_TOP_K
        )
        case.calibration_score = max(
            (chunk.score for chunk in searched), default=None
        )
        cases.append(case)
        (unsupported_scores if case.unsupported else supported_scores).append(
            case.calibration_score
        )

        if (
            not case.unsupported
            and case.answered
            and case.source == "tool"
            and not args.skip_judge
        ):
            evidence_texts = fetch_evidence_texts(searched)
            case.judge_grounded = await judge.is_grounded(
                question.question, evidence_texts, case.answer_text
            )
            verdict = (
                "grounded" if case.judge_grounded
                else "NOT_grounded" if case.judge_grounded is False
                else "judge_failed"
            )
            print(f"  [judge] {verdict:<13} {question.question[:55]}")
        print(
            f"[case] {'UNSUPPORTED' if case.unsupported else 'SUPPORTED':<10} "
            f"{'ANSWER' if case.answered else 'NOT_FOUND':<9} "
            f"{'direct' if case.source == 'direct' else case.tool or '-':<22} "
            f"score={(case.max_score if case.max_score is not None else '-'):<7}"
            f"latency={case.latency_ms:6.0f}ms  {question.question[:50]}"
        )

    calibration = calibrate_thresholds(
        supported_scores, unsupported_scores, args.thresholds
    )
    recommended, rationale = recommend_threshold(calibration)
    summary = build_summary(cases, calibration)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "answer-per-question.json").write_text(
        json.dumps([case.to_dict() for case in cases], indent=2) + "\n",
        encoding="utf-8",
    )
    summary_dict = summary.to_dict()
    summary_dict["recommended_threshold"] = round(recommended, 3)
    summary_dict["recommended_rationale"] = rationale
    summary_dict["grounding_threshold_used_e2e"] = args.threshold
    (args.out_dir / "answer-summary.json").write_text(
        json.dumps(summary_dict, indent=2) + "\n",
        encoding="utf-8",
    )
    print(_render(summary, recommended, rationale))


def _render(summary, recommended: float, rationale: str) -> str:
    lines = [
        "M6 answer-evaluation summary (real runs)",
        "=" * 60,
        f" questions                : {summary.n_total}"
        f" ({summary.n_supported} supported /"
        f" {summary.n_unsupported} unsupported)",
        f" unsupported rejection    :"
        f" {summary.unsupported_rejection_rate:.4f}",
        f" unsupported answered     :"
        f" {summary.unsupported_answered_rate:.4f}"
        f" (false accepts at E2E)",
        f" supported answer rate    :"
        f" {summary.supported_answer_rate:.4f}",
        f" supported answered direct:"
        f" {summary.supported_direct_rate:.4f}"
        f" (planner, no search)",
        f" citation precision       :"
        f" {summary.citation_precision:.4f}",
        f" citation coverage        :"
        f" {summary.citation_coverage:.4f}",
        f" faithfulness (judge)     : {summary.faithfulness:.4f}"
        f" (n={summary.n_faithfulness_judged})",
        f" latency mean/med/p90 (ms):"
        f" {summary.mean_latency_ms:.1f}"
        f" / {summary.median_latency_ms:.1f}"
        f" / {summary.p90_latency_ms:.1f}",
        "",
        "Threshold calibration"
        " (grounding gate, conditioned on real search scores)",
        f" {'threshold':<10}{'true_accept':>14}{'false_accept':>14}",
        "-" * 38,
    ]
    for point in summary.calibration:
        lines.append(
            f" {point.threshold:<10.3f}"
            f"{point.true_accept_rate:>13.4f}"
            f"{point.false_accept_rate:>14.4f}"
        )
    lines.append(f"\n recommended threshold: {recommended:.3f}  ({rationale})")
    return "\n".join(lines)


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Run Atlas answer-evaluation experiment")
    parser.add_argument("--corpus", type=Path, default=REPO_ROOT / "knowledge" / "eval")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=REPO_ROOT / "evaluation" / "datasets" / "retrieval.json",
        help="supported-question dataset (expected_sources)",
    )
    parser.add_argument(
        "--answer-dataset",
        type=Path,
        default=REPO_ROOT / "evaluation" / "datasets" / "answer.json",
        help="unsupported-question dataset",
    )
    parser.add_argument(
        "--out-dir", type=Path, default=REPO_ROOT / "evaluation" / "results"
    )
    parser.add_argument(
        "--data-dir", type=Path, default=BACKEND_DIR / "data" / "eval_chroma"
    )
    parser.add_argument("--base-url", default=settings.ollama_base_url)
    parser.add_argument("--embedding-model", default=settings.embedding_model)
    parser.add_argument(
        "--llm-model",
        default="gemma2:2b",
        help="LLM used for the agent planner/generation and the judge (defaults to "
        "the M4 eval provider gemma2:2b, which is installed; settings.llm_model "
        "defaults to an uninstalled 'gemma2' alias)",
    )
    parser.add_argument("--threshold", type=float, default=settings.grounding_threshold)
    parser.add_argument(
        "--thresholds",
        type=lambda value: [float(x) for x in value.split(",")],
        default=[0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65],
        help="comma-separated threshold grid for calibration",
    )
    parser.add_argument(
        "--chunk-size", type=int, default=EVAL_CHUNKING.chunk_size
    )
    parser.add_argument(
        "--chunk-overlap", type=int, default=EVAL_CHUNKING.chunk_overlap
    )
    parser.add_argument("--limit", type=int, default=0, help="run only first N questions")
    parser.add_argument("--skip-judge", action="store_true", help="skip LLM-as-judge pass")
    args = parser.parse_args()

    asyncio.run(run_eval(args))


if __name__ == "__main__":
    main()