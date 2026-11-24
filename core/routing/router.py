"""
Pattern Router & Query Cache Intelligence

Attempts deterministic pattern matching before falling back to LLM.
This layer prevents unnecessary LLM calls by handling simple queries
via rule-based matchers and governs caching rules.
"""

from typing import Optional, Tuple

from core.routing.datetime_pattern import match as match_datetime
from core.routing.math_pattern import match as match_math
from core.routing.text_pattern import match as match_text


# ═══════════════════════════════════════════════════════════════════════════════
# DYNAMIC QUERY INDICATORS (NON-CACHEABLE)
# ═══════════════════════════════════════════════════════════════════════════════

DATETIME_INDICATORS = [
    'today', 'tomorrow', 'yesterday',
    'what day is', 'what time is', 'current date', 'current time',
    'what date is', 'days from today', 'days before today',
    'next monday', 'next week', 'last week'
]

WEB_SEARCH_INDICATORS = [
    'who is', 'what is', 'where is', 'when was', 'why is', 'how does',
    'search for', 'find', 'look up',
    'latest', 'recent', 'current', 'news about',
    'tell me about', 'information about',
    'capital of', 'president', 'prime minister'
]

FINANCIAL_INDICATORS = ['stock', 'price', 'ticker', 'crypto', 'bitcoin']

RAG_PERSONAL_PHRASES = [
    'my energy', 'my routine', 'my habit', 'my schedule',
    'my best', 'my focus', 'my deep work',
    'my walk', 'my temple', 'my tea', 'my tmkoc',
    'when should i', 'should i schedule',
    'when is my', 'what is my',
    'plan my', 'plan today', 'plan tomorrow',
]

# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC ROUTING API
# ═══════════════════════════════════════════════════════════════════════════════





def route_pattern(query: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Evaluate query against deterministic pattern matchers in priority order:
    1. Datetime (highest priority - captures dates before math grabs numbers)
    2. Math (evaluates safe AST arithmetic)
    3. Text (string transformations and counts)

    Args:
        query: User input string

    Returns:
        Tuple of (response_text, pattern_type) or (None, None)
    """
    # 1. Datetime check
    dt_res = match_datetime(query)
    if dt_res:
        return (dt_res, "datetime")

    # 2. Math check
    math_res = match_math(query)
    if math_res:
        return (math_res, "math")

    # 3. Text check
    text_res = match_text(query)
    if text_res:
        return (text_res, "text")

    return (None, None)


def is_cacheable_pattern(pattern_type: Optional[str]) -> bool:
    """Determine if a pattern match output is safe to cache."""
    return pattern_type in ("math", "text")


def is_cacheable_query(query: str) -> bool:
    """
    Determine if an agent response or raw query is safe to cache.
    Filters out queries requiring dynamic or context-dependent state.
    """
    q = query.lower()

    # 1. Weather
    if 'weather' in q or 'temperature' in q:
        return False

    # 2. Datetime
    if any(ind in q for ind in DATETIME_INDICATORS):
        return False

    # 3. Web Search
    if any(ind in q for ind in WEB_SEARCH_INDICATORS):
        return False

    # 4. Financial/Stock
    if any(word in q for word in FINANCIAL_INDICATORS):
        return False

    # 5. Personal / RAG preferences
    if any(phrase in q for phrase in RAG_PERSONAL_PHRASES):
        return False

    return True
