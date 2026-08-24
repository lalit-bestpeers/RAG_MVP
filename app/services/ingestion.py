import logging
import uuid
from pathlib import Path
from uuid import UUID

from app.core.config import settings
from app.db.models import Document
from app.db.session import SessionLocal
from app.services.chunking import chunk_pages
from app.services.document_loader import extract_pages
from app.services.embeddings import embedding_service
from app.services.qdrant import qdrant_service

logger = logging.getLogger("rag.ingestion")


def process_document(document_id: UUID) -> None:
    db = SessionLocal()
    try:
        document = db.get(Document, document_id)
        if document is None:
            logger.warning("Document %s no longer exists; skipping ingestion", document_id)
            return

        document.status = "processing"
        document.error_message = None
        db.commit()

        pages = extract_pages(Path(document.stored_path))
        if not any(page.text.strip() for page in pages):
            raise ValueError("No text could be extracted from the document")

        chunks = chunk_pages(pages, settings.chunk_size, settings.chunk_overlap)
        if not chunks:
            raise ValueError("Chunking produced no chunks")

        vectors = embedding_service.embed([chunk.text for chunk in chunks])
        points = []
        for chunk, vector in zip(chunks, vectors):
            chunk_id = uuid.uuid4()
            points.append(
                {
                    "chunk_id": chunk_id,
                    "user_id": document.user_id,
                    "session_id": document.session_id,
                    "document_id": document.id,
                    "filename": document.filename,
                    "page_number": chunk.page_number,
                    "text": chunk.text,
                    "vector": vector,
                }
            )

        qdrant_service.upsert_chunks(points)

        document.status = "processed"
        document.page_count = len(pages)
        document.error_message = None
        db.commit()
        logger.info(
            "Document %s processed: %d chunks into Qdrant (session %s)",
            document_id,
            len(chunks),
            document.session_id,
        )
    except Exception as exc:
        logger.exception("Ingestion failed for document %s", document_id)
        db.rollback()
        document = db.get(Document, document_id)
        if document is not None:
            document.status = "failed"
            document.error_message = str(exc)[:1000]
            db.commit()
    finally:
        db.close()
