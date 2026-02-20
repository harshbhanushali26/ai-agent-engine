"""
Test suite for text pattern matcher
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from patterns.text_pattern import (
    detect_operation,
    extract_quoted_text,
    extract_target_text,
    is_valid_text_query,
    match_text_pattern,
)


def test_detect_operation():
    """Test operation detection."""
    
    print("Testing detect_operation...")
    
    # Case transformations
    assert detect_operation("Convert to uppercase") == "uppercase"
    assert detect_operation("make it lowercase") == "lowercase"
    assert detect_operation("titlecase this") == "titlecase"
    assert detect_operation("capitalize the text") == "titlecase"
    
    # Counting operations
    assert detect_operation("count words in text") == "word_count"
    assert detect_operation("how many characters") == "char_count"
    assert detect_operation("count sentences") == "sentence_count"
    
    # Should NOT match (word boundaries)
    assert detect_operation("What is the character of Hamlet?") is None
    assert detect_operation("Tell me about sentence structure") is None
    
    # No operation
    assert detect_operation("Tell me about Python") is None
    
    print("✓ detect_operation tests passed")


def test_extract_quoted_text():
    """Test quoted text extraction."""
    
    print("Testing extract_quoted_text...")
    
    # Double quotes
    assert extract_quoted_text('Convert "hello" to uppercase') == "hello"
    assert extract_quoted_text('Make "hello world" uppercase') == "hello world"
    
    # Single quotes
    assert extract_quoted_text("Convert 'world' to lowercase") == "world"
    assert extract_quoted_text("Make 'Python code' uppercase") == "Python code"
    
    # No quotes
    assert extract_quoted_text("Convert hello to uppercase") is None
    
    # Mixed quotes (prioritize double)
    assert extract_quoted_text('Convert "hello" and \'world\'') == "hello"
    
    print("✓ extract_quoted_text tests passed")


def test_extract_target_text():
    """Test target text extraction."""
    
    print("Testing extract_target_text...")
    
    # Quoted text (highest priority)
    assert extract_target_text("Convert 'hello' to uppercase", "uppercase") == "hello"
    assert extract_target_text('Make "world" lowercase', "lowercase") == "world"
    
    # Colon format
    assert extract_target_text("uppercase: hello world", "uppercase") == "hello world"
    assert extract_target_text("text: Python", "uppercase") == "Python"
    
    # "of" format
    assert extract_target_text("count words of hello world", "word_count") == "hello world"
    assert extract_target_text("uppercase of test", "uppercase") == "test"
    
    # "in" format
    assert extract_target_text("how many words in hello world", "word_count") == "hello world"
    assert extract_target_text("count chars in Python", "char_count") == "Python"
    
    # Direct command
    assert extract_target_text("uppercase hello", "uppercase") == "hello"
    assert extract_target_text("lowercase WORLD", "lowercase") == "WORLD"
    
    # Edge cases
    assert extract_target_text("uppercase", "uppercase") is None  # No text
    assert extract_target_text("count words of", "word_count") is None  # Empty
    
    print("✓ extract_target_text tests passed")


def test_is_valid_text_query():
    """Test query validation."""
    
    print("Testing is_valid_text_query...")
    
    # Valid text queries
    assert is_valid_text_query("Convert hello to uppercase") == True
    assert is_valid_text_query("count words in text") == True
    
    # Invalid (information queries)
    assert is_valid_text_query("What is uppercase?") == False
    assert is_valid_text_query("Tell me about lowercase") == False
    assert is_valid_text_query("Explain titlecase") == False
    
    print("✓ is_valid_text_query tests passed")


def test_match_text_pattern():
    """Test complete pattern matching."""
    
    print("Testing match_text_pattern...")
    
    # Uppercase transformations
    assert match_text_pattern("Convert 'hello' to uppercase") == "HELLO"
    assert match_text_pattern('Make "world" uppercase') == "WORLD"
    assert match_text_pattern("uppercase: python") == "PYTHON"
    assert match_text_pattern("uppercase hello") == "HELLO"
    
    # Lowercase transformations
    assert match_text_pattern("Convert 'HELLO' to lowercase") == "hello"
    assert match_text_pattern("Make 'WORLD' lowercase") == "world"
    assert match_text_pattern("lowercase: PYTHON") == "python"
    
    # Titlecase transformations
    assert match_text_pattern("Convert 'hello world' to titlecase") == "Hello World"
    assert match_text_pattern("capitalize 'python code'") == "Python Code"
    
    # Word count
    assert match_text_pattern("count words in hello world") == "2"
    assert match_text_pattern("how many words in the quick brown fox") == "4"
    assert match_text_pattern("word count of hello") == "1"
    
    # Character count
    assert match_text_pattern("count characters in hello") == "5"
    assert match_text_pattern("how many chars in Python") == "6"
    assert match_text_pattern("character count of abc") == "3"
    
    # Sentence count
    assert match_text_pattern("count sentences in Hello. World.") == "2"
    assert match_text_pattern("how many sentences in Hi! How are you?") == "2"
    
    # Case preservation in input
    assert match_text_pattern("Make 'HeLLo WoRLd' uppercase") == "HELLO WORLD"
    assert match_text_pattern("Make 'HeLLo WoRLd' lowercase") == "hello world"
    
    # Should NOT match
    assert match_text_pattern("What is uppercase?") is None
    assert match_text_pattern("Tell me about lowercase") is None
    assert match_text_pattern("Convert to uppercase") is None  # No text
    
    # False positives (should NOT match)
    assert match_text_pattern("What is the character of Hamlet?") is None
    assert match_text_pattern("Tell me about sentence structure") is None
    
    print("✓ match_text_pattern tests passed")


def test_edge_cases():
    """Test edge cases and error handling."""
    
    print("Testing edge cases...")
    
    # Empty text
    assert match_text_pattern("uppercase:") is None
    assert match_text_pattern("count words of") is None
    
    # Only whitespace
    assert match_text_pattern("uppercase:   ") is None
    
    # Special characters
    assert match_text_pattern("Convert '!@#$%' to uppercase") == "!@#$%"
    assert match_text_pattern("count words in hello-world") == "1"  # Hyphenated = 1 word
    
    # Unicode
    assert match_text_pattern("Convert 'café' to uppercase") == "CAFÉ"
    assert match_text_pattern("count chars in café") == "4"
    
    # Very long text
    long_text = "word " * 100
    assert match_text_pattern(f"count words in {long_text}") == "100"
    
    print("✓ edge cases tests passed")
    

def test_two_word_commands():
    """Test two-word command formats."""
    
    print("Testing two-word commands...")
    
    # Two-word triggers
    assert match_text_pattern("upper case hello world") == "HELLO WORLD"
    assert match_text_pattern("lower case HELLO WORLD") == "hello world"
    assert match_text_pattern("title case hello world") == "Hello World"
    
    # Mixed with quoted
    assert match_text_pattern("upper case 'hello world'") == "HELLO WORLD"
    
    # Single-word still works
    assert match_text_pattern("uppercase hello") == "HELLO"
    assert match_text_pattern("lowercase WORLD") == "world"
    
    print("✓ two-word commands tests passed")


def run_all_tests():
    """Run all test functions."""
    print("\n" + "="*60)
    print("Running Text Pattern Matcher Tests")
    print("="*60 + "\n")
    
    try:
        test_detect_operation()
        test_extract_quoted_text()
        test_extract_target_text()
        test_is_valid_text_query()
        test_match_text_pattern()
        test_edge_cases()
        test_two_word_commands()
        
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED!")
        print("="*60 + "\n")
        
    except AssertionError as e:
        print("\n" + "="*60)
        print("❌ TEST FAILED!")
        print("="*60)
        print(f"Error: {e}\n")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    run_all_tests()