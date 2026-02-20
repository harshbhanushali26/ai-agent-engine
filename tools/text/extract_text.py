"""
Web Search Tool - Improved Extraction

Enhanced text extraction with:
- Sentence-level scoring
- Relevance ranking
- Multi-sentence synthesis
- Better handling of vague references
"""

from tools.responses import tool_response
import re
from datetime import datetime
import dateparser
from tools.schemas import ExtractInputFromTextInput

DATETIME_FMT = "%Y-%m-%d %H:%M:%S"


# ═══════════════════════════════════════════════════════════════════════════════
# EXTRACT FROM TEXT (IMPROVED)
# ═══════════════════════════════════════════════════════════════════════════════

def extract_from_text(data: ExtractInputFromTextInput):
    """
    Extract specific data from text with improved relevance scoring.
    
    Supports extraction of:
        - integer: Whole numbers
        - float: Decimal numbers
        - percentage: Percentage values
        - datetime: Dates and times
        - text: Text snippets with intelligent extraction
        
    Args:
        data: ExtractFromTextInput with text, extract_type, and optional reference
        
    Returns:
        tool_response with extracted value or synthesized answer
    """
    try:
        text = (data.text or "").strip()
        if not text:
            return tool_response(
                tool="extract_from_text",
                success=True,
                data=None
            )
        
        extract_type = data.extract_type
        reference = data.reference.lower() if data.reference else None
        
        # Route to appropriate extractor
        extractors = {
            "integer": lambda: _extract_integer(text),
            "float": lambda: _extract_float(text),
            "percentage": lambda: _extract_percentage(text),
            "datetime": lambda: _extract_datetime(text, reference),
            "text": lambda: _extract_text_improved(text, reference)  # NEW!
        }
        
        extractor = extractors.get(extract_type)
        if not extractor:
            raise ValueError(f"Unsupported extract_type: {extract_type}")
        
        result = extractor()
        
        return tool_response(
            tool="extract_from_text",
            success=True,
            data=result,
            meta={"extract_type": extract_type}
        )
        
    except Exception as e:
        return tool_response(
            tool="extract_from_text",
            success=False,
            error=str(e)
        )


# ═══════════════════════════════════════════════════════════════════════════════
# EXTRACTION HANDLERS
# ═══════════════════════════════════════════════════════════════════════════════

def _extract_integer(text: str) -> int | None:
    """Extract the first integer from text"""
    matches = re.findall(r"\b-?\d+\b", text)
    return int(matches[0]) if matches else None


def _extract_float(text: str) -> float | None:
    """Extract the first float from text"""
    matches = re.findall(r"\b-?\d+(?:\.\d+)?\b", text)
    return float(matches[0]) if matches else None


def _extract_percentage(text: str) -> float | None:
    """Extract percentage value (without the % sign)"""
    match = re.search(r"\b(\d+(?:\.\d+)?)\s*%\b", text)
    return float(match.group(1)) if match else None


def _extract_datetime(text: str, reference: str | None) -> str | None:
    """
    Extract datetime from text.
    
    Args:
        text: Source text
        reference: Hint about what datetime to look for
        
    Returns:
        ISO format datetime string or None
    """
    if not reference:
        raise ValueError("reference hint required for datetime extraction")
    
    parsed_dt = dateparser.parse(
        text,
        settings={"PREFER_DATES_FROM": "future"}
    )
    
    if not parsed_dt:
        return None
    
    return parsed_dt.strftime(DATETIME_FMT)


# ═══════════════════════════════════════════════════════════════════════════════
# IMPROVED TEXT EXTRACTION
# ═══════════════════════════════════════════════════════════════════════════════

def _extract_text_improved(text: str, reference: str | None) -> str | None:
    """
    Extract text with intelligent relevance scoring.
    
    Strategies:
    1. If no reference: Return full text (let LLM synthesize)
    2. If reference is vague (highlights, summary, info): Extract top sentences
    3. If reference is specific: Find most relevant sentence
    
    Args:
        text: Source text
        reference: Keyword or phrase to guide extraction
        
    Returns:
        Extracted/synthesized text or None
    """
    if not text:
        return None
    
    # Strategy 1: No reference → return all (let LLM handle it)
    if not reference:
        return text
    
    # Strategy 2: Vague reference → extract top N relevant sentences
    vague_keywords = [
        'highlights', 'summary', 'key points', 'main points',
        'overview', 'information', 'details', 'facts'
    ]
    
    is_vague = any(keyword in reference for keyword in vague_keywords)
    
    if is_vague:
        return _extract_top_sentences(text, reference, top_n=7)
    
    # Strategy 3: Specific reference → find best matching sentence
    return _extract_best_sentence(text, reference)


