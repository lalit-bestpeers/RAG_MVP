import logging

from app.core.config import settings

logger = logging.getLogger("rag.grok")


class GrokService:
    def __init__(self) -> None:
        self._client = None

    def _get_client(self):
        if self._client is None:
            if not settings.grok_api_key:
                raise RuntimeError(
                    "GROK_API_KEY is not configured. Set it in the .env file and restart."
                )
            from openai import OpenAI

            self._client = OpenAI(
                api_key=settings.grok_api_key,
                base_url=settings.grok_base_url,
            )
        return self._client

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        client = self._get_client()
        response = client.chat.completions.create(
            model=settings.grok_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=settings.grok_temperature,
            max_tokens=settings.grok_max_tokens,
        )
        return response.choices[0].message.content or ""


grok_service = GrokService()
