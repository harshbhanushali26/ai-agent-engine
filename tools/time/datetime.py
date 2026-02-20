"""
DateTime Tool Handlers

Provides datetime operations and natural language time parsing.

Tools:
- run_datetime: Perform datetime operations (now, add_days, day_of_week, date_diff)
- normalize_datetime: Convert natural language to ISO datetime format
"""

from datetime import datetime, timedelta
from math import ceil, floor
import re
import dateparser

from tools.responses import tool_response
from tools.schemas import DateTimeInput, NormalizeDateTimeInput


# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

DATETIME_FMT = "%Y-%m-%d %H:%M:%S"

WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

TIME_UNIT_CONVERSIONS = {
    "secs": 1,
    "mins": 60,
    "hours": 3600,
    "days": 86400,
    "weeks": 86400 * 7,
    "months": 86400 * 30,  # Approximate
    "years": 86400 * 365,  # Approximate
}


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN DATETIME TOOL
# ═══════════════════════════════════════════════════════════════════════════════

def run_datetime(data: DateTimeInput):
    """
    Perform datetime operations.
    
    Operations:
        - now: Get current datetime
        - add_days: Add/subtract days from base datetime
        - day_of_week: Get day name from datetime
        - date_diff: Calculate difference between two datetimes
        
    Args:
        data: DateTimeInput with operation and relevant parameters
        
    Returns:
        tool_response with datetime string or number
    """
    try:
        # Resolve base datetime for operations that need it
        base_dt = _resolve_base_datetime(data.base_datetime)
        
        # Route to appropriate operation handler
        if data.operation == "now":
            result = _operation_now(base_dt)
            
        elif data.operation == "add_days":
            result = _operation_add_days(base_dt, data.days)
            
        elif data.operation == "day_of_week":
            result = _operation_day_of_week(base_dt)
            
        elif data.operation == "date_diff":
            result = _operation_date_diff(
                data.start_datetime,
                data.end_datetime,
                data.unit,
                data.rounding
            )
            
        else:
            raise ValueError(f"Invalid datetime operation: {data.operation}")
        
        return tool_response(
            tool="datetime",
            success=True,
            data=result,
            meta={"operation": data.operation}
        )
        
    except Exception as e:
        return tool_response(
            tool="datetime",
            success=False,
            error=str(e)
        )


# ═══════════════════════════════════════════════════════════════════════════════
# OPERATION HANDLERS
# ═══════════════════════════════════════════════════════════════════════════════

def _operation_now(base_dt: datetime) -> str:
    """Get current datetime (or base_dt if provided)"""
    return base_dt.strftime(DATETIME_FMT)


def _operation_add_days(base_dt: datetime, days: int) -> str:
    """Add days to base datetime"""
    if days is None:
        raise ValueError("'days' parameter is required for add_days operation")
    
    result_dt = base_dt + timedelta(days=days)
    return result_dt.strftime(DATETIME_FMT)


def _operation_day_of_week(base_dt: datetime) -> str:
    """Get day of week name"""
    return base_dt.strftime("%A")


def _operation_date_diff(
    start_datetime: str,
    end_datetime: str,
    unit: str,
    rounding: str
) -> float:
    """
    Calculate difference between two datetimes.
    
    Args:
        start_datetime: Start datetime in ISO format
        end_datetime: End datetime in ISO format
        unit: Unit to return difference in (secs, mins, hours, days, etc.)
        rounding: floor, ceil, or exact
        
    Returns:
        Number representing the time difference in specified units
    """
    if not start_datetime or not end_datetime or not unit:
        raise ValueError(
            "start_datetime, end_datetime, and unit are required for date_diff"
        )
    
    # Parse datetimes
    start_dt = datetime.strptime(start_datetime, DATETIME_FMT)
    end_dt = datetime.strptime(end_datetime, DATETIME_FMT)
    
    # Calculate difference in seconds
    delta_seconds = (end_dt - start_dt).total_seconds()
    
    # Convert to requested unit
    if unit not in TIME_UNIT_CONVERSIONS:
        raise ValueError(f"Unsupported unit: {unit}")
    
    value = delta_seconds / TIME_UNIT_CONVERSIONS[unit]
    
    # Apply rounding
    rounding = rounding or "exact"
    if rounding == "floor":
        return floor(value)
    elif rounding == "ceil":
        return ceil(value)
    else:  # exact
        return value


# ═══════════════════════════════════════════════════════════════════════════════
# NATURAL LANGUAGE DATETIME PARSER
# ═══════════════════════════════════════════════════════════════════════════════

def normalize_datetime(data: NormalizeDateTimeInput):
    """
    Convert natural language time expressions to ISO format.
    
    Uses deterministic parsing for common patterns (e.g., "next Monday")
    and falls back to dateparser for complex expressions.
    
    Examples:
        "tomorrow at 3pm" → "2026-01-30 15:00:00"
        "next Monday" → "2026-02-02 00:00:00"
        "in 2 hours" → "2026-01-29 16:30:00"
        
    Args:
        data: NormalizeDateTimeInput with text and optional reference_datetime
        
    Returns:
        tool_response with ISO datetime string
    """
    try:
        # Resolve reference datetime
        reference_dt = _resolve_base_datetime(data.reference_datetime)
        
        text = data.text.strip().lower()
        
        # Try fast deterministic parsing first
        parsed_dt = _parse_next_weekday(text, reference_dt)
        
        # Fallback to general NLP parsing
        if not parsed_dt:
            parsed_dt = _parse_with_dateparser(text, reference_dt)
        
        if not parsed_dt:
            raise ValueError(f"Could not parse datetime from text: '{data.text}'")
        
        return tool_response(
            tool="normalize_datetime",
            success=True,
            data=parsed_dt.strftime(DATETIME_FMT)
        )
        
    except Exception as e:
        return tool_response(
            tool="normalize_datetime",
            success=False,
            error=str(e)
        )


def _parse_next_weekday(text: str, reference_dt: datetime) -> datetime | None:
    """
    Fast deterministic parser for "next [weekday]" patterns.
    
    Examples:
        "next monday" → datetime object for next Monday
        "next friday" → datetime object for next Friday
    """
    match = re.match(
        r"next\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)",
        text
    )
    
    if not match:
        return None
    
    target_weekday = WEEKDAYS[match.group(1)]
    current_weekday = reference_dt.weekday()
    
    # Calculate days ahead (always next occurrence, not today)
    days_ahead = (target_weekday - current_weekday + 7) % 7
    if days_ahead == 0:
        days_ahead = 7
    
    return reference_dt + timedelta(days=days_ahead)


def _parse_with_dateparser(text: str, reference_dt: datetime) -> datetime | None:
    """
    Parse using dateparser library for complex expressions.
    
    Handles expressions like:
        - "tomorrow at 3pm"
        - "in 2 hours"
        - "January 15, 2026"
    """
    return dateparser.parse(
        text,
        settings={
            "RELATIVE_BASE": reference_dt,
            "PREFER_DATES_FROM": "future"
        }
    )


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def _resolve_base_datetime(datetime_str: str | None) -> datetime:
    """
    Convert datetime string to datetime object, or return current time.
    
    Args:
        datetime_str: ISO format datetime string or None
        
    Returns:
        datetime object
    """
    if datetime_str:
        return datetime.strptime(datetime_str, DATETIME_FMT)
    return datetime.now()

