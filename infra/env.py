import os
from dotenv import load_dotenv

load_dotenv()


def require_env(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return value


GEMINI_API_KEY = require_env("GEMINI_API_KEY")
