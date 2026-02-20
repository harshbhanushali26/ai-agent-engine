"""
Routing Layer

Exposes deterministic pattern routing to avoid unnecessary LLM calls.
"""

from .router import match_pattern

__all__ = ["match_pattern"]
