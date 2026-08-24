from app.core.config import settings
from app.db.models import ChatSession
from app.services.embeddings import embedding_service
from app.services.qdrant import qdrant_service


def retrieve(session: ChatSession, question: str, top_k: int | None = None) -> list[dict]:
    vector = embedding_service.embed([question])[0]
    return qdrant_service.search(vector, session.user_id, session.id, top_k or settings.top_k)
