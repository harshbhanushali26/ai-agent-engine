"""
Math Pattern Matcher

Detects and evaluates mathematical expressions without using LLM.
Handles: +, -, *, /, %, ** operators with parentheses and decimals.

Uses AST (Abstract Syntax Tree) for safe evaluation.
"""


import re
import ast
from typing import Optional
from tools.math.calculate import eval_node



# ═══════════════════════════════════════════════════════════════════════════
# EXPRESSION EXTRACTION
# ═══════════════════════════════════════════════════════════════════════════


def extract_math_expression(query: str) -> str | None:
    """
    Extract arithmetic expression from natural language query.
    """

    # Find all arithmetic-like fragments
    candidates = re.findall(r'[-+*/%().\d]+(?:\s*[-+*/%().\d]+)*', query)

    if not candidates:
        return None

    # Evaluate each candidate
    for candidate in candidates:
        expr = candidate.strip()

        # Must contain at least one digit
        if not re.search(r'\d', expr):
            continue

        # Must contain at least one operator
        if not re.search(r'[+\-*/%]', expr):
            continue

        # Minimum viable length
        if len(expr) < 3:
            continue

        return expr

    return None




# ═══════════════════════════════════════════════════════════════════════════
# SAFETY VALIDATION
# ═══════════════════════════════════════════════════════════════════════════

def is_safe_expression(expr: str) -> bool:
    """
    Validate expression is safe to evaluate.
    
    Args:
        expr: Mathematical expression string
        
    Returns:
        True if safe, False otherwise
    """
    if not re.match(r'^[\d\s+\-*/%().**]+$', expr):
        return False

    # Check balanced parentheses
    if expr.count('(') != expr.count(')'):
        return False

    # Reasonable length (prevent DoS)
    if len(expr) > 100:
        return False
    
    return True



# ═══════════════════════════════════════════════════════════════════════════
# RESULT FORMATTING
# ═══════════════════════════════════════════════════════════════════════════

def format_math_result(result: float) -> str:
    """
    Format calculation result for display.
    
    Args:
        result: Numeric result from calculation
        
    Returns:
        Formatted string
        
    Examples:
        8.0 → "8"
        3.333... → "3.33"
        116.5 → "116.5"
    """
    # If result is a whole number, show as integer
    if isinstance(result, float) and result.is_integer():
        return str(int(result))
    
    # Otherwise round to 2 decimal places
    return str(round(result, 2))



# ═══════════════════════════════════════════════════════════════════════════
# MAIN PATTERN MATCHER
# ═══════════════════════════════════════════════════════════════════════════

def match_math_pattern(query: str) -> str | None:
    """
    Try to match and evaluate mathematical expression.
    
    This is the main entry point for the math pattern matcher.
    Returns a result string if the query contains evaluable math,
    otherwise returns None (allowing fallback to LLM).
    
    Args:
        query: User's query string
        
    Returns:
        Formatted result string, or None if no match/evaluation failed
        
    Examples:
        "What's 5 + 3?" → "8"
        "Calculate (10+5)*2" → "30"
        "What's -10 + 2?" → "-8"
        "100 - 23.50 + 40" → "116.5"
        "Tell me about Python" → None
    """

    # Step 1: Extract expression
    expr = extract_math_expression(query)
    if not expr:
        return None
    
    # Step 2: Validate safety
    if not is_safe_expression(expr):
        return None
    
    # Step 3: Evaluate using AST
    try:
        tree = ast.parse(expr, mode="eval")
        result = eval_node(tree.body)
        
        # Step 4: Format result
        return format_math_result(result)
        
    except (SyntaxError, ValueError, ZeroDivisionError, TypeError):
        # Invalid expression or evaluation error
        # Return None to fall back to LLM
        return None
    except Exception:
        # Catch-all for any other errors
        return None



# ═══════════════════════════════════════════════════════════════════════════
# ADDITIONAL HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def should_skip_math_pattern(query: str) -> bool:
    """
    Check if query should skip math pattern matching.
    
    Queries are skipped if they're clearly about:
    - Datetime/calendar operations
    - Weather information
    - Text transformations
    - Web searches/information lookup
    
    BUT queries with math operators are never skipped,
    even if they contain these keywords.
    
    Args:
        query: User's query string
        
    Returns:
        True if should skip math pattern matching
        
    Examples:
        "What's 5 + 3?" → False (has +, don't skip)
        "What is Python?" → True (web search, skip)
        "What is 2 + 2?" → False (has +, don't skip)
        "Convert to uppercase" → True (text op, skip)
    """
    query_lower = query.lower()

    # Rule 1: If query has math operators, NEVER skip
    math_operators = ['+', '-', '*', '/', '%', '**', '(', ')']
    if any(op in query for op in math_operators):
        return False

    # Rule 2: Skip if matches other pattern types
    
    # Datetime/calendar
    datetime_keywords = [
        'date', 'day', 'week', 'month', 'year',
        'today', 'tomorrow', 'yesterday',
        'time', 'clock', 'when', 'calendar'
    ]
    if any(word in query_lower for word in datetime_keywords):
        return True

    # Weather
    if 'weather' in query_lower or 'temperature' in query_lower:
        return True

    # Text operations
    text_keywords = [
        'uppercase', 'lowercase', 'capitalize',
        'reverse', 'convert', 'transform', 'string'
    ]
    if any(word in query_lower for word in text_keywords):
        return True

    # Web search/information lookup
    search_phrases = [
        'who is', 'what is', 'where is', 'when was', 'why is',
        'capital of', 'president', 'prime minister',
        'tell me about', 'search for', 'find', 'look up',
        'information about', 'explain', 'describe'
    ]
    if any(phrase in query_lower for phrase in search_phrases):
        return True

    # Default: don't skip (let pattern matcher try)
    return False

# ═══════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════

def match(query: str) -> Optional[str]:
    """
    Public API for math pattern matching.
    
    Args:
        query: User's query string
        
    Returns:
        Result string or None
    """
    # Check if query should be skipped
    if should_skip_math_pattern(query):
        return None

    # Try to match and evaluate
    return match_math_pattern(query)