from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".html", ".docx", ".pptx", ".png", ".jpg", ".jpeg"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "RAG MVP"
    api_v1_prefix: str = "/api/v1"

    database_url: str = "postgresql+psycopg2://rag:rag@postgres:5432/rag"

    jwt_secret_key: str = "change-me-to-a-long-random-string"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 10080

    qdrant_url: str = "http://qdrant:6333"
    qdrant_collection: str = "documents"
    qdrant_vector_size: int = 384

    embedding_provider: str = "local"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_api_key: str = ""
    embedding_base_url: str = ""
    embedding_batch_size: int = 32

    llm_model: str = "Qwen/Qwen2-1.5B-Instruct"
    llm_device: str = "auto"
    llm_max_new_tokens: int = 512
    llm_temperature: float = 0.1
    llm_torch_dtype: str = "auto"
    llm_cache_dir: str = "/app/model_cache"
    llm_preload: bool = True

    chunk_size: int = 1000
    chunk_overlap: int = 150
    top_k: int = 5

    document_parser: str = "opendataloader"

    upload_dir: str = "/app/uploads"
    max_upload_size_mb: int = 50

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
