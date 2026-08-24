from app.core.config import settings
from app.db.models import ChatSession
from app.services.grok import grok_service
from app.services.retriever import retrieve

NOT_FOUND = "I could not find the answer in the provided documents."

SYSTEM_PROMPT = (
    "You are a RAG assistant. Answer the user's question using ONLY the document "
    "excerpts provided below. Do not use outside knowledge. Cite the excerpt used "
    "for each claim with its source number, e.g. [1] or [2]. "
    f"If the excerpts do not contain the answer, respond with exactly: {NOT_FOUND}"
)


def answer_question(session: ChatSession, question: str) -> tuple[str, list[dict]]:
    results = retrieve(session, question, settings.top_k)
    if not results:
        return NOT_FOUND, []

    context = "\n\n".join(
        f"[{i}] ({result['filename']}, page {result['page_number']}): "
        f"{result['text'].strip()}"
        for i, result in enumerate(results, start=1)
    )
    prompt = f"Document excerpts:\n\n{context}\n\nQuestion: {question}\n\nAnswer:"
    answer = grok_service.generate(SYSTEM_PROMPT, prompt).strip()

    if not answer:
        answer = NOT_FOUND

    sources = [
        {
            "document_id": result["document_id"],
            "filename": result["filename"],
            "page_number": result["page_number"],
            "chunk_id": result["chunk_id"],
            "similarity_score": result["similarity_score"],
        }
        for result in results
    ]
    return answer, sources
