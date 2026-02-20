
"""
Test suite for datetime pattern matcher (using normalize_datetime tool)
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from patterns.datetime_pattern import (
    match_current_datetime,
    match_day_of_week,
    match_natural_date,
    match_days_in_month,
    match_datetime_pattern,
)


# ═══════════════════════════════════════════════════════════════════════════
# MOCK RESPONSES
# ═══════════════════════════════════════════════════════════════════════════

def mock_run_datetime_now():
    """Mock run_datetime for 'now' operation."""
    return {
        "success": True,
        "data": {"value": "2026-02-18 14:30:00"}
    }

def mock_run_datetime_day_of_week():
    """Mock run_datetime for 'day_of_week' operation."""
    return {
        "success": True,
        "data": {"value": "Wednesday"}
    }

def mock_normalize_datetime(text):
    """Mock normalize_datetime with common patterns."""
    patterns = {
        "7 days from today": "2026-02-25 14:30:00",
        "tomorrow": "2026-02-19 00:00:00",
        "next monday": "2026-02-23 00:00:00",
        "february": "2026-02-01 00:00:00",
        "february 2026": "2026-02-01 00:00:00",
        "april 2026": "2026-04-01 00:00:00",
    }
    
    normalized = patterns.get(text.lower())
    if normalized:
        return {"success": True, "data": {"value": normalized}}
    return {"success": False, "error": "Could not parse"}


# ═══════════════════════════════════════════════════════════════════════════
# TESTS
# ═══════════════════════════════════════════════════════════════════════════

def test_match_current_datetime():
    """Test current time and date patterns."""
    
    print("Testing match_current_datetime...")
    
    with patch('patterns.datetime_pattern.run_datetime', return_value=mock_run_datetime_now()):
        # Current time
        assert match_current_datetime("What's the time?") == "02:30 PM"
        assert match_current_datetime("What time is it?") == "02:30 PM"
        
        # Current date
        assert match_current_datetime("What's today's date?") == "February 18, 2026"
        assert match_current_datetime("What is the current date?") == "February 18, 2026"
        assert match_current_datetime("What date is it?") == "February 18, 2026"
        
        # Should NOT match
        assert match_current_datetime("Tell me about dates") is None
        assert match_current_datetime("Random query") is None
    
    print("✓ match_current_datetime tests passed")


def test_match_day_of_week():
    """Test day of week with natural language."""
    
    print("Testing match_day_of_week...")
    
    def mock_normalize(input_data):
        return mock_normalize_datetime(input_data.text)
    
    with patch('patterns.datetime_pattern.normalize_datetime', side_effect=mock_normalize):
        with patch('patterns.datetime_pattern.run_datetime', return_value=mock_run_datetime_day_of_week()):
            # "What day is X"
            assert match_day_of_week("What day is tomorrow?") == "Wednesday"
            assert match_day_of_week("What day will be next Monday?") == "Wednesday"
            
            # Should NOT match
            assert match_day_of_week("Tell me about days") is None
    
    print("✓ match_day_of_week tests passed")


def test_match_natural_date():
    """Test date from natural language."""
    
    print("Testing match_natural_date...")
    
    def mock_normalize(input_data):
        return mock_normalize_datetime(input_data.text)
    
    with patch('patterns.datetime_pattern.normalize_datetime', side_effect=mock_normalize):
        # "What date is X"
        assert match_natural_date("What date is 7 days from today?") == "February 25, 2026"
        assert match_natural_date("What date will be tomorrow?") == "February 19, 2026"
        assert match_natural_date("What date is next Monday?") == "February 23, 2026"
        
        # Should NOT match
        assert match_natural_date("Tell me about dates") is None
    
    print("✓ match_natural_date tests passed")


def test_match_days_in_month():
    """Test days in month calculations."""
    
    print("Testing match_days_in_month...")
    
    def mock_normalize(input_data):
        return mock_normalize_datetime(input_data.text)
    
    with patch('patterns.datetime_pattern.normalize_datetime', side_effect=mock_normalize):
        # Explicit month + year
        result = match_days_in_month("How many days in February 2026?")
        assert result == "28", f"Expected '28', got '{result}'"
        
        result = match_days_in_month("How many days in April 2026?")
        assert result == "30", f"Expected '30', got '{result}'"
        
        # Should NOT match
        assert match_days_in_month("Random query") is None
    
    print("✓ match_days_in_month tests passed")


def test_match_datetime_pattern():
    """Test main datetime pattern matcher."""
    
    print("Testing match_datetime_pattern...")
    
    def mock_normalize(input_data):
        return mock_normalize_datetime(input_data.text)
    
    with patch('patterns.datetime_pattern.normalize_datetime', side_effect=mock_normalize):
        with patch('patterns.datetime_pattern.run_datetime') as mock_run:
            # Setup mock to return appropriate responses
            def run_datetime_side_effect(input_data):
                if input_data.operation == "now":
                    return mock_run_datetime_now()
                elif input_data.operation == "day_of_week":
                    return mock_run_datetime_day_of_week()
                return {"success": False}
            
            mock_run.side_effect = run_datetime_side_effect
            
            # Current time
            assert match_datetime_pattern("What time is it?") == "02:30 PM"
            
            # Current date
            assert match_datetime_pattern("What's today's date?") == "February 18, 2026"
            
            # Day of week
            assert match_datetime_pattern("What day is tomorrow?") == "Wednesday"
            
            # Natural date
            assert match_datetime_pattern("What date is 7 days from today?") == "February 25, 2026"
            
            # Days in month
            assert match_datetime_pattern("How many days in February 2026?") == "28"
            
            # Should NOT match
            assert match_datetime_pattern("Tell me about Python") is None
    
    print("✓ match_datetime_pattern tests passed")


def run_all_tests():
    """Run all test functions."""
    print("\n" + "="*60)
    print("Running Datetime Pattern Matcher Tests")
    print("="*60 + "\n")
    
    try:
        test_match_current_datetime()
        test_match_day_of_week()
        test_match_natural_date()
        test_match_days_in_month()
        test_match_datetime_pattern()
        
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