"""
Text Pattern Matcher

Detects and executes text transformation operations without using LLM.
Handles: uppercase, lowercase, titlecase, word count, character count, sentence count.
"""

import re
from typing import Optional
from tools.text.text_transform import run_text
from tools.schemas import TextTransformInput


# ═══════════════════════════════════════════════════════════════════════════
# OPERATION MAPPING
# ═══════════════════════════════════════════════════════════════════════════

OPERATION_MAP = {
    # Case transformations
    "uppercase": "uppercase",
    "upper case": "uppercase",
    "to uppercase": "uppercase",
    "make uppercase": "uppercase",
    
    "lowercase": "lowercase",
    "lower case": "lowercase",
    "to lowercase": "lowercase",
    "make lowercase": "lowercase",
    
    "titlecase": "titlecase",
    "title case": "titlecase",
    "to titlecase": "titlecase",
    "capitalize": "titlecase",
    
    # Counting operations
    "word count": "word_count",
    "count words": "word_count",
    "how many words": "word_count",
    "number of words": "word_count",
    
    "character count": "char_count",
    "char count": "char_count",
    "count characters": "char_count",
    "count chars": "char_count",
    "how many characters": "char_count",
    "how many chars": "char_count",
    
    "sentence count": "sentence_count",
    "count sentences": "sentence_count",
    "how many sentences": "sentence_count",
}


# ═══════════════════════════════════════════════════════════════════════════
# OPERATION DETECTION
# ═══════════════════════════════════════════════════════════════════════════

def detect_operation(query: str) -> Optional[str]:
    """
    Detect text operation from query.
    
    Uses exact phrase matching with word boundaries to avoid false positives.
    
    Args:
        query: User's query string
        
    Returns:
        Operation type or None
    """
    query_lower = query.lower()
    
    # Sort by length (longest first) to match most specific phrases first
    sorted_phrases = sorted(OPERATION_MAP.keys(), key=len, reverse=True)
    
    for phrase in sorted_phrases:
        # Use word boundaries to avoid false positives
        # "character count" won't match "character of Hamlet"
        pattern = r'\b' + re.escape(phrase) + r'\b'
        if re.search(pattern, query_lower):
            return OPERATION_MAP[phrase]
    
    return None


# ═══════════════════════════════════════════════════════════════════════════
# TEXT EXTRACTION
# ═══════════════════════════════════════════════════════════════════════════

def extract_quoted_text(query: str) -> Optional[str]:
    """
    Extract text from quotes (single or double).
    
    Examples:
        "Convert 'hello' to uppercase" → "hello"
        'Make "world" uppercase' → "world"
    """
    # Try double quotes first
    double_quote_match = re.search(r'"([^"]+)"', query)
    if double_quote_match:
        return double_quote_match.group(1)
    
    # Try single quotes
    single_quote_match = re.search(r"'([^']+)'", query)
    if single_quote_match:
        return single_quote_match.group(1)
    
    return None

def extract_target_text(query: str, operation: str) -> Optional[str]:
    """
    Extract target text from query.
    
    Tries multiple patterns in order of specificity:
    1. Quoted text ('hello' or "hello")
    2. Colon format (text: hello)
    3. "of" format (count words of hello world)
    4. "in" format (how many words in hello world)
    5. Direct command (uppercase hello OR upper case hello)
    
    Args:
        query: User's query string
        operation: Detected operation type
        
    Returns:
        Extracted text or None
    """
    query_lower = query.lower().strip()
    
    # Pattern 1: Quoted text (highest priority)
    quoted = extract_quoted_text(query)
    if quoted:
        return quoted
    
    # Pattern 2: Colon format
    if ":" in query:
        parts = query.split(":", 1)
        if len(parts) == 2:
            target = parts[1].strip()
            if target:
                return target
    
    # Pattern 3: "of" keyword
    if " of " in query_lower:
        parts = query.lower().split(" of ", 1)
        if len(parts) == 2:
            # Get original case from query
            start_idx = query.lower().index(" of ") + 4
            target = query[start_idx:].strip()
            if target:
                return target
    
    # Pattern 4: "in" keyword
    if " in " in query_lower:
        parts = query.lower().split(" in ", 1)
        if len(parts) == 2:
            # Get original case from query
            start_idx = query.lower().index(" in ") + 4
            target = query[start_idx:].strip()
            if target:
                return target
    
    # Pattern 5: Direct command (only for case transformations)
    if operation in ["uppercase", "lowercase", "titlecase"]:
        words = query.split()
        
        if len(words) < 2:
            return None
        
        first_word = words[0].lower()
        
        # Check TWO-WORD triggers FIRST (more specific)
        if len(words) >= 3:
            second_word = words[1].lower()
            two_word = f"{first_word} {second_word}"
            
            if two_word in ["upper case", "lower case", "title case"]:
                # "upper case hello world" → extract "hello world"
                target = " ".join(words[2:]).strip()
                if target:
                    return target
        
        # Then check SINGLE-WORD triggers
        operation_triggers = {
            "uppercase": ["uppercase", "upper"],
            "lowercase": ["lowercase", "lower"],
            "titlecase": ["titlecase", "title", "capitalize"]
        }
        
        if first_word in operation_triggers.get(operation, []):
            # "uppercase hello world" → extract "hello world"
            target = " ".join(words[1:]).strip()
            if target:
                return target
    
    return None


# ═══════════════════════════════════════════════════════════════════════════
# VALIDATION
# ═══════════════════════════════════════════════════════════════════════════

def is_valid_text_query(query: str) -> bool:
    """
    Check if query should be handled by text pattern matcher.
    
    Skips queries that are clearly not text operations.
    """
    query_lower = query.lower()
    
    # Skip if asking about definitions/information
    skip_phrases = [
        "what is", "who is", "tell me about",
        "explain", "describe", "define"
    ]
    
    for phrase in skip_phrases:
        if phrase in query_lower:
            return False
    
    return True


# ═══════════════════════════════════════════════════════════════════════════
# MAIN PATTERN MATCHER
# ═══════════════════════════════════════════════════════════════════════════

def match_text_pattern(query: str) -> Optional[str]:
    """
    Try to match and execute text transformation.
    
    Args:
        query: User's query string
        
    Returns:
        Transformed text/count result, or None if no match
        
    Examples:
        "Convert 'hello' to uppercase" → "HELLO"
        "upper case hello world" → "HELLO WORLD"
        "Make 'WORLD' lowercase" → "world"
        "Count words in hello world" → "2"
        "What is character?" → None (not a text operation)
    """
    # Validation
    if not is_valid_text_query(query):
        return None
    
    # Detect operation
    operation = detect_operation(query)
    if not operation:
        return None
    
    # Extract target text
    target = extract_target_text(query, operation)
    if not target:
        return None
    
    # Execute text transformation
    try:
        input_data = TextTransformInput(
            text=target,
            operation=operation
        )
        
        tool_result = run_text(input_data)
        
        # Return clean result
        if tool_result.get("success"):
            value = tool_result["data"]["value"]
            return str(value)
        
    except Exception:
        # Tool execution failed, return None to fall back to LLM
        return None
    
    return None


# ═══════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════

def match(query: str) -> Optional[str]:
    """
    Public API for text pattern matching.
    
    Args:
        query: User's query string
        
    Returns:
        Result string or None
    """
    return match_text_pattern(query)