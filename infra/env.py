import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


def get_env(key: str, default: Optional[str] = None) -> Optional[str]:
    """Get environment variable with optional default."""
    return os.getenv(key, default)


def require_env(key: str) -> str:
    """Get required environment variable or raise RuntimeError."""
    value = os.getenv(key)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return value


