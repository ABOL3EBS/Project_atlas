"""Shared eval-corpus configuration and chunking helper.

Chunk size is an explicit experiment dimension (see ATLAS_PROJECT_SPEC.md section
19). The eval corpus uses a smaller chunk than the production default so that
top-k selection over the corpus is actually discriminating instead of trivial.
"""

from __future__ import annotations

from pathlib import Path

from app.ingestion import ChunkingConfig, chunk_document, parse_document
from app.services.ingestion_service import sanitize_filename

EVAL_CHUNK_SIZE = 250
EVAL_CHUNK_OVERLAP = 25
EVAL_CHUNKING = ChunkingConfig(chunk_size=EVAL_CHUNK_SIZE, chunk_overlap=EVAL_CHUNK_OVERLAP)


def chunk_corpus(
    corpus_dir: str | Path, chunking: ChunkingConfig | None = None
) -> dict[str, list[str]]:
    documents: dict[str, list[str]] = {}
    for path in sorted(Path(corpus_dir).glob("*.md")):
        document_id = f"eval_{sanitize_filename(path.stem)}"
        pages = parse_document(path.name, path.read_bytes())
        chunks = chunk_document(document_id, path.name, pages, chunking or EVAL_CHUNKING)
        documents[path.name] = [chunk.text for chunk in chunks]
    return documents