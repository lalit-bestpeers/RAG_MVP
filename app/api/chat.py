from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_owned_session
from app.db.models import ChatMessage, User
from app.db.session import get_db
from app.schemas.chat import ChatRequest, ChatResponse, MessageOut, Source
from app.services.rag import answer_question

router = APIRouter(tags=["chat"])


@router.post("/sessions/{session_id}/chat", response_model=ChatResponse)
def create_chat(
    session_id: UUID,
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatResponse:
    chat_session = get_owned_session(session_id, db, current_user)

    user_message = ChatMessage(
        session_id=chat_session.id,
        user_id=current_user.id,
        role="user",
        content=payload.question,
    )
    db.add(user_message)
    db.commit()

    answer, sources = answer_question(chat_session, payload.question)

    assistant_message = ChatMessage(
        session_id=chat_session.id,
        user_id=current_user.id,
        role="assistant",
        content=answer,
        sources=sources,
    )
    db.add(assistant_message)
    db.commit()

    return ChatResponse(
        answer=answer,
        sources=[Source(**source) for source in sources],
    )


@router.get("/sessions/{session_id}/messages", response_model=list[MessageOut])
def list_messages(
    session_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ChatMessage]:
    chat_session = get_owned_session(session_id, db, current_user)
    return (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == chat_session.id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
