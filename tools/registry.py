from tools.schemas import *
from tools.math.calculate import calculate
from tools.web.weather import get_weather
from tools.text.text_transform import run_text
from tools.time.datetime import run_datetime, normalize_datetime
from tools.web.web_search import web_search, combine_search_results
from tools.text.extract_text import extract_from_text



TOOL_REGISTRY: dict[str, ToolEntry] = {

    # ---------- CORE UTILITIES ----------

    "calculator": {
        "schema": CalculatorInput,
        "handler": calculate,
        "requires_tool": True,
        "max_retries": 0,
        "timeout": 1.0,
        "cost": "low",
        "deterministic": True,
        "cacheable": True,   # FIXED: pure math, safe to cache
    },

    "text_transform": {
        "schema": TextTransformInput,
        "handler": run_text,
        "requires_tool": True,
        "max_retries": 0,
        "timeout": 2.0,
        "cost": "low",
        "deterministic": True,
        "cacheable": True,   # FIXED: deterministic text ops
    },

    # ---------- DATETIME ----------

    "datetime": {
        "schema": DateTimeInput,
        "handler": run_datetime,
        "requires_tool": True,
        "max_retries": 0,
        "timeout": 1.0,
        "cost": "low",
        "deterministic": False,  # FIXED: depends on operation
        "cacheable": False,      # FIXED: "now" breaks caching
    },

    "normalize_datetime": {
        "schema": NormalizeDateTimeInput,
        "handler": normalize_datetime,
        "requires_tool": True,
        "max_retries": 1,
        "timeout": 4.0,
        "cost": "medium",
        "deterministic": False,  # NLP parsing
        "cacheable": False,
    },

    # ---------- WEATHER ----------

    "weather": {
        "schema": WeatherInput,
        "handler": get_weather,
        "requires_tool": True,
        "max_retries": 1,        # FIXED: avoid API abuse
        "timeout": 30.0,
        "cost": "medium",
        "deterministic": False,
        "cacheable": False,
    },

    # ---------- WEB ----------

    "web_search": {
        "schema": WebSearchInput,
        "handler": web_search,
        "requires_tool": True,
        "max_retries": 2,        # FIXED: reduce retry storms
        "timeout": 20.0,
        "cost": "high",
        "deterministic": False,
        "cacheable": False,
    },

    "combine_search_results": {
        "schema": CombineSearchResults,
        "handler": combine_search_results,
        "requires_tool": True,
        "max_retries": 0,
        "timeout": 3.0,
        "cost": "low",
        "deterministic": True,
        "cacheable": True,
    },

    # ---------- EXTRACTION ----------

    "extract_from_text": {
        "schema": ExtractInputFromTextInput,
        "handler": extract_from_text,
        "requires_tool": True,
        "max_retries": 0,
        "timeout": 6.0,
        "cost": "medium",        # FIXED: hallucination risk
        "deterministic": False,
        "cacheable": False,      # FIXED: unsafe to cache
    },
}
