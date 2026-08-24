import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


class Source(BaseModel):
    document_id: uuid.UUID
    filename: str
    page_number: int
    chunk_id: uuid.UUID
    similarity_score: float


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source]


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    content: str
    sources: list[dict] | None = None
    created_at: datetime
