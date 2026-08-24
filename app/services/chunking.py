import re
from dataclasses import dataclass

from app.core.config import settings
from app.services.document_loader import ExtractedPage


@dataclass
class Chunk:
    text: str
    page_number: int


def clean_text(text: str) -> str:
    text = text.replace("\x00", " ").replace("\ufeff", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_pages(
    pages: list[ExtractedPage],
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[Chunk]:
    chunk_size = chunk_size or settings.chunk_size
    chunk_overlap = chunk_overlap or settings.chunk_overlap
    chunk_overlap = max(0, min(chunk_overlap, chunk_size // 2))

    chunks: list[Chunk] = []
    for page in pages:
        text = clean_text(page.text)
        if not text:
            continue
        for piece in _chunk_text(text, chunk_size, chunk_overlap):
            chunks.append(Chunk(text=piece, page_number=page.page_number))
    return chunks


def _chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    words = text.split()
    if not words:
        return []

    step = max(1, chunk_size - chunk_overlap)
    pieces: list[str] = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        pieces.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start += step
    return pieces
