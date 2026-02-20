
"""
Tool Execution Runner

Handles tool execution with:
- Input validation
- Retry logic with exponential backoff
- Timeout enforcement
- Comprehensive logging
- Error handling
"""

import time
from typing import Dict

from tools.registry import TOOL_REGISTRY
from tools.responses import tool_response
from infra.logger import logger_tool, LogContext


# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

# Exceptions that should not trigger retries
NON_RETRIABLE_EXCEPTIONS = (
    ValueError,
    TypeError,
    KeyError,
    ZeroDivisionError,
)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN TOOL RUNNER
# ═══════════════════════════════════════════════════════════════════════════════

def run_tool(tool_name: str, tool_args: dict, context: dict = None) -> dict:
    """
    Execute a tool with validation, retries, and logging.
    
    Args:
        tool_name: Name of tool to execute
        tool_args: Arguments to pass to the tool
        context: Optional context (step_id, execution_id, etc.)
        
    Returns:
        Tool response dictionary with success status and data/error
    """
    context = context or {}
    step_id = context.get("step_id")
    execution_id = context.get("execution_id")
    
    # Log tool execution start
    _log_tool_start(tool_name, step_id, execution_id)
    
    # Check if tool exists
    if tool_name not in TOOL_REGISTRY:
        error_msg = f"Unknown tool: {tool_name}"
        logger_tool.error(f"TOOL_NOT_FOUND | tool={tool_name}")
        return tool_response(tool=tool_name, success=False, error=error_msg)
    
    tool_entry = TOOL_REGISTRY[tool_name]
    
    # Validate input (no retries for validation errors)
    validated_input = _validate_input(tool_name, tool_entry["schema"], tool_args)
    if validated_input is None:  # Validation failed
        return tool_response(
            tool=tool_name,
            success=False,
            error="Input validation failed"
        )
    
    # Execute with retry logic
    return _execute_with_retries(
        tool_name=tool_name,
        tool_entry=tool_entry,
        validated_input=validated_input,
        context=context
    )


# ═══════════════════════════════════════════════════════════════════════════════
# INPUT VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

def _validate_input(tool_name: str, schema, tool_args: dict):
    """
    Validate tool input against schema.
    
    Args:
        tool_name: Name of the tool
        schema: Pydantic schema class
        tool_args: Arguments to validate
        
    Returns:
        Validated input object or None if validation fails
    """
    try:
        logger_tool.debug(f"VALIDATE_INPUT | tool={tool_name}")
        validated = schema(**tool_args)
        logger_tool.debug(f"VALIDATE_SUCCESS | tool={tool_name}")
        return validated
        
    except Exception as e:
        logger_tool.error(
            f"VALIDATION_FAIL | tool={tool_name} | error={str(e)[:200]}"
        )
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# EXECUTION WITH RETRIES
# ═══════════════════════════════════════════════════════════════════════════════

