"""
Tool Schemas and Type Definitions

Defines Pydantic schemas for all available tools and core execution types.
Each tool has an input schema that validates parameters at planning time.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Literal, TypedDict, Type, Callable, Any


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL REGISTRY TYPE
# ═══════════════════════════════════════════════════════════════════════════════

class ToolEntry(TypedDict):
    """
    Registry entry for a tool.
    
    Attributes:
        schema: Pydantic model for validating tool inputs
        handler: Function that executes the tool
        requires_tool: Whether this tool needs external dependencies
        max_retries: Maximum retry attempts on failure
        timeout: Execution timeout in seconds
        cost: Resource cost tier
        deterministic: Whether tool produces same output for same input
        cacheable: Whether results can be cached
    """
    schema: Type[BaseModel]
    handler: Callable
    
    requires_tool: bool
    
    max_retries: int
    timeout: float
    
    cost: Literal["low", "medium", "high"]
    
    deterministic: bool
    cacheable: bool


# ═══════════════════════════════════════════════════════════════════════════════
# DATETIME TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

class NormalizeDateTimeInput(BaseModel):
    """
    Convert natural language time expressions to ISO format.
    
    Examples:
        - "tomorrow at 3pm" → "2026-01-30 15:00:00"
        - "next Monday" → "2026-02-02 00:00:00"
        - "in 2 hours" → "2026-01-29 16:30:00"
    """
    text: str = Field(
        ...,
        description="Natural language time expression to parse",
        examples=["tomorrow at 3pm", "next Monday", "in 2 hours"]
    )
    
    reference_datetime: Optional[str] = Field(
        None,
        description="Reference datetime in ISO format (YYYY-MM-DD HH:MM:SS) for relative calculations. Defaults to current time if not provided"
    )


class DateTimeInput(BaseModel):
    """
    Perform datetime operations: get current time, add days, get day of week, or calculate date differences.
    
    Operations:
        - now: Get current datetime
        - add_days: Add/subtract days from a base datetime
        - day_of_week: Get day name (Monday, Tuesday, etc.)
        - date_diff: Calculate difference between two dates
    """
    operation: Literal["now", "add_days", "day_of_week", "date_diff"] = Field(
        ...,
        description="Operation to perform"
    )
    
    # For add_days and day_of_week
    base_datetime: Optional[str] = Field(
        None,
        description="Base datetime in ISO format (YYYY-MM-DD HH:MM:SS)"
    )
    
    # For add_days only
    days: Optional[int] = Field(
        None,
        description="Number of days to add (positive) or subtract (negative)",
        examples=[7, -3, 14]
    )
    
    # For date_diff only
    start_datetime: Optional[str] = Field(
        None,
        description="Start datetime in ISO format for date_diff"
    )
    end_datetime: Optional[str] = Field(
        None,
        description="End datetime in ISO format for date_diff"
    )
    unit: Optional[Literal["secs", "mins", "hours", "days", "weeks", "months", "years"]] = Field(
        None,
        description="Unit to return the difference in"
    )
    rounding: Optional[Literal["floor", "ceil", "exact"]] = Field(
        None,
        description="Rounding method: 'floor' rounds down, 'ceil' rounds up, 'exact' returns precise value"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# WEB SEARCH TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

class WebSearchInput(BaseModel):
    """
    Search the web for information.
    
    Returns a list of search results with title, URL, snippet, and publish date.
    Must be followed by combine_search_results in the pipeline.
    """
    query: str = Field(
        ...,
        description="Search query string",
        examples=["Python tutorials", "latest AI news", "weather forecast"]
    )
    
    num_results: int = Field(
        default=2,
        description="Number of search results to return",
        ge=1,
        le=6
    )
    
    time_range: Literal["any", "past_year", "past_month", "past_week"] = Field(
        ...,
        description="Time range filter for results"
    )


class CombineSearchResults(BaseModel):
    """
    Combine multiple search results into a single text string.
    
    Takes the list output from web_search and merges all snippets into
    a single text block suitable for extraction or analysis.
    """
    results: Optional[list] = Field(
        None,
        description="List of search result objects from web_search"
    )


class ExtractInputFromTextInput(BaseModel):
    """
    Extract specific data from text. 
    
    Supports extracting numbers, percentages, dates, or text snippets.
    Use 'reference' to guide extraction to the right piece of information.
    """
    text: str = Field(
        None,
        description="Source text to extract information from"
    )
    
    extract_type: Literal["integer", "float", "percentage", "datetime", "text"] = Field(
        ...,
        description="Type of information to extract"
    )
    
    reference: Optional[str] = Field(
        None,
        description="Hint or keyword to guide extraction (e.g., 'release date', 'price', 'version number')",
        examples=["release date", "population count", "error code", "price"]
    )


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITY TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

class CalculatorInput(BaseModel):
    """
    Evaluate mathematical expressions.
    
    Supports basic arithmetic, parentheses, and common math operations.
    IMPORTANT: All values must be literals - calculator cannot accept dependencies.
    """
    expression: str = Field(
        ...,
        description="Mathematical expression to evaluate",
        examples=["2 + 2", "(10 * 5) / 2", "7 * 24"]
    )


class TextTransformInput(BaseModel):
    """
    Transform or analyze text.
    
    Operations include counting (words, characters, sentences) and
    case transformations (uppercase, lowercase, titlecase).
    """
    text: str = Field(
        ...,
        description="Input text to transform or analyze"
    )
    
    operation: Literal[
        "word_count",
        "char_count",
        "sentence_count",
        "uppercase",
        "lowercase",
        "titlecase"
    ] = Field(
        ...,
        description="Transformation operation to perform"
    )


class WeatherInput(BaseModel):
    """
    Get weather forecast for one or more locations.
    
    Returns current weather or forecast for up to 14 days ahead.
    Maximum 5 locations per request.
    """
    locations: List[str] = Field(
        ...,
        description="List of location names (cities, regions, or coordinates)",
        examples=[["New York"], ["London", "Paris"], ["Tokyo", "Seoul", "Beijing"]],
        min_length=1,
        max_length=5
    )
    
    days_ahead: int = Field(
        ...,
        description="Days ahead to forecast (0 for current weather, 1-14 for future)",
        ge=0,
        le=14
    )


# ═══════════════════════════════════════════════════════════════════════════════
# CORE EXECUTION SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class Step(BaseModel):
    """
    A single step in an execution plan.
    
    Attributes:
        step_id: Sequential identifier starting from 1
        instruction: Human-readable description of what this step does
        tool_name: Name of the tool to execute (must exist in registry)
        tool_args: Arguments to pass to the tool (can contain None for dependencies)
        metadata: Additional data including dependencies
    """
    step_id: int = Field(..., ge=1)
    instruction: str = Field(..., min_length=1)
    tool_name: str
    tool_args: dict
    metadata: dict = Field(default_factory=dict)


class PlannerOutput(BaseModel):
    """
    Output from the planning engine.
    
    Represents either a valid execution plan (possible) or an explanation
    of why the request cannot be fulfilled (impossible).
    """
    goal: str = Field(..., description="Clear statement of the user's objective")
    
    plan_status: Literal["possible", "impossible"] = Field(
        ...,
        description="Whether the plan can be executed"
    )
    
    steps: List[Step] = Field(
        default_factory=list,
        description="Ordered list of steps to execute (empty if impossible)"
    )
    
    fail_reason: Optional[Literal["scope_mismatch", "safety_violation", "logic_gap"]] = Field(
        None,
        description="Reason for failure (only present if plan_status is 'impossible')"
    )
    
    metadata: dict = Field(
        default_factory=dict,
        description="Additional planning metadata"
    )


class ExecutionResult(BaseModel):
    """
    Result of executing a plan.
    
    Contains the execution status, results from each step, and metadata
    about the execution process.
    """
    execution_status: Literal["skipped", "completed", "failed"] = Field(
        ...,
        description="Overall execution status"
    )
    
    step_results: List[dict] = Field(
        default_factory=list,
        description="Results from each executed step"
    )
    
    executed_steps: int = Field(
        ...,
        ge=0,
        description="Number of steps successfully executed"
    )
    
    metadata: dict = Field(
        default_factory=dict,
        description="Execution metadata (timing, errors, etc.)"
    )





