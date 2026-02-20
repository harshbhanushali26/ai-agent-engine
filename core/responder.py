"""
Response Generation Module

Generates user-facing responses from execution results.
Supports both LLM-based and template-based response generation.
"""

import time
import re
from typing import Tuple, Dict, Any

from tools.schemas import PlannerOutput, ExecutionResult
from app.config import (
    MODEL_NAME,
    USE_LLM_RESPONDER,
    FALLBACK_RESPONSES,
    ResponseStrategy,
    DEFAULT_RESPONSE_STRATEGY,
    LOG_LLM_CALLS,
    get_token_utilization_ratio,
    get_budget_state
)
from tools.llm.client import client
from infra.logger import logger_api, LogContext
from prompts.responder_prompt import RESPONDER_SYSTEM_PROMPT


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════════

def respond(
    planner_output: PlannerOutput,
    execution_result: ExecutionResult,
    prompt_strategy: ResponseStrategy = DEFAULT_RESPONSE_STRATEGY,
    request_id: str = None
) -> Tuple[str, Dict[str, Any]]:
    """
    Generate user-facing response from execution result.
    
    Args:
        planner_output: Original plan
        execution_result: Execution result
        prompt_strategy: Response generation strategy
        request_id: Optional request ID for tracking
        
    Returns:
        Tuple of (response_text, usage_dict)
    """
    _log_response_start(execution_result.execution_status, request_id)
    start_time = time.perf_counter()
    
    try:
        # Route based on execution status
        if execution_result.execution_status == "skipped":
            response_text, usage = _handle_skipped(planner_output)
            
        elif execution_result.execution_status == "failed":
            response_text, usage = _handle_failed(
                planner_output,
                execution_result,
                prompt_strategy
            )
            
        else:  # completed
            response_text, usage = _handle_completed(
                planner_output,
                execution_result,
                prompt_strategy
            )
        
        # Log response generation complete
        duration_ms = (time.perf_counter() - start_time) * 1000
        _log_response_complete(
            execution_result.execution_status,
            usage,
            duration_ms,
            request_id
        )
        
        return response_text, usage
        
    except Exception as e:
        logger_api.error(f"RESPONSE_GENERATION_ERROR | error={str(e)[:200]}")
        
        # Return fallback response
        return FALLBACK_RESPONSES["failed"], _empty_usage()


# ═══════════════════════════════════════════════════════════════════════════════
# STATUS HANDLERS
# ═══════════════════════════════════════════════════════════════════════════════

def _handle_skipped(planner_output: PlannerOutput) -> Tuple[str, Dict[str, Any]]:
    """Handle skipped execution (impossible plan)"""
    logger_api.debug("RESPONSE_SKIPPED | using fallback")
    
    response = FALLBACK_RESPONSES["skipped"]
    
    # Add fail_reason context if available
    if planner_output.fail_reason:
        logger_api.debug(f"SKIP_REASON | reason={planner_output.fail_reason}")
    
    return response, _empty_usage()


def _handle_failed(
    planner_output: PlannerOutput,
    execution_result: ExecutionResult,
    prompt_strategy: ResponseStrategy
) -> Tuple[str, Dict[str, Any]]:
    """Handle failed execution"""
    
    # Option 1: Use LLM to explain failure
    if USE_LLM_RESPONDER:
        logger_api.debug("RESPONSE_FAILED | using LLM")
        try:
            return _llm_responder(
                planner_output,
                execution_result,
                prompt_strategy
            )
        except Exception as e:
            logger_api.warning(
                f"LLM_RESPONDER_FAILED | falling back to template | error={str(e)[:100]}"
            )
    
    # Option 2: Template-based fallback
    logger_api.debug("RESPONSE_FAILED | using template")
    
    failed_step_id = execution_result.metadata.get("failed_step_id")
    error = execution_result.metadata.get("error", "Unknown error")
    
    if failed_step_id:
        response = f"The request failed at step {failed_step_id}: {error}"
    else:
        response = FALLBACK_RESPONSES["failed"]
    
    return response, _empty_usage()


def _handle_completed(
    planner_output: PlannerOutput,
    execution_result: ExecutionResult,
    prompt_strategy: ResponseStrategy
) -> Tuple[str, Dict[str, Any]]:
    """Handle successful execution"""
    
    # Use LLM to generate response
    if USE_LLM_RESPONDER:
        logger_api.debug(
            f"RESPONSE_COMPLETED | using LLM | strategy={prompt_strategy}"
        )
        response_text, usage = _llm_responder(
            planner_output,
            execution_result,
            prompt_strategy
        )
        # return _llm_responder(
        #     planner_output,
        #     execution_result,
        #     prompt_strategy
        # )
        # Post-process for better formatting
        response_text = _format_response(response_text, execution_result)
        
        return response_text, usage

    # Template-based fallback (simple)
    logger_api.debug("RESPONSE_COMPLETED | using template")

    if execution_result.step_results:
        last_result = execution_result.step_results[-1]
        final_data = last_result.get("data", {}).get("data")
        response = f"The request completed successfully. Result: {final_data}"
    else:
        response = "The request completed successfully."
    
    return response, _empty_usage()