def _execute_with_retries(
    tool_name: str,
    tool_entry: dict,
    validated_input,
    context: dict
) -> dict:
    """
    Execute tool with retry logic.
    
    Args:
        tool_name: Name of the tool
        tool_entry: Tool registry entry
        validated_input: Validated input object
        context: Execution context
        
    Returns:
        Tool response dictionary
    """
    handler = tool_entry["handler"]
    max_retries = tool_entry["max_retries"]
    timeout = tool_entry["timeout"]
    deterministic = tool_entry["deterministic"]
    
    # Deterministic tools don't retry
    attempts_allowed = 1 if deterministic else (max_retries + 1)
    
    step_id = context.get("step_id")
    
    for attempt in range(1, attempts_allowed + 1):
        result = _execute_single_attempt(
            tool_name=tool_name,
            handler=handler,
            validated_input=validated_input,
            timeout=timeout,
            attempt=attempt,
            step_id=step_id
        )
        
        # Success - return immediately
        if result["success"]:
            return result
        
        # Tool-declared failure (don't retry)
        if _is_tool_declared_failure(result):
            logger_tool.warning(
                f"TOOL_DECLARED_FAIL | tool={tool_name} | error={result.get('error', 'unknown')[:100]}"
            )
            return result
        
        # Check if we should retry
        if deterministic or attempt >= attempts_allowed:
            logger_tool.error(
                f"TOOL_EXHAUSTED | tool={tool_name} | attempts={attempt}"
            )
            return result
        
        # Apply backoff before retry
        _apply_backoff(tool_name, attempt)
    
    # Should never reach here, but just in case
    return tool_response(
        tool=tool_name,
        success=False,
        error=f"Exhausted {attempts_allowed} attempts"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLE ATTEMPT EXECUTION
# ═══════════════════════════════════════════════════════════════════════════════

def _execute_single_attempt(
    tool_name: str,
    handler,
    validated_input,
    timeout: float,
    attempt: int,
    step_id: int = None
) -> dict:
    """
    Execute a single tool attempt with timeout checking.
    
    Args:
        tool_name: Name of the tool
        handler: Tool handler function
        validated_input: Validated input
        timeout: Maximum execution time
        attempt: Attempt number
        step_id: Optional step ID for context
        
    Returns:
        Tool response dictionary
    """
    start_time = time.perf_counter()
    
    # Log attempt
    _log_attempt_start(tool_name, attempt, step_id)
    
    try:
        # Execute the tool
        result = handler(validated_input)
        
        duration = time.perf_counter() - start_time
        duration_ms = duration * 1000
        
        # Check timeout
        if duration > timeout:
            error_msg = f"Timeout exceeded ({duration:.2f}s > {timeout}s)"
            logger_tool.error(
                f"TOOL_TIMEOUT | tool={tool_name} | attempt={attempt} | "
                f"duration={duration:.2f}s | timeout={timeout}s"
            )
            raise TimeoutError(error_msg)
        
        # Validate response format
        if not _is_valid_response(result):
            logger_tool.error(
                f"INVALID_RESPONSE | tool={tool_name} | attempt={attempt}"
            )
            return tool_response(
                tool=tool_name,
                success=False,
                error="Tool returned invalid response format"
            )
        
        # Log result
        _log_attempt_complete(tool_name, attempt, result["success"], duration_ms, step_id)
        
        return result
        
    except Exception as e:
        duration = time.perf_counter() - start_time
        duration_ms = duration * 1000
        
        # Log failure
        _log_attempt_failed(tool_name, attempt, str(e), duration_ms, step_id)
        
        return tool_response(
            tool=tool_name,
            success=False,
            error=str(e),
            meta={"attempt": attempt, "duration_ms": duration_ms}
        )


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def _is_valid_response(result) -> bool:
    """Check if result follows tool response contract"""
    return isinstance(result, dict) and "success" in result


def _is_tool_declared_failure(result: dict) -> bool:
    """
    Check if failure is declared by the tool itself.
    
    Tool-declared failures have success=False with a structured response,
    meaning the tool ran successfully but returned a failure result.
    """
    return (
        isinstance(result, dict) and
        result.get("success") == False and
        "error" in result
    )


def _apply_backoff(tool_name: str, attempt: int):
    """Apply exponential backoff before retry"""
    backoff = 0.5 * attempt  # 0.5s, 1.0s, 1.5s, etc.
    logger_tool.info(
        f"RETRY_BACKOFF | tool={tool_name} | attempt={attempt} | backoff={backoff}s"
    )
    time.sleep(backoff)


# ═══════════════════════════════════════════════════════════════════════════════
# LOGGING HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _log_tool_start(tool_name: str, step_id: int = None, execution_id: str = None):
    """Log tool execution start"""
    context = {"tool": tool_name}
    if step_id:
        context["step_id"] = step_id
    if execution_id:
        context["execution_id"] = execution_id
    logger_tool.debug(f"TOOL_START | {LogContext.format_dict(context)}")


def _log_attempt_start(tool_name: str, attempt: int, step_id: int = None):
    """Log attempt start"""
    context = {"tool": tool_name, "attempt": attempt}
    if step_id:
        context["step_id"] = step_id
    logger_tool.info(f"TOOL_ATTEMPT | {LogContext.format_dict(context)}")


def _log_attempt_complete(
    tool_name: str,
    attempt: int,
    success: bool,
    duration_ms: float,
    step_id: int = None
):
    """Log attempt completion"""
    context = {
        "tool": tool_name,
        "attempt": attempt,
        "success": success,
        "duration_ms": f"{duration_ms:.2f}"
    }
    if step_id:
        context["step_id"] = step_id
    
    log_level = logger_tool.info if success else logger_tool.warning
    status = "SUCCESS" if success else "FAIL"
    log_level(f"TOOL_{status} | {LogContext.format_dict(context)}")


def _log_attempt_failed(
    tool_name: str,
    attempt: int,
    error: str,
    duration_ms: float,
    step_id: int = None
):
    """Log attempt failure with error"""
    context = {
        "tool": tool_name,
        "attempt": attempt,
        "duration_ms": f"{duration_ms:.2f}",
        "error": error[:100]  # Truncate long errors
    }
    if step_id:
        context["step_id"] = step_id
    logger_tool.warning(f"TOOL_EXCEPTION | {LogContext.format_dict(context)}")