def _extract_top_sentences(text: str, reference: str, top_n: int = 7) -> str:
    """
    Extract top N most relevant sentences.
    
    For vague queries like "highlights" or "summary",
    return multiple relevant sentences.
    
    Args:
        text: Source text
        reference: Reference keywords
        top_n: Number of sentences to return
        
    Returns:
        Combined top sentences
    """
    sentences = _split_into_sentences(text)
    if not sentences:
        return text  # Fallback to full text
    
    # Score all sentences
    reference_words = set(reference.lower().split())
    scored_sentences = []
    
    for sentence in sentences:
        score = _score_sentence(sentence, reference_words)
        if score > 0:  # Only include sentences with some relevance
            scored_sentences.append((score, sentence))
    
    if not scored_sentences:
        # No relevant sentences found, return first N sentences as fallback
        return " ".join(sentences[:top_n])
    
    # Sort by score (highest first)
    scored_sentences.sort(reverse=True, key=lambda x: x[0])
    
    # Take top N
    top_sentences = [sent for score, sent in scored_sentences[:top_n]]
    
    return " ".join(top_sentences)


def _extract_best_sentence(text: str, reference: str) -> str | None:
    """
    Extract single best matching sentence.
    
    For specific queries, find the most relevant sentence.
    
    Args:
        text: Source text
        reference: Reference keywords
        
    Returns:
        Best matching sentence or None
    """
    sentences = _split_into_sentences(text)
    if not sentences:
        return None
    
    # Score all sentences
    reference_words = set(reference.lower().split())
    scored_sentences = []
    
    for sentence in sentences:
        score = _score_sentence(sentence, reference_words)
        if score > 0:
            scored_sentences.append((score, sentence))
    
    if not scored_sentences:
        return None
    
    # Return highest scoring sentence
    scored_sentences.sort(reverse=True, key=lambda x: x[0])
    return scored_sentences[0][1]


def _split_into_sentences(text: str) -> list[str]:
    """
    Split text into sentences.
    
    Handles:
    - Period, exclamation, question marks
    - Multiple punctuation
    - Preserves sentence structure
    
    Args:
        text: Source text
        
    Returns:
        List of sentences
    """
    # Split on sentence endings
    sentences = re.split(r'[.!?]+', text)
    
    # Clean and filter
    cleaned = []
    for sent in sentences:
        sent = sent.strip()
        # Keep sentences with at least 5 words (filter out fragments)
        if sent and len(sent.split()) >= 5:
            cleaned.append(sent)
    
    return cleaned


def _score_sentence(sentence: str, reference_words: set) -> float:
    """
    Score sentence relevance to reference keywords.
    
    Scoring factors:
    - Matching words (1 point each)
    - Exact phrase match (5 bonus points)
    - Sentence length penalty (very long = less focused)
    - Position bonus (earlier sentences often more important)
    
    Args:
        sentence: Sentence to score
        reference_words: Set of reference keywords
        
    Returns:
        Relevance score (higher = more relevant)
    """
    sentence_lower = sentence.lower()
    sentence_words = set(sentence_lower.split())
    
    # Base score: matching words
    matches = len(reference_words & sentence_words)
    score = float(matches)
    
    # Bonus: exact phrase match
    reference_phrase = " ".join(reference_words)
    if reference_phrase in sentence_lower:
        score += 5.0
    
    # Penalty: very long sentences (likely not direct answer)
    word_count = len(sentence.split())
    if word_count > 50:
        score *= 0.5
    elif word_count > 100:
        score *= 0.25
    
    # Bonus: short, focused sentences
    if 10 <= word_count <= 30:
        score *= 1.2
    
    return score


# ═══════════════════════════════════════════════════════════════════════════════
# VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

def _is_valid_extraction(text: str, reference: str | None) -> bool:
    """
    Validate extracted text makes sense.
    
    Args:
        text: Extracted text
        reference: Reference keywords
        
    Returns:
        True if valid, False otherwise
    """
    if not text or len(text) < 3:
        return False
    
    # Must contain some letters (not just symbols)
    if not re.search(r'[a-zA-Z]', text):
        return False
    
    # If reference provided, should still contain some reference words
    if reference:
        reference_words = reference.lower().split()
        text_lower = text.lower()
        matches = sum(1 for word in reference_words if word in text_lower)
        
        # At least 1 reference word should appear
        if matches == 0:
            return False
    
    return True