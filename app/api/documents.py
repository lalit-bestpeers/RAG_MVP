from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_owned_document, get_owned_session
from app.core.config import ALLOWED_EXTENSIONS, settings
from app.db.models import ChatSession, Document, User
from app.db.session import get_db
from app.schemas.document import DocumentOut
from app.services.ingestion import process_document
from app.services.qdrant import qdrant_service

router = APIRouter(tags=["documents"])


def _safe_filename(name: str | None) -> str:
    normalized = (name or "file").replace("\\", "/")
    return Path(normalized).name


async def _save_upload(upload: UploadFile, dest: Path) -> None:
    size = 0
    with open(dest, "wb") as fh:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > settings.max_upload_bytes:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File too large (max {settings.max_upload_size_mb} MB)",
                )
            fh.write(chunk)


@router.post(
    "/sessions/{session_id}/documents",
    response_model=DocumentOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    session_id: UUID,
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Document:
    chat_session: ChatSession = get_owned_session(session_id, db, current_user)

    filename = _safe_filename(file.filename)
    ext = Path(filename).suffix.lower()
    if not filename or ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
        )

    document = Document(
        session_id=chat_session.id,
        user_id=current_user.id,
        filename=filename,
        stored_path="",
        status="pending",
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    dest_dir = Path(settings.upload_dir) / str(session_id) / str(document.id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename

    try:
        await _save_upload(file, dest)
    except HTTPException:
        dest.unlink(missing_ok=True)
        db.delete(document)
        db.commit()
        raise

    document.stored_path = str(dest)
    db.commit()

    background_tasks.add_task(process_document, document.id)
    return document


@router.get("/sessions/{session_id}/documents", response_model=list[DocumentOut])
def list_documents(
    session_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Document]:
    chat_session = get_owned_session(session_id, db, current_user)
    return (
        db.query(Document)
        .filter(Document.session_id == chat_session.id)
        .order_by(Document.created_at.desc())
        .all()
    )


@router.get("/documents/{document_id}", response_model=DocumentOut)
def get_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Document:
    return get_owned_document(document_id, db, current_user)


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    document = get_owned_document(document_id, db, current_user)
    qdrant_service.delete_by_document(document_id)
    Path(document.stored_path).unlink(missing_ok=True)
    db.delete(document)
    db.commit()
