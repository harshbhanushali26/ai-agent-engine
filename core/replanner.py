"""
Replanner Module

Repairs failed execution plans by analyzing failures and generating
corrected plans with LLM guidance.
"""

import time
from typing import Optional, Dict, Any, List

from tools.schemas import PlannerOutput, ExecutionResult, Step
from core.planner import plan_gateway
from core.planner_validator import validate_plan, PlannerValidationError
from tools.registry import TOOL_REGISTRY
from infra.logger import logger_replanner, LogContext


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════════

def replan_gateway(
    *,
    original_plan: PlannerOutput,
    execution_result: ExecutionResult,
    user_input: str,
    request_id: Optional[str] = None
) -> PlannerOutput:
    """
    Repair a failed execution plan.
    
    Analyzes the failure, extracts successful steps, and generates
    a corrected plan that addresses the failure while reusing
    successful steps where possible.
    
    Args:
        original_plan: The plan that failed
        execution_result: Execution result with failure info
        user_input: Original user query
        request_id: Optional request ID for tracking
        
    Returns:
        New validated plan
        
    Raises:
        PlannerValidationError: If replanned plan is invalid
    """
    # Log replan start
    _log_replan_start(original_plan, execution_result, request_id)
    start_time = time.perf_counter()
    
    try:
        # Extract failure information
        failed_step_id = execution_result.metadata.get("failed_step_id")
        error = execution_result.metadata.get("error", "Unknown error")
        
        # Build context for replanner
        replan_context = _build_replan_context(
            original_plan=original_plan,
            execution_result=execution_result,
            failed_step_id=failed_step_id,
            error=error
        )
        
        logger_replanner.debug(
            f"REPLAN_CONTEXT | successful_steps={len(replan_context['successful_steps'])} | "
            f"failed_step={failed_step_id}"
        )
        
        # Call planner in replan mode
        logger_replanner.debug("Calling LLM for plan repair")
        planner_output, planner_usage = plan_gateway(
            user_input=user_input,
            mode="replan",
            context=replan_context,
            request_id=request_id
        )
        
        # Validate tool existence (quick check before full validation)
        _validate_tools_exist(planner_output)
        
        # Full validation
        logger_replanner.debug("Validating repaired plan")
        validated = validate_plan(planner_output, user_input)
        
        if not validated["valid"]:
            error_info = validated.get("error", "Unknown validation error")
            logger_replanner.error(
                f"REPLAN_VALIDATION_FAILED | error={str(error_info)[:200]}"
            )
            raise PlannerValidationError(error_info)
        
        # Log replan success
        duration_ms = (time.perf_counter() - start_time) * 1000
        _log_replan_complete(planner_output, duration_ms, request_id)
        
        return validated["normalized_plan"]
        
    except PlannerValidationError:
        # Re-raise validation errors
        raise
        
    except Exception as e:
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger_replanner.error(
            f"REPLAN_ERROR | duration_ms={duration_ms:.2f} | error={str(e)[:200]}"
        )
        raise


# ═══════════════════════════════════════════════════════════════════════════════
# CONTEXT BUILDING
# ═══════════════════════════════════════════════════════════════════════════════

def _build_replan_context(
    original_plan: PlannerOutput,
    execution_result: ExecutionResult,
    failed_step_id: Optional[int],
    error: str
) -> Dict[str, Any]:
    """
    Build context for replanner LLM.
    
    Includes:
        - Original goal
        - Successful steps (to preserve)
        - Failed step information
        - Error details
        
    Args:
        original_plan: Original plan that failed
        execution_result: Execution result
        failed_step_id: ID of step that failed
        error: Error message
        
    Returns:
        Context dictionary for replanner
    """
    # Extract successful steps
    successful_steps = _extract_successful_steps(
        original_plan=original_plan,
        execution_result=execution_result
    )
    
    # Get failed step details
    failed_step = _get_step_by_id(original_plan, failed_step_id)
    
    return {
        "original_goal": original_plan.goal,
        "failed_step": {
            "step_id": failed_step_id,
            "tool": failed_step.tool_name if failed_step else None,
            "instruction": failed_step.instruction if failed_step else None,
            "error": error
        },
        "successful_steps": successful_steps,
        "total_steps": len(original_plan.steps)
    }


def _extract_successful_steps(
    original_plan: PlannerOutput,
    execution_result: ExecutionResult
) -> List[Dict[str, Any]]:
    """
    Extract information about successful steps.
    
    Args:
        original_plan: Original plan
        execution_result: Execution result
        
    Returns:
        List of successful step information
    """
    successful = []
    
    for step_result in execution_result.step_results:
        if step_result.get("success"):
            step_id = step_result["step_id"]
            step = _get_step_by_id(original_plan, step_id)
            
            if step:
                successful.append({
                    "step_id": step.step_id,
                    "tool": step.tool_name,
                    "instruction": step.instruction,
                    "output_available": True  # Can be reused in dependencies
                })
                
                logger_replanner.debug(
                    f"SUCCESSFUL_STEP | step_id={step_id} | tool={step.tool_name}"
                )
    
    return successful


# ═══════════════════════════════════════════════════════════════════════════════
# VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

def _validate_tools_exist(plan: PlannerOutput):
    """
    Quick validation that all tools in plan exist in registry.
    
    Args:
        plan: Plan to validate
        
    Raises:
        PlannerValidationError: If unknown tool found
    """
    for step in plan.steps:
        if step.tool_name not in TOOL_REGISTRY:
            logger_replanner.error(
                f"UNKNOWN_TOOL | step_id={step.step_id} | tool={step.tool_name}"
            )
            raise PlannerValidationError({
                "category": "REPLAN_TOOL_ERROR",
                "message": f"Replanner used unknown tool '{step.tool_name}'",
                "step_id": step.step_id,
                "tool_name": step.tool_name
            })


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def _get_step_by_id(plan: PlannerOutput, step_id: Optional[int]) -> Optional[Step]:
    """Get step from plan by ID"""
    if step_id is None:
        return None
    
    for step in plan.steps:
        if step.step_id == step_id:
            return step
    
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# LOGGING HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _log_replan_start(
    original_plan: PlannerOutput,
    execution_result: ExecutionResult,
    request_id: Optional[str]
):
    """Log replan start"""
    failed_step_id = execution_result.metadata.get("failed_step_id")
    
    log_data = {
        "original_steps": len(original_plan.steps),
        "failed_step": failed_step_id,
        "executed_steps": execution_result.executed_steps
    }
    
    if request_id:
        log_data["request_id"] = request_id
    
    logger_replanner.info(f"REPLAN_START | {LogContext.format_dict(log_data)}")


def _log_replan_complete(
    new_plan: PlannerOutput,
    duration_ms: float,
    request_id: Optional[str]
):
    """Log replan completion"""
    log_data = {
        "status": new_plan.plan_status,
        "new_steps": len(new_plan.steps),
        "duration_ms": f"{duration_ms:.2f}"
    }
    
    if request_id:
        log_data["request_id"] = request_id
    
    logger_replanner.info(f"REPLAN_COMPLETE | {LogContext.format_dict(log_data)}")