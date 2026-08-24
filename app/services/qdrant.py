import logging
from uuid import UUID

from qdrant_client import QdrantClient, models

from app.core.config import settings

logger = logging.getLogger("rag.qdrant")


class QdrantService:
    def __init__(self) -> None:
        self.client = QdrantClient(url=settings.qdrant_url)

    def ensure_collection(self) -> None:
        if not self.client.collection_exists(settings.qdrant_collection):
            self.client.create_collection(
                collection_name=settings.qdrant_collection,
                vectors_config=models.VectorParams(
                    size=settings.qdrant_vector_size,
                    distance=models.Distance.COSINE,
                ),
            )

    def _filter(self, **fields) -> models.Filter:
        must = [
            models.FieldCondition(key=key, match=models.MatchValue(value=str(value)))
            for key, value in fields.items()
        ]
        return models.Filter(must=must)

    def upsert_chunks(self, chunks: list[dict]) -> None:
        points = [
            models.PointStruct(
                id=str(chunk["chunk_id"]),
                vector=chunk["vector"],
                payload={
                    "user_id": str(chunk["user_id"]),
                    "session_id": str(chunk["session_id"]),
                    "document_id": str(chunk["document_id"]),
                    "chunk_id": str(chunk["chunk_id"]),
                    "filename": chunk["filename"],
                    "page_number": int(chunk["page_number"]),
                    "text": chunk["text"],
                },
            )
            for chunk in chunks
        ]
        self.client.upsert(collection_name=settings.qdrant_collection, points=points)

    def search(self, vector: list[float], user_id: UUID, session_id: UUID, top_k: int) -> list[dict]:
        response = self.client.query_points(
            collection_name=settings.qdrant_collection,
            query=vector,
            query_filter=self._filter(user_id=user_id, session_id=session_id),
            limit=top_k,
            with_payload=True,
        )
        results = []
        for hit in response.points:
            payload = hit.payload or {}
            results.append(
                {
                    "chunk_id": payload.get("chunk_id"),
                    "document_id": payload.get("document_id"),
                    "filename": payload.get("filename"),
                    "page_number": int(payload.get("page_number") or 0),
                    "text": payload.get("text") or "",
                    "similarity_score": float(hit.score),
                }
            )
        return results

    def delete_by_document(self, document_id: UUID) -> None:
        try:
            self.client.delete(
                collection_name=settings.qdrant_collection,
                points_selector=models.FilterSelector(filter=self._filter(document_id=document_id)),
            )
        except Exception as exc:
            logger.warning("Could not delete Qdrant points for document %s: %s", document_id, exc)

    def delete_by_session(self, session_id: UUID) -> None:
        try:
            self.client.delete(
                collection_name=settings.qdrant_collection,
                points_selector=models.FilterSelector(filter=self._filter(session_id=session_id)),
            )
        except Exception as exc:
            logger.warning("Could not delete Qdrant points for session %s: %s", session_id, exc)


qdrant_service = QdrantService()
