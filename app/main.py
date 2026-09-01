import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.api import auth, chat, documents, health, sessions
from app.core.config import settings
from app.db import models  #  (registers models for Alembic metadata)
from app.services.local_llm import llm_service
from app.services.qdrant import qdrant_service

logger = logging.getLogger("rag")


@asynccontextmanager
async def lifespan(_: FastAPI):
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    qdrant_service.ensure_collection()
    logger.info("Using local LLM model: %s", settings.llm_model)
    if settings.llm_preload:
        llm_service.load(wait=False)
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

app.include_router(health.router)
app.include_router(auth.router, prefix=settings.api_v1_prefix)
app.include_router(sessions.router, prefix=settings.api_v1_prefix)
app.include_router(documents.router, prefix=settings.api_v1_prefix)
app.include_router(chat.router, prefix=settings.api_v1_prefix)
