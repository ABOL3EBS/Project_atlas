from dataclasses import dataclass
from pathlib import Path

import pymupdf


class UnsupportedFormatError(ValueError):
    pass


@dataclass
class ParsedPage:
    text: str
    page: int | None = None
    section: str | None = None


SUPPORTED_EXTENSIONS = {".pdf", ".md", ".txt"}


def parse_document(filename: str, content: bytes) -> list[ParsedPage]:
    extension = Path(filename).suffix.lower()
    if extension == ".pdf":
        return _parse_pdf(content)
    if extension in {".md", ".txt"}:
        return _parse_text(content, is_markdown=extension == ".md")
    raise UnsupportedFormatError(f"Unsupported format: {extension}")


def _parse_pdf(content: bytes) -> list[ParsedPage]:
    try:
        document = pymupdf.open(stream=content, filetype="pdf")
    except Exception as error:
        raise ValueError(f"Could not parse PDF: {error}") from error
    pages: list[ParsedPage] = []
    for index, page in enumerate(document, start=1):
        text = page.get_text("text")
        if text:
            pages.append(ParsedPage(text=text, page=index))
    document.close()
    return pages


def _parse_text(content: bytes, *, is_markdown: bool) -> list[ParsedPage]:
    text = content.decode("utf-8", errors="replace")
    if not is_markdown:
        return [ParsedPage(text=text)]
    return _split_markdown_sections(text)


def _split_markdown_sections(text: str) -> list[ParsedPage]:
    pages: list[ParsedPage] = []
    current = ParsedPage(text="")
    for line in text.splitlines():
        if line.startswith("#"):
            if current.text.strip():
                pages.append(current)
            current = ParsedPage(text="", section=line.strip())
        else:
            current.text += f"{line}\n"
    if current.text.strip():
        pages.append(current)
    return pages or [ParsedPage(text=text)]