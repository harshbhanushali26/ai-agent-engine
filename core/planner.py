"""
Plan Generation Module

Generates execution plans from user queries using LLM.
Supports both initial planning and replanning on failures.
"""

import json
import time
from typing import Tuple, Dict, Any, Optional

from tools.schemas import PlannerOutput
from app.config import MODEL_NAME, LOG_LLM_CALLS
from prompts.planner_prompt import PLANNER_PROMPT, REPLAN_PROMPT
from tools.llm.client import client
from infra.logger import logger_planner, LogContext


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════════

def plan_gateway(
    user_input: str,
    mode: str = "plan",
    context: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None
) -> Tuple[PlannerOutput, Dict[str, Any]]:
    """
    Generate or repair an execution plan.
    
    Args:
        user_input: User's query (for mode="plan")
        mode: "plan" for new plans, "replan" for repairs
        context: Context for replanning (original plan, failure info)
        request_id: Optional request ID for tracking
        
    Returns:
        Tuple of (PlannerOutput, usage_dict)
    """
    # Validate mode
    if mode not in ("plan", "replan"):
        raise ValueError(f"Invalid mode: {mode}. Must be 'plan' or 'replan'")
    
    # Log planning start
    _log_plan_start(mode, user_input, context, request_id)
    start_time = time.perf_counter()
    
    try:
        # Prepare prompts based on mode
        system_prompt, user_prompt = _prepare_prompts(mode, user_input, context)
        
        # Call LLM
        logger_planner.debug(f"LLM_CALL | mode={mode} | model={MODEL_NAME}")
        raw_result, usage = _call_llm_planner(user_prompt, system_prompt)
        
        # Parse and validate result
        logger_planner.debug(f"PARSE_RESPONSE | mode={mode}")
        plan = PlannerOutput(**raw_result)
        
        # Log result
        duration_ms = (time.perf_counter() - start_time) * 1000
        _log_plan_complete(mode, plan, duration_ms, usage, request_id)
        
        return plan, usage
        
    except json.JSONDecodeError as e:
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger_planner.error(
            f"JSON_PARSE_ERROR | mode={mode} | duration_ms={duration_ms:.2f} | error={str(e)[:100]}"
        )
        raise
        
    except Exception as e:
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger_planner.error(
            f"PLAN_FAILED | mode={mode} | duration_ms={duration_ms:.2f} | error={str(e)[:200]}"
        )
        raise


# ═══════════════════════════════════════════════════════════════════════════════
# PROMPT PREPARATION
# ═══════════════════════════════════════════════════════════════════════════════

def _prepare_prompts(
    mode: str,
    user_input: str,
    context: Optional[Dict[str, Any]]
) -> Tuple[str, str]:
    """
    Prepare system and user prompts based on mode.
    
    Args:
        mode: "plan" or "replan"
        user_input: Original user query
        context: Replanning context (if mode="replan")
        
    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    if mode == "replan":
        if not context:
            raise ValueError("context is required for replan mode")
        
        system_prompt = REPLAN_PROMPT
        user_prompt = json.dumps(context, indent=2)
        
        logger_planner.debug(
            f"REPLAN_CONTEXT | original_steps={len(context.get('original_plan', {}).get('steps', []))} | "
            f"failed_step={context.get('failure_info', {}).get('failed_step')}"
        )
    else:
        system_prompt = PLANNER_PROMPT
        user_prompt = user_input
        
        logger_planner.debug(f"PLAN_QUERY | length={len(user_input)}")
    
    return system_prompt, user_prompt


# ═══════════════════════════════════════════════════════════════════════════════
# LLM INTERACTION
# ═══════════════════════════════════════════════════════════════════════════════

def _call_llm_planner(
    user_prompt: str,
    system_prompt: str
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Call LLM to generate plan.
    
    Args:
        user_prompt: User message
        system_prompt: System message
        
    Returns:
        Tuple of (parsed_json_response, usage_dict)
        
    Raises:
        Exception: If API call fails
        json.JSONDecodeError: If response is not valid JSON
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    # Log request if enabled
    if LOG_LLM_CALLS:
        logger_planner.debug(
            f"LLM_REQUEST | system_length={len(system_prompt)} | "
            f"user_length={len(user_prompt)}"
        )
    
    try:
        # Make API call
        response = client.chat.completions.create(
            model=MODEL_NAME,
            response_format={"type": "json_object"},
            messages=messages
        )
        
        # Extract response
        raw_output = response.choices[0].message.content
        usage = _extract_usage(response.usage)
        
        # Log response if enabled
        if LOG_LLM_CALLS:
            logger_planner.debug(
                f"LLM_RESPONSE | length={len(raw_output)} | "
                f"tokens={usage['total_tokens']}"
            )
        
        # Parse JSON
        parsed_output = json.loads(raw_output)
        
        return parsed_output, usage
        
    except Exception as e:
        logger_planner.error(f"LLM_API_ERROR | error={str(e)[:200]}")
        raise


def _extract_usage(usage_obj) -> Dict[str, Any]:
    """
    Extract usage information from API response.
    
    Args:
        usage_obj: Usage object from API response
        
    Returns:
        Dictionary with usage statistics
    """
    if not usage_obj:
        return {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }
    
    return {
        "prompt_tokens": getattr(usage_obj, "prompt_tokens", 0),
        "completion_tokens": getattr(usage_obj, "completion_tokens", 0),
        "total_tokens": getattr(usage_obj, "total_tokens", 0)
    }


# ═══════════════════════════════════════════════════════════════════════════════
# LOGGING HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _log_plan_start(
    mode: str,
    user_input: str,
    context: Optional[Dict],
    request_id: Optional[str]
):
    """Log planning start"""
    log_data = {
        "mode": mode,
        "query_length": len(user_input) if mode == "plan" else 0
    }
    
    if request_id:
        log_data["request_id"] = request_id
    
    if mode == "replan" and context:
        log_data["replan_trigger"] = context.get("failure_info", {}).get("reason", "unknown")
    
    logger_planner.info(f"PLAN_START | {LogContext.format_dict(log_data)}")


def _log_plan_complete(
    mode: str,
    plan: PlannerOutput,
    duration_ms: float,
    usage: Dict[str, Any],
    request_id: Optional[str]
):
    """Log planning completion"""
    log_data = {
        "mode": mode,
        "status": plan.plan_status,
        "steps": len(plan.steps),
        "duration_ms": f"{duration_ms:.2f}",
        "tokens": usage.get("total_tokens", 0)
    }
    
    if request_id:
        log_data["request_id"] = request_id
    
    if plan.plan_status == "impossible":
        log_data["fail_reason"] = plan.fail_reason
    
    logger_planner.info(f"PLAN_COMPLETE | {LogContext.format_dict(log_data)}")