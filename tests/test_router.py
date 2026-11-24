"""
Unit tests for unified pattern routing and cache filtering.
"""

from core.routing.router import (
    route_pattern,
    is_cacheable_pattern,
    is_cacheable_query
)


def test_router_priority_datetime_over_math():
    """Verify relative datetime with numbers is handled by datetime matcher, not math."""
    # "5 days from today" has a number "5" but is a datetime query
    response, pattern_type = route_pattern("What date is 5 days from today?")
    assert pattern_type == "datetime"
    assert response is not None

    # Pure math query should match math
    response, pattern_type = route_pattern("What is 15 * 4?")
    assert pattern_type == "math"
    assert response == "60"

    # Pure text query should match text
    response, pattern_type = route_pattern("Convert 'agent' to uppercase")
    assert pattern_type == "text"
    assert response == "AGENT"


def test_is_cacheable_pattern():
    """Verify only deterministic pattern match outputs are cacheable."""
    assert is_cacheable_pattern("math") is True
    assert is_cacheable_pattern("text") is True
    assert is_cacheable_pattern("datetime") is False  # Datetime changes dynamically
    assert is_cacheable_pattern(None) is False


def test_is_cacheable_query_dynamic_filtering():
    """Verify dynamic categories are skipped from caching."""
    # Weather queries -> Dynamic
    assert is_cacheable_query("What's the weather in Tokyo?") is False

    # Datetime queries -> Dynamic
    assert is_cacheable_query("What time is it right now?") is False
    assert is_cacheable_query("What date is tomorrow?") is False

    # Financial queries -> Dynamic
    assert is_cacheable_query("Current Bitcoin price") is False

    # Personal RAG queries -> Dynamic
    assert is_cacheable_query("What is my energy routine?") is False
    assert is_cacheable_query("Plan my focus hours today") is False

    # General deterministic queries -> Cacheable
    assert is_cacheable_query("Convert 100 meters to feet") is True
    assert is_cacheable_query("Summarize this static paragraph") is True