# RAG MVP

Session-based Retrieval-Augmented Generation MVP that runs locally with Docker Compose.

**Stack:** FastAPI · PostgreSQL · Qdrant · OpenDataLoader (PDF/OCR) · sentence-transformers (free local embeddings) · Grok API (LLM)

## Architecture

```
User → Register/Login (JWT) → Create Session → Upload Documents
    → OpenDataLoader + OCR → Extract → Chunk → Embed → Qdrant
    → Ask question → session-filtered vector search → Grok → Answer + Sources
```

Every Qdrant point is tagged with `user_id`, `session_id`, `document_id`, `chunk_id`,
`filename`, `page_number`, `text`. Every search filters by **both** `user_id` and
`session_id`, so users can never retrieve another user's data or another session's documents.

## Quick start

1. Copy the environment template and add your Grok API key:

   ```powershell
   Copy-Item .env.example .env
   # edit .env → set GROK_API_KEY (get one at https://console.x.ai/)
   #            → replace JWT_SECRET_KEY with a long random string
   ```

2. Start everything:

   ```powershell
   docker compose up --build -d
   ```

   The first start downloads the base images and the local embedding model, so it takes a few minutes.

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

# ask a question (waits for the LLM)
$q = Invoke-RestMethod -Method Post -Uri "$api/sessions/$sid/chat" -ContentType "application/json" -Headers $h -Body '{"question":"What is the document about?"}'
$q.answer
$q.sources
```

## Configuration (`.env`)

| Variable | Description | Default |
| --- | --- | --- |
| `GROK_API_KEY` | **Required** for chat. xAI API key. | — |
| `JWT_SECRET_KEY` | Secret for signing JWTs. Change it! | placeholder |
| `EMBEDDING_PROVIDER` | `local` (sentence-transformers) or `openai` (OpenAI-compatible API) | `local` |
| `EMBEDDING_MODEL` / `EMBEDDING_DIMENSION` | Embedding model + vector size (must match `QDRANT_VECTOR_SIZE`) | MiniLM-L6-v2 / 384 |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | Document chunking | 1000 / 150 |
| `TOP_K` | Number of retrieved chunks per question | 5 |
| `GROK_MODEL` | Grok model id | `grok-4.3` |
| `DOCUMENT_PARSER` | `opendataloader` (default, needs Java, handled by image) or `pymupdf` | `opendataloader` |
| `MAX_UPLOAD_SIZE_MB` | Upload size limit | 50 |

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
 │               qdrant, retriever, grok, rag)
 └── main.py     FastAPI app
alembic/         migrations (auto-run on container start)
```

## Security

- JWT bearer auth; bcrypt password hashing
- Session/document ownership validated against the authenticated user on every request (404 on foreign resources)
- Qdrant search always filtered by `user_id` + `session_id`
- File type whitelist + upload size limit; sanitized filenames
- API keys live only in `.env` (never hard-coded, `.env` is docker-ignored)
