# RAG MVP

Session-based Retrieval-Augmented Generation MVP that runs locally with Docker Compose.

**Stack:** FastAPI · PostgreSQL · Qdrant · OpenDataLoader (PDF/OCR) · sentence-transformers (free local embeddings) · HuggingFace local LLM (auto-downloaded, no API key)

## Architecture

```
User → Register/Login (JWT) → Create Session → Upload Documents
    → OpenDataLoader + OCR → Extract → Chunk → Embed → Qdrant
    → Ask question → session-filtered vector search → local LLM → Answer + Sources
```

Every Qdrant point is tagged with `user_id`, `session_id`, `document_id`, `chunk_id`,
`filename`, `page_number`, `text`. Every search filters by **both** `user_id` and
`session_id`, so users can never retrieve another user's data or another session's documents.

## Quick start

1. Copy the environment template (no API key needed — the LLM runs locally):

   ```powershell
   Copy-Item .env.example .env
   # edit .env → replace JWT_SECRET_KEY with a long random string
   #            → optionally change LLM_MODEL (see Configuration below)
   ```

2. Start everything:

   ```powershell
   docker compose up --build -d
   ```

   The first start downloads the base images, the local embedding model, and the LLM,
   so it takes a few minutes. The LLM is preloaded in a background thread at startup,
   so your first chat request is fast.

3. Verify:

   ```powershell
   Invoke-RestMethod http://localhost:8000/health   # {"status":"ok"}
   Invoke-RestMethod http://localhost:8000/ready    # {"status":"ready"}
   ```

4. Open the interactive docs at http://localhost:8000/docs

## Smoke test (end to end)

```powershell
$api = "http://localhost:8000/api/v1"

# register
$body = '{"email":"a@example.com","username":"alice","password":"password123"}'
$token = (Invoke-RestMethod -Method Post -Uri "$api/auth/register" -ContentType "application/json" -Body $body).access_token
$h = @{ Authorization = "Bearer $token" }

# create a session
$session = Invoke-RestMethod -Method Post -Uri "$api/sessions" -ContentType "application/json" -Headers $h -Body '{"title":"Test"}'
$sid = $session.id

# upload a PDF (PowerShell 7+; on Windows PowerShell 5.1 use curl.exe, see below)
Invoke-RestMethod -Method Post -Uri "$api/sessions/$sid/documents" -Headers $h -Form @{ file = Get-Item .\sample.pdf }

# Windows PowerShell 5.1 alternative:
# curl.exe -X POST -H "Authorization: Bearer $token" -F "file=@sample.pdf" "$api/sessions/$sid/documents"

# ask a question (first call waits if the model is still preloading)
$q = Invoke-RestMethod -Method Post -Uri "$api/sessions/$sid/chat" -ContentType "application/json" -Headers $h -Body '{"question":"What is the document about?"}'
$q.answer
$q.sources
```

## Configuration (`.env`)

| Variable | Description | Default |
| --- | --- | --- |
| `LLM_MODEL` | HuggingFace model id, auto-downloaded to `LLM_CACHE_DIR` on first run. Change this to switch models | `Qwen/Qwen2-1.5B-Instruct` |
| `LLM_DEVICE` | `auto` (CUDA if available, else CPU), `cpu`, or `cuda` | `auto` |
| `LLM_MAX_NEW_TOKENS` | Max tokens to generate per answer | 512 |
| `LLM_TEMPERATURE` | Sampling temperature (0 = greedy/deterministic) | 0.1 |
| `LLM_TORCH_DTYPE` | `auto`, `float16`, `float32`, `bfloat16` | `auto` |
| `LLM_CACHE_DIR` | Where models are downloaded/cached (Docker volume) | `/app/model_cache` |
| `LLM_PRELOAD` | Preload model in a background thread at startup for fast first chat | `true` |
| `JWT_SECRET_KEY` | Secret for signing JWTs. Change it! | placeholder |
| `EMBEDDING_PROVIDER` | `local` (sentence-transformers) or `openai` (OpenAI-compatible API) | `local` |
| `EMBEDDING_MODEL` / `EMBEDDING_DIMENSION` | Embedding model + vector size (must match `QDRANT_VECTOR_SIZE`) | MiniLM-L6-v2 / 384 |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | Document chunking | 1000 / 150 |
| `TOP_K` | Number of retrieved chunks per question | 5 |
| `DOCUMENT_PARSER` | `opendataloader` (default, needs Java, handled by image) or `pymupdf` | `opendataloader` |
| `MAX_UPLOAD_SIZE_MB` | Upload size limit | 50 |

### Switching local LLM models

The LLM runs fully locally, so no API key is required. To use a different model, set
`LLM_MODEL` to any causal language model id on the HuggingFace Hub and restart — it is
downloaded automatically on the next startup and cached in the `model_cache` volume.

Good options depending on your hardware (RAG needs a reasonably capable model):
- `Qwen/Qwen2-1.5B-Instruct` — ~4 GB RAM, good quality/speed balance (default)
- `microsoft/Phi-3.5-mini-instruct` — ~8 GB RAM, best quality on modest hardware
- `TinyLlama/TinyLlama-1.1B-Chat-v1.0` — ~2 GB RAM, faster but noticeably weaker
- `Qwen/Qwen2-7B-Instruct` — ~16 GB RAM; add an HF token for gated/LLaMA-style models if needed

> **CPU note:** The Dockerfile installs CPU-only PyTorch, so models run on CPU unless you
> rebuild the image for CUDA / pass a GPU into Docker. Pick a model that fits your memory.

> **Gated models:** Some models (e.g. Llama, Mistral) require a HuggingFace token. Set
> the `HF_TOKEN` environment variable in `.env` for those.

If you change the embedding model, set `EMBEDDING_DIMENSION` **and** `QDRANT_VECTOR_SIZE` to the same value
before the Qdrant collection is first created.

## Layout

```
app/
 ├── api/        thin route handlers (auth, sessions, documents, chat, health, deps)
 ├── core/       settings + security (JWT, bcrypt)
 ├── db/         SQLAlchemy session + models (users, sessions, documents, chat_messages)
 ├── schemas/    Pydantic request/response models
 ├── services/   business logic (ingestion, document_loader, chunking, embeddings,
 │               qdrant, retriever, local_llm, rag)
 └── main.py     FastAPI app
alembic/         migrations (auto-run on container start)
```

## Security

- JWT bearer auth; bcrypt password hashing
- Session/document ownership validated against the authenticated user on every request (404 on foreign resources)
- Qdrant search always filtered by `user_id` + `session_id`
- File type whitelist + upload size limit; sanitized filenames
- No API keys for inference (LLM + embeddings both run locally); secrets live only in `.env`
