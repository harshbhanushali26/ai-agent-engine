from typing import Optional
from openai import OpenAI
from app.config import BASE_URL
from infra.env import require_env


_client_instance: Optional[OpenAI] = None


def get_client() -> OpenAI:
    """Lazy-load the LLM client on first usage."""
    global _client_instance
    if _client_instance is None:
        api_key = require_env("GEMINI_API_KEY")
        _client_instance = OpenAI(api_key=api_key, base_url=BASE_URL, max_retries=0)
    return _client_instance


class _LazyClientProxy:
    @property
    def chat(self):
        return get_client().chat

client = _LazyClientProxy()