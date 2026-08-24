import shutil
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_owned_session
from app.core.config import settings
from app.db.models import ChatSession, User
from app.db.session import get_db
from app.schemas.session import SessionCreate, SessionOut
from app.services.qdrant import qdrant_service

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
def create_session(
    payload: SessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatSession:
    chat_session = ChatSession(
        user_id=current_user.id,
        title=payload.title or "New Session",
    )
    db.add(chat_session)
    db.commit()
    db.refresh(chat_session)
    return chat_session


@router.get("", response_model=list[SessionOut])
def list_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ChatSession]:
    return (
        db.query(ChatSession)
        .filter(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.created_at.desc())
        .all()
    )


@router.get("/{session_id}", response_model=SessionOut)
def get_session(
    session_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatSession:
    return get_owned_session(session_id, db, current_user)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    chat_session = get_owned_session(session_id, db, current_user)
    qdrant_service.delete_by_session(session_id)
    session_dir = Path(settings.upload_dir) / str(session_id)
    if session_dir.exists():
        shutil.rmtree(session_dir, ignore_errors=True)
    db.delete(chat_session)
    db.commit()
