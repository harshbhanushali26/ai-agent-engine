"""
State Management & Failure Classification

Provides:
1. DependencyState - Manages step outputs and resolves dependencies
2. FailureClassifier - Classifies failures for recovery strategy
"""

from enum import Enum
from typing import Dict, Any, List, Optional

from infra.logger import logger_executor


# ═══════════════════════════════════════════════════════════════════════════════
# FAILURE CLASSIFICATION
# ═══════════════════════════════════════════════════════════════════════════════

class FailureType(Enum):
    """
    Types of failures and their recovery strategies.
    
    TRANSIENT: Temporary issues (network, timeouts) → Retry same plan
    STRUCTURAL: Plan/logic issues (validation, wrong tool) → Replan
    TERMINAL: Permanent issues (unsupported, permission) → Stop immediately
    """
    TRANSIENT = "transient"     # Retry same step
    STRUCTURAL = "structural"   # Re-plan
    TERMINAL = "terminal"       # Stop and respond


def classify_failure(
    *,
    error: str,
    tool_name: Optional[str] = None
) -> FailureType:
    """
    Classify execution failure to determine recovery strategy.
    
    Analyzes error message to determine if the failure is:
    - TRANSIENT: Can be fixed by retrying (network issues, rate limits)
    - STRUCTURAL: Requires replanning (wrong tool, validation errors)
    - TERMINAL: Cannot be fixed (unsupported operation, permissions)
    
    Args:
        error: Error message from failed execution
        tool_name: Optional tool name that failed
        
    Returns:
        FailureType indicating recovery strategy
        
    Examples:
        >>> classify_failure(error="Connection timeout")
        FailureType.TRANSIENT
        
        >>> classify_failure(error="Invalid argument type")
        FailureType.STRUCTURAL
        
        >>> classify_failure(error="Operation not supported")
        FailureType.TERMINAL
    """
    if not error:
        logger_executor.warning("CLASSIFY_FAILURE | empty error, defaulting to STRUCTURAL")
        return FailureType.STRUCTURAL
    
    e = error.lower()
    
    # TRANSIENT: Retry same plan (network, rate limits, timeouts)
    transient_indicators = (
        "timeout", "timed out", "connection error", "network error",
        "rate limit", "temporarily unavailable", "service unavailable",
        "502", "503", "504", "connection reset", "connection refused"
    )
    
    if any(indicator in e for indicator in transient_indicators):
        logger_executor.debug(f"CLASSIFY_FAILURE | TRANSIENT | error={error[:50]}")
        return FailureType.TRANSIENT
    
    # STRUCTURAL: Re-plan (validation, wrong tool, type errors)
    structural_indicators = (
        "validation error", "schema error", "type error", "dependency error",
        "input should be", "invalid argument", "cannot be parsed",
        "tool not applicable", "wrong tool", "missing required field",
        "unexpected value", "does not match", "field required"
    )
    
    if any(indicator in e for indicator in structural_indicators):
        logger_executor.debug(f"CLASSIFY_FAILURE | STRUCTURAL | error={error[:50]}")
        return FailureType.STRUCTURAL
    
    # TERMINAL: Fail fast (permanent issues)
    terminal_indicators = (
        "impossible", "unsupported", "not supported", "cannot be done",
        "not allowed", "permission denied", "access denied",
        "authentication failed", "unauthorized", "forbidden"
    )
    
    if any(indicator in e for indicator in terminal_indicators):
        logger_executor.debug(f"CLASSIFY_FAILURE | TERMINAL | error={error[:50]}")
        return FailureType.TERMINAL
    
    # Default: STRUCTURAL (safest assumption - try replanning)
    logger_executor.debug(
        f"CLASSIFY_FAILURE | UNKNOWN → STRUCTURAL | error={error[:50]}"
    )
    return FailureType.STRUCTURAL


