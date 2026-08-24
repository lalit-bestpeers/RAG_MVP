import threading

from app.core.config import settings


class EmbeddingService:
    def __init__(self) -> None:
        self.provider = settings.embedding_provider.lower()
        self._model = None
        self._client = None
        self._lock = threading.Lock()

    def _load_local_model(self) -> None:
        if self._model is not None:
            return
        with self._lock:
            if self._model is None:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(settings.embedding_model)

    def _get_openai_client(self):
        if self._client is None:
            if not settings.embedding_api_key:
                raise RuntimeError("EMBEDDING_API_KEY is not configured")
            from openai import OpenAI

            self._client = OpenAI(
                api_key=settings.embedding_api_key,
                base_url=settings.embedding_base_url or None,
            )
        return self._client

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        if self.provider == "openai":
            client = self._get_openai_client()
            response = client.embeddings.create(model=settings.embedding_model, input=texts)
            response.data.sort(key=lambda item: item.index)
            return [item.embedding for item in response.data]

        self._load_local_model()
        with self._lock:
            vectors = self._model.encode(
                texts,
                batch_size=settings.embedding_batch_size,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        return [vector.tolist() for vector in vectors]


embedding_service = EmbeddingService()