# ═══════════════════════════════════════════════════════════════════════════════
# LLM RESPONDER
# ═══════════════════════════════════════════════════════════════════════════════

def _llm_responder(
    planner_output: PlannerOutput,
    execution_result: ExecutionResult,
    prompt_strategy: ResponseStrategy
) -> Tuple[str, Dict[str, Any]]:
    """
    Generate response using LLM.
    
    Args:
        planner_output: Original plan
        execution_result: Execution result
        prompt_strategy: Response strategy
        
    Returns:
        Tuple of (response_text, usage_dict)
    """
    # Prepare system prompt
    system_prompt = RESPONDER_SYSTEM_PROMPT
    if prompt_strategy == "compressed":
        system_prompt += "\n\nRespond concisely in 1-2 sentences."
    elif prompt_strategy == "detailed":
        system_prompt += "\n\nProvide a detailed explanation with context."
    
    # Prepare user prompt
    user_prompt = f"""
Plan:
{planner_output.model_dump_json(indent=2)}

Execution Result:
{execution_result.model_dump_json(indent=2)}
"""
    
    # Log request if enabled
    if LOG_LLM_CALLS:
        logger_api.debug(
            f"LLM_RESPONDER_REQUEST | strategy={prompt_strategy} | "
            f"system_length={len(system_prompt)} | user_length={len(user_prompt)}"
        )
    
    # Call LLM
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )
    
    # Extract response
    response_text = response.choices[0].message.content
    usage = _extract_usage(response.usage)
    
    # Log response if enabled
    if LOG_LLM_CALLS:
        logger_api.debug(
            f"LLM_RESPONDER_RESPONSE | length={len(response_text)} | "
            f"tokens={usage['total_tokens']}"
        )
    
    return response_text, usage


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def _extract_usage(usage_obj) -> Dict[str, Any]:
    """Extract usage information from API response"""
    if not usage_obj:
        return _empty_usage()
    
    prompt_tokens = getattr(usage_obj, "prompt_tokens", 0)
    completion_tokens = getattr(usage_obj, "completion_tokens", 0)
    total_tokens = prompt_tokens + completion_tokens
    
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "token_utilization_ratio": get_token_utilization_ratio(total_tokens),
        "budget_state": get_budget_state(total_tokens)
    }


def _empty_usage() -> Dict[str, Any]:
    """Create empty usage dictionary for template-based responses"""
    return {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "token_utilization_ratio": 0.0,
        "budget_state": "safe"
    }






def _format_response(response_text: str, execution_result: ExecutionResult) -> str:
    """
    Post-process LLM response for better formatting.
    
    Detects if response should be formatted as list and adds bullets if missing.
    """
    # If response mentions multiple items but has no bullets, add them
    if _should_be_list(response_text) and not _has_bullets(response_text):
        return _add_bullets(response_text)
    
    return response_text


def _should_be_list(text: str) -> bool:
    """Check if response should be formatted as list."""
    list_indicators = [
        'highlights', 'key points', 'main points',
        'include', 'consists of', 'features',
        'following', 'these are'
    ]
    return any(indicator in text.lower() for indicator in list_indicators)


def _has_bullets(text: str) -> bool:
    """Check if text already has bullet points."""
    return bool(re.search(r'[•\-*]\s', text))


def _add_bullets(text: str) -> str:
    """Convert comma-separated list to bullet points."""
    # Split on commas or "and"
    items = re.split(r',\s*(?:and\s*)?', text)
    
    if len(items) < 3:
        return text  # Keep as-is if not really a list
    
    # Format as bullet list
    bullets = [f"• {item.strip()}" for item in items if item.strip()]
    return "\n".join(bullets)







# ═══════════════════════════════════════════════════════════════════════════════
# LOGGING HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _log_response_start(status: str, request_id: str = None):
    """Log response generation start"""
    log_data = {"status": status}
    if request_id:
        log_data["request_id"] = request_id
    logger_api.debug(f"RESPONSE_START | {LogContext.format_dict(log_data)}")


def _log_response_complete(
    status: str,
    usage: Dict[str, Any],
    duration_ms: float,
    request_id: str = None
):
    """Log response generation completion"""
    log_data = {
        "status": status,
        "tokens": usage.get("total_tokens", 0),
        "duration_ms": f"{duration_ms:.2f}"
    }
    if request_id:
        log_data["request_id"] = request_id
    logger_api.debug(f"RESPONSE_COMPLETE | {LogContext.format_dict(log_data)}")