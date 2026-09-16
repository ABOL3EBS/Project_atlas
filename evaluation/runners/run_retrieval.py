"""Run the M4 retrieval experiments and report measured results.

Usage (from anywhere):

    uv run python evaluation/runners/run_retrieval.py

Every number in the printed table and the JSON files under evaluation/results/
is produced by running the actual pipeline against the actual dataset; nothing
is estimated or fabricated.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import get_settings  # noqa: E402
from app.embeddings.ollama_provider import OllamaEmbeddingProvider  # noqa: E402
from app.evaluation.corpus import EVAL_CHUNKING  # noqa: E402
from app.evaluation.dataset import (  # noqa: E402
    evaluate_question,
    load_dataset,
    summarize,
)
from app.ingestion import ChunkingConfig, chunk_document, parse_document  # noqa: E402
from app.llm.ollama_provider import OllamaProvider  # noqa: E402
from app.retrieval.chroma_store import ChromaVectorStore  # noqa: E402
from app.retrieval.pipelines import (  # noqa: E402
    BM25Reranker,
    LLMMultiQueryTransformer,
    LLMQueryRewriter,
    baseline_search,
    multi_query_search,
    reranked_search,
    rewrite_search,
)
from app.retrieval.retriever import Retriever  # noqa: E402
from app.services.ingestion_service import sanitize_filename  # noqa: E402


def build_index(
    corpus_dir: Path,
    data_dir: Path,
    embedding_provider: OllamaEmbeddingProvider,
    chunking_config: ChunkingConfig,
) -> tuple[ChromaVectorStore, str, list[str]]:
    knowledge_base_id = "eval"
    if data_dir.exists():
        shutil.rmtree(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    vector_store = ChromaVectorStore(str(data_dir))

    corpus_chunks: list[str] = []
    index = 0
    for path in sorted(corpus_dir.glob("*.md")):
        document_id = f"eval_{sanitize_filename(path.stem)}"
        content = path.read_bytes()
        pages = parse_document(path.name, content)
        chunks = chunk_document(document_id, path.name, pages, chunking_config)
        corpus_chunks.extend(chunk.text for chunk in chunks)
        embeddings = embedding_provider.embed_documents([chunk.text for chunk in chunks])
        vector_store.add_chunks(knowledge_base_id, chunks, embeddings)
        index += len(chunks)
        print(f"[index] {path.name}: {len(chunks)} chunks")
    print(f"[index] total {index} chunks in knowledge base '{knowledge_base_id}'")
    return vector_store, knowledge_base_id, corpus_chunks


def latency_total(timings: dict[str, float]) -> float:
    return sum(timings.values())


async def run_pipeline(
    pipeline: str,
    retriever: Retriever,
    questions,
    knowledge_base_id: str,
    llm_provider,
    reranker,
    top_k: int,
    candidates: int,
    variants: int,
) -> list:
    per_query = []
    for item in questions:
        begin = asyncio.get_running_loop().time()
        if pipeline == "baseline":
            result = baseline_search(retriever, knowledge_base_id, item.question, top_k)
        elif pipeline == "rewrite":
            transformer = LLMQueryRewriter(llm_provider)
            result = await rewrite_search(
                retriever, transformer, knowledge_base_id, item.question, top_k
            )
        elif pipeline == "rerank":
            result = reranked_search(
                retriever, reranker, knowledge_base_id, item.question, top_k, candidates
            )
        else:
            transformer = LLMMultiQueryTransformer(llm_provider, variants=variants)
            result = await multi_query_search(
                retriever, transformer, reranker, knowledge_base_id, item.question, top_k,
                candidates,
            )
        wall_time = (asyncio.get_running_loop().time() - begin) * 1000.0
        per_query.append(
            evaluate_question(item.question, item.expected_sources, result.results, wall_time)
        )
    return per_query


def render_table(summaries: list) -> str:
    header = (
        f"{'Pipeline':<26}{'Recall@5':>10}{'MRR':>9}{'Latency (ms)':>14}"
    )
    separator = "-" * len(header)
    lines = [header, separator]
    for summary in summaries:
        lines.append(
            f"{summary.pipeline:<26}{summary.recall_at_5:>10.4f}"
            f"{summary.mrr:>9.4f}{summary.mean_latency_ms:>14.1f}"
        )
    lines.append(separator)
    lines.append(f"Dataset: {summaries[0].n_questions} questions; means across queries.")
    lines.append("Latency is per-query wall time including every pipeline stage.")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Atlas retrieval experiments")
    settings = get_settings()
    parser.add_argument("--corpus", type=Path, default=REPO_ROOT / "knowledge" / "eval")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=REPO_ROOT / "evaluation" / "datasets" / "retrieval.json",
    )
    parser.add_argument(
        "--out-dir", type=Path, default=REPO_ROOT / "evaluation" / "results"
    )
    parser.add_argument(
        "--data-dir", type=Path, default=BACKEND_DIR / "data" / "eval_chroma"
    )
    parser.add_argument("--base-url", default=settings.ollama_base_url)
    parser.add_argument("--embedding-model", default=settings.embedding_model)
    parser.add_argument("--llm-model", default=settings.llm_model)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--candidates", type=int, default=25)
    parser.add_argument("--variants", type=int, default=3)
    parser.add_argument(
        "--chunk-size", type=int, default=EVAL_CHUNKING.chunk_size
    )
    parser.add_argument(
        "--chunk-overlap", type=int, default=EVAL_CHUNKING.chunk_overlap
    )
    parser.add_argument(
        "--pipeline",
        choices=["baseline", "rewrite", "rerank", "multi"],
        nargs="+",
        default=["baseline", "rewrite", "rerank", "multi"],
    )
    args = parser.parse_args()

    chunking_config = ChunkingConfig(
        chunk_size=args.chunk_size, chunk_overlap=args.chunk_overlap
    )
    embedding_provider = OllamaEmbeddingProvider(args.base_url, args.embedding_model)
    if not embedding_provider.check():
        raise SystemExit(f"Embedding provider unreachable at {args.base_url}")

    vector_store, knowledge_base_id, corpus_texts = build_index(
        args.corpus, args.data_dir, embedding_provider, chunking_config
    )
    retriever = Retriever(vector_store, embedding_provider, top_k=args.top_k)
    reranker = BM25Reranker(corpus_texts)
    llm_provider = OllamaProvider(args.base_url, args.llm_model)

    questions = load_dataset(args.dataset)
    print(f"[dataset] {len(questions)} questions from {args.dataset.name}")

    summaries = []
    for pipeline in args.pipeline:
        print(f"[run] {pipeline} ...")
        per_query = asyncio.run(
            run_pipeline(
                pipeline,
                retriever,
                questions,
                knowledge_base_id,
                llm_provider,
                reranker,
                args.top_k,
                args.candidates,
                args.variants,
            )
        )
        summary = summarize(pipeline, per_query)
        summaries.append(summary)
        args.out_dir.mkdir(parents=True, exist_ok=True)
        (args.out_dir / f"retrieval-{pipeline}.json").write_text(
            json.dumps(summary.to_dict(), indent=2) + "\n", encoding="utf-8"
        )

    (args.out_dir / "retrieval-summary.json").write_text(
        json.dumps([summary.to_dict() for summary in summaries], indent=2) + "\n",
        encoding="utf-8",
    )
    table = render_table(summaries)
    print("\n" + table)
    print(f"\nWrote results to {args.out_dir / 'retrieval-summary.json'}")


if __name__ == "__main__":
    main()