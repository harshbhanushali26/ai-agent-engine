"""
Datetime Pattern Matcher (Clean Architecture)

Pattern Layer = intent detection only
Tool Layer = all datetime computation
"""

import re
from datetime import datetime, timedelta
from typing import Optional

from tools.time.datetime import run_datetime, normalize_datetime
from tools.schemas import DateTimeInput, NormalizeDateTimeInput


DATETIME_FMT = "%Y-%m-%d %H:%M:%S"


# ═══════════════════════════════════════════════════════════════
# INTENT: CURRENT DATE / TIME
# ═══════════════════════════════════════════════════════════════

def match_current_datetime(query: str) -> Optional[str]:
    q = query.lower()

    # Current time
    if re.search(r"\bwhat'?s?\s+(the\s+)?time\b", q):
        result = run_datetime(DateTimeInput(operation="now"))
        if result.get("success"):
            dt = datetime.strptime(result["data"]["value"], DATETIME_FMT)
            return dt.strftime("%I:%M %p")
        return None

    # Current date
    if re.search(r"\b(today'?s?\s+date|current\s+date|what\s+date\s+is\s+it)\b", q):
        result = run_datetime(DateTimeInput(operation="now"))
        if result.get("success"):
            dt = datetime.strptime(result["data"]["value"], DATETIME_FMT)
            return dt.strftime("%B %d, %Y")
        return None

    return None


# ═══════════════════════════════════════════════════════════════
# INTENT: DAY OF WEEK (relative / natural language)
# ═══════════════════════════════════════════════════════════════

def match_day_of_week(query: str) -> Optional[str]:
    q = query.lower()

    match = re.search(r"what\s+day\s+(?:is|will\s+be)\s+(.+)", q)
    if not match:
        return None

    time_expression = match.group(1).strip(" ?")

    norm = normalize_datetime(
        NormalizeDateTimeInput(text=time_expression)
    )

    if not norm.get("success"):
        return None

    result = run_datetime(
        DateTimeInput(
            operation="day_of_week",
            base_datetime=norm["data"]["value"]
        )
    )

    if result.get("success"):
        return result["data"]["value"]

    return None


# ═══════════════════════════════════════════════════════════════
# INTENT: DATE FROM NATURAL LANGUAGE
# ═══════════════════════════════════════════════════════════════

def match_natural_date(query: str) -> Optional[str]:
    q = query.lower()

    match = re.search(r"what\s+date\s+(?:is|will\s+be)\s+(.+)", q)
    if not match:
        return None

    time_expression = match.group(1).strip(" ?")

    norm = normalize_datetime(
        NormalizeDateTimeInput(text=time_expression)
    )

    if not norm.get("success"):
        return None

    dt = datetime.strptime(norm["data"]["value"], DATETIME_FMT)
    return dt.strftime("%B %d, %Y")


# ═══════════════════════════════════════════════════════════════
# INTENT: DAYS IN MONTH
# ═══════════════════════════════════════════════════════════════

def match_days_in_month(query: str) -> Optional[str]:
    q = query.lower()

    match = re.search(r"how\s+many\s+days\s+in\s+([a-zA-Z]+\s*\d{0,4})", q)
    if not match:
        return None

    text = match.group(1).strip()

    # If year missing → use current year
    if not re.search(r"\d{4}", text):
        current_year = datetime.now().year
        text = f"{text} {current_year}"

    norm = normalize_datetime(
        NormalizeDateTimeInput(text=text)
    )

    if not norm.get("success"):
        return None

    dt = datetime.strptime(norm["data"]["value"], DATETIME_FMT)

    # Compute next month safely
    if dt.month == 12:
        next_month = datetime(dt.year + 1, 1, 1)
    else:
        next_month = datetime(dt.year, dt.month + 1, 1)

    last_day = next_month - timedelta(days=1)
    return str(last_day.day)


# ═══════════════════════════════════════════════════════════════
# MAIN ROUTER
# ═══════════════════════════════════════════════════════════════

def match_datetime_pattern(query: str) -> Optional[str]:
    for matcher in [
        match_current_datetime,
        match_day_of_week,
        match_natural_date,
        match_days_in_month,
    ]:
        result = matcher(query)
        if result:
            return result

    return None


def match(query: str) -> Optional[str]:
    return match_datetime_pattern(query)
