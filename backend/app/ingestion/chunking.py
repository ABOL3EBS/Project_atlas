from dataclasses import dataclass

from .cleaning import split_paragraphs
from .parsers import ParsedPage


@dataclass
class Chunk:
    text: str
    document_id: str
    document_name: str
    page: int | None
    section: str | None
    chunk_id: str


@dataclass
class ChunkingConfig:
    chunk_size: int = 500
    chunk_overlap: int = 50


def estimate_tokens(text: str) -> int:
    return len(text.split())


def chunk_document(
    document_id: str,
    document_name: str,
    pages: list[ParsedPage],
    config: ChunkingConfig,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    index = 0

    for page in pages:
        for paragraph in split_paragraphs(page.text):
            if estimate_tokens(paragraph) > config.chunk_size:
                for piece in _split_oversized(
                    paragraph, page, config
                ):
                    chunks.append(_make_chunk(piece, page, document_id, document_name, index))
                    index += 1
                continue

            if chunks and _exceeds(chunks[-1].text, paragraph, config):
                remainder = _overlap_tail(chunks[-1].text, config.chunk_overlap)
                chunks.append(
                    _make_chunk(
                        _join_parts(remainder, paragraph),
                        page,
                        document_id,
                        document_name,
                        index,
                    )
                )
                index += 1
            elif chunks:
                chunks[-1].text = _join_parts(chunks[-1].text, paragraph)
            else:
                chunks.append(_make_chunk(paragraph, page, document_id, document_name, index))
                index += 1

    return [chunk for chunk in chunks if chunk.text.strip()]


def _make_chunk(
    text: str,
    page: ParsedPage,
    document_id: str,
    document_name: str,
    index: int,
) -> Chunk:
    return Chunk(
        text=text.strip(),
        document_id=document_id,
        document_name=document_name,
        page=page.page,
        section=page.section,
        chunk_id=f"{document_id}-{index}",
    )


def _exceeds(current: str, addition: str, config: ChunkingConfig) -> bool:
    return estimate_tokens(current) + estimate_tokens(addition) > config.chunk_size


def _join_parts(left: str, right: str) -> str:
    return f"{left}\n\n{right}".strip()


def _overlap_tail(text: str, overlap: int) -> str:
    words = text.split()
    return " ".join(words[max(0, len(words) - overlap) :])


def _split_oversized(
    paragraph: str, page: ParsedPage, config: ChunkingConfig
) -> list[str]:
    words = paragraph.split()
    pieces: list[str] = []
    for start in range(0, len(words), config.chunk_size):
        pieces.append(" ".join(words[start : start + config.chunk_size]))
    return pieces