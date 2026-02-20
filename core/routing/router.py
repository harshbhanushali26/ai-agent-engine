"""
Pattern Router

Attempts deterministic pattern matching before falling back to LLM.
This layer prevents unnecessary LLM calls by handling simple queries
via rule-based matchers.
"""

from typing import Callable, Optional

from core.routing.math_pattern import match as match_math
from core.routing.datetime_pattern import match as match_datetime
from core.routing.text_pattern import match as match_text


# Ordered by priority (most common / fastest first)
PATTERN_MATCHERS: list[Callable[[str], Optional[str]]] = [
    match_math,
    match_datetime,
    match_text,
]


def match_pattern(query: str) -> Optional[str]:
    """
    Try all pattern matchers in priority order.

    Args:
        query: User input string

    Returns:
        Result string if matched, otherwise None
    """
    for matcher in PATTERN_MATCHERS:
        result = matcher(query)
        if result is not None:
            return result

    return None
