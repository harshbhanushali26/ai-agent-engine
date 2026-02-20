"""
Test suite for math pattern matcher
"""

import sys
from pathlib import Path

# Add project root to path so we can import from patterns/
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from patterns.math_pattern import (
    extract_math_expression,
    is_safe_expression,
    format_math_result,
    match_math_pattern,
    should_skip_math_pattern,
)


def test_extract_math_expression():
    """Test expression extraction."""
    
    print("Testing extract_math_expression...")
    
    # Valid expressions
    assert extract_math_expression("What's 5 + 3?") == "5 + 3"
    assert extract_math_expression("Calculate 10*2") == "10*2"
    assert extract_math_expression("(5+3)*2 please") == "(5+3)*2"
    assert extract_math_expression("What's -10 + 2?") == "-10 + 2"
    assert extract_math_expression("100 - 23.50 + 40") == "100 - 23.50 + 40"
    
    # Invalid (no operator)
    assert extract_math_expression("What is 42?") is None
    assert extract_math_expression("Tell me about 7") is None
    
    # Invalid (no math)
    assert extract_math_expression("Hello world") is None
    assert extract_math_expression("Tell me about Python") is None
    
    print("✓ extract_math_expression tests passed")


def test_is_safe_expression():
    """Test safety validation."""
    
    print("Testing is_safe_expression...")
    
    # Valid
    assert is_safe_expression("5 + 3") == True
    assert is_safe_expression("10*2") == True
    assert is_safe_expression("(5+3)*2") == True
    
    # Invalid (unbalanced parentheses)
    assert is_safe_expression("(5 + 3") == False
    assert is_safe_expression("5 + 3)") == False
    
    # Invalid (unsafe characters)
    assert is_safe_expression("5 + __import__") == False
    
    # Invalid (too long)
    assert is_safe_expression("1+" * 100) == False
    
    print("✓ is_safe_expression tests passed")


def test_format_math_result():
    """Test result formatting."""
    
    print("Testing format_math_result...")
    
    # Whole numbers
    assert format_math_result(8.0) == "8"
    assert format_math_result(100.0) == "100"
    
    # Decimals
    assert format_math_result(3.33333) == "3.33"
    assert format_math_result(116.5) == "116.5"
    assert format_math_result(0.5) == "0.5"
    
    print("✓ format_math_result tests passed")


def test_match_math_pattern():
    """Test complete pattern matching."""
    
    print("Testing match_math_pattern...")
    
    # Simple operations
    assert match_math_pattern("What's 5 + 3?") == "8"
    assert match_math_pattern("Calculate 10*2") == "20"
    assert match_math_pattern("100 / 4") == "25"
    
    # Complex expressions
    assert match_math_pattern("(10+5)*2") == "30"
    assert match_math_pattern("5 + 3 * 2") == "11"  # Order of operations
    assert match_math_pattern("100 - 23.50 + 40") == "116.5"
    
    # Negative numbers
    assert match_math_pattern("What's -10 + 2?") == "-8"
    assert match_math_pattern("-5 * 3") == "-15"
    
    # Modulo and power
    assert match_math_pattern("10 % 3") == "1"
    assert match_math_pattern("2 ** 8") == "256"
    
    # Invalid (no match)
    assert match_math_pattern("Tell me about Python") is None
    assert match_math_pattern("What is 42?") is None
    
    # Invalid (division by zero)
    assert match_math_pattern("10 / 0") is None
    
    print("✓ match_math_pattern tests passed")


def test_should_skip_math_pattern():
    """Test skip logic."""
    
    print("Testing should_skip_math_pattern...")
    
    # Should skip (datetime queries)
    assert should_skip_math_pattern("What date is 5 days from today?") == True
    assert should_skip_math_pattern("What time is it?") == True
    
    # Should skip (weather)
    assert should_skip_math_pattern("What's the weather?") == True
    
    # Should skip (text operations)
    assert should_skip_math_pattern("Convert 'hello' to uppercase") == True
    
    # Should skip (web search)
    assert should_skip_math_pattern("Who is the president?") == True
    assert should_skip_math_pattern("What is Python?") == True
    
    # Should NOT skip (has math operators)
    assert should_skip_math_pattern("What's 5 + 3?") == False
    assert should_skip_math_pattern("Calculate 10*2") == False
    assert should_skip_math_pattern("What is 2 + 2?") == False  # Has + operator
    
    print("✓ should_skip_math_pattern tests passed")


def run_all_tests():
    """Run all test functions."""
    print("\n" + "="*60)
    print("Running Math Pattern Matcher Tests")
    print("="*60 + "\n")
    
    try:
        test_extract_math_expression()
        test_is_safe_expression()
        test_format_math_result()
        test_match_math_pattern()
        test_should_skip_math_pattern()
        
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED!")
        print("="*60 + "\n")
        
    except AssertionError as e:
        print("\n" + "="*60)
        print("❌ TEST FAILED!")
        print("="*60)
        print(f"Error: {e}\n")
        raise


if __name__ == "__main__":
    run_all_tests()