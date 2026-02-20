"""
Agent Configuration

Centralized configuration for the AI agent system.
Environment variables and secrets should be loaded separately.
"""

from typing import Set, Literal


# ═══════════════════════════════════════════════════════════════════════════════
# LLM CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

# Available Gemini models (in order of capability)
# - gemini-2.5-flash-lite: Fastest, cheapest
# - gemini-2.5-flash: Balanced speed and quality
# - gemini-3-flash-preview: Latest features
AVAILABLE_MODELS = [
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-3-flash-preview"
]

# Default model for agent operations
MODEL_NAME: str = "gemini-2.5-flash-lite"

# Gemini API base URL
BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai/"


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT LIMITS
# ═══════════════════════════════════════════════════════════════════════════════

# Maximum steps allowed in a single plan
MAX_STEPS: int = 5

# Maximum retry attempts per tool execution
MAX_RETRIES_PER_STEP: int = 2

# Maximum replan attempts when execution fails
MAX_REPLANS_PER_RUN: int = 1


# ═══════════════════════════════════════════════════════════════════════════════
# COST & RESOURCE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

# Maximum logical context window of the model
MAX_CONTEXT_TOKENS: int = 128_000

# Token usage thresholds (as ratio of MAX_CONTEXT_TOKENS)
SAFE_LIMIT: float = 0.50      # Below this: safe zone
WARNING_LIMIT: float = 0.75   # Above this: approaching limit
CRITICAL_LIMIT: float = 0.90  # Above this: danger zone

# Token cost tracking (for budgeting and alerts)
TOKEN_COSTS = {
    "gemini-2.5-flash-lite": {
        "input": 0.000001,   # per token
        "output": 0.000004   # per token
    },
    "gemini-2.5-flash": {
        "input": 0.000002,
        "output": 0.000008
    },
    "gemini-3-flash-preview": {
        "input": 0.000003,
        "output": 0.000012
    }
}


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

# Tools that are currently disabled (maintenance, bugs, etc.)
DISABLED_TOOLS: Set[str] = set()

# Tools that can fail without causing complete execution failure
# If a non-critical tool fails, the system may continue or provide partial results
NON_CRITICAL_TOOLS: Set[str] = {"web_search"}

# Tool timeout overrides (in seconds)
# If not specified here, tools use their default timeout from registry
TOOL_TIMEOUT_OVERRIDES = {
    "web_search": 10.0,      # External API, may be slow
    "weather": 5.0,          # External API
    "calculator": 1.0,       # Should be fast
    "text_transform": 1.0    # Should be fast
}


# ═══════════════════════════════════════════════════════════════════════════════
# RESPONSE GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

# Response generation strategies
ResponseStrategy = Literal["normal", "compressed", "detailed"]

# Default strategy for generating user-facing responses
DEFAULT_RESPONSE_STRATEGY: ResponseStrategy = "normal"

# Enable LLM-based response generation (vs template-based)
USE_LLM_RESPONDER: bool = True

# Fallback responses (when LLM responder fails or is disabled)
FALLBACK_RESPONSES = {
    "skipped": "This request is not supported with the current capabilities.",
    "failed": "The request could not be completed due to an error.",
    "timeout": "The request timed out. Please try again with a simpler query.",
    "invalid": "The request could not be understood. Please rephrase your query."
}


# ═══════════════════════════════════════════════════════════════════════════════
# LOGGING CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

# Log level for the application
LOG_LEVEL: str = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL

# Enable file logging
ENABLE_FILE_LOGGING: bool = True

# Log file path
LOG_FILE_PATH: str = "runtime/logs/agent.log"

# Log LLM requests and responses (for debugging)
LOG_LLM_CALLS: bool = False  # Set to True in development only


# ═══════════════════════════════════════════════════════════════════════════════
# VALIDATION & SAFETY
# ═══════════════════════════════════════════════════════════════════════════════

# Enable strict validation (reject plans with any validation warnings)
STRICT_VALIDATION: bool = True

# Enable plan repair/replanning on validation failure
ENABLE_REPLANNING: bool = True

# Maximum query length (characters)
MAX_QUERY_LENGTH: int = 2000

# Minimum query length (characters)
MIN_QUERY_LENGTH: int = 3


# ═══════════════════════════════════════════════════════════════════════════════
# FEATURE FLAGS
# ═══════════════════════════════════════════════════════════════════════════════

# Enable experimental features
ENABLE_EXPERIMENTAL_TOOLS: bool = False

# Enable caching of tool results
ENABLE_TOOL_CACHING: bool = False

# Enable parallel tool execution (for independent steps)
ENABLE_PARALLEL_EXECUTION: bool = False


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def get_token_utilization_ratio(total_tokens: int) -> float:
    """Calculate token utilization as ratio of max context"""
    return total_tokens / MAX_CONTEXT_TOKENS


def get_budget_state(total_tokens: int) -> str:
    """Get budget state based on token usage"""
    ratio = get_token_utilization_ratio(total_tokens)
    
    if ratio < SAFE_LIMIT:
        return "safe"
    elif ratio < WARNING_LIMIT:
        return "warning"
    elif ratio < CRITICAL_LIMIT:
        return "critical"
    else:
        return "exceeded"


def get_tool_timeout(tool_name: str, default: float = 30.0) -> float:
    """Get timeout for a specific tool"""
    return TOOL_TIMEOUT_OVERRIDES.get(tool_name, default)


def is_tool_enabled(tool_name: str) -> bool:
    """Check if a tool is enabled"""
    return tool_name not in DISABLED_TOOLS


def validate_config():
    """Validate configuration on startup"""
    assert MODEL_NAME in AVAILABLE_MODELS, f"Invalid MODEL_NAME: {MODEL_NAME}"
    assert MAX_STEPS > 0, "MAX_STEPS must be positive"
    assert MAX_RETRIES_PER_STEP >= 0, "MAX_RETRIES_PER_STEP must be non-negative"
    assert 0 < SAFE_LIMIT < WARNING_LIMIT < CRITICAL_LIMIT <= 1.0, "Invalid limit thresholds"
    assert MAX_QUERY_LENGTH > MIN_QUERY_LENGTH, "Invalid query length limits"


# Validate on import
validate_config()