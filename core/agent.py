"""
Agent Module - Main Orchestrator

Coordinates the complete agent workflow:
1. Planning
2. Validation
3. Execution (with retry/replan on failure)
4. Response generation

Handles failure recovery through classification and adaptive replanning.
"""

import time
import uuid
from typing import Tuple, Optional, Dict, Any

from tools.schemas import PlannerOutput, ExecutionResult
from tools.usage_tracker import track_cost, aggregate_costs
from core.planner import plan_gateway
from core.executor import execute_plan
from core.responder import respond
from core.planner_validator import validate_plan, PlannerValidationError
from core.failure_classifier import FailureType, classify_failure
from core.replanner import replan_gateway
from app.config import MAX_REPLANS_PER_RUN, MAX_RETRIES_PER_STEP, MODEL_NAME
from infra.logger import (
    logger_api,
    log_replan_trigger,
    log_replan_attempt,
    LogContext
)
from tools.usage_tracker import QuotaManager, QuotaExceeded




# ═══════════════════════════════════════════════════════════════════════════════
# MAIN AGENT ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def run_agent(
    user_input: str,
    request_id: Optional[str] = None,
    quota: Optional[QuotaManager] = None
) -> str:
    """
    Main agent entry point. Process user query through complete pipeline.
    
    Flow:
        1. Generate plan
        2. Validate plan
        3. Execute with recovery (retry/replan on failure)
        4. Generate user-facing response
        
    Args:
        user_input: User's query
        request_id: Optional request ID for tracking
        
    Returns:
        User-facing response string
        
    Raises:
        PlannerValidationError: If plan validation fails
        ValueError: If input is invalid
    """

    # Generate request ID if not provided
    if not request_id:
        request_id = str(uuid.uuid4())[:8]

    # Log agent start
    _log_agent_start(user_input, request_id)
    start_time = time.perf_counter()

    try:
        # Validate input
        _validate_user_input(user_input)

        if not quota.can_call(MODEL_NAME):
            raise QuotaExceeded("Quota exhausted before planner")

        # Step 1: Generate plan
        logger_api.debug(f"AGENT_PLAN | request_id={request_id}")
        planner_output, planner_usage = plan_gateway(
            user_input=user_input,
            mode="plan",
            request_id=request_id
        )
        quota.record_call(MODEL_NAME)
        planner_cost = track_cost(planner_usage)

        # Step 2: Validate plan
        logger_api.debug(f"AGENT_VALIDATE | request_id={request_id}")
        validated = validate_plan(planner_output, user_input)

        if not validated["valid"]:
            logger_api.error(
                f"VALIDATION_FAILED | request_id={request_id} | "
                f"error={validated.get('error', 'unknown')[:100]}"
            )
            raise PlannerValidationError(validated["error"])

        normalized_plan = validated["normalized_plan"]

        # Step 3: Execute with recovery
        logger_api.debug(f"AGENT_EXECUTE | request_id={request_id}")
        executor_output, final_plan = run_with_recovery(
            quota=quota,
            user_input=user_input,
            initial_plan=normalized_plan,
            planner_cost=planner_cost,
            request_id=request_id,
        )

        # Add planner cost to metadata
        executor_output.metadata["planner_cost"] = planner_cost

        # Step 4: Determine response strategy
        prompt_strategy = _determine_response_strategy(planner_cost)


        if not quota.can_call(MODEL_NAME):
            raise QuotaExceeded("Quota exhausted before responder")

        # Step 5: Generate response
        logger_api.debug(
            f"AGENT_RESPOND | request_id={request_id} | strategy={prompt_strategy}"
        )
        responder_output, responder_usage = respond(
            planner_output=final_plan,
            execution_result=executor_output,
            prompt_strategy=prompt_strategy,
            request_id=request_id
        )
        quota.record_call(MODEL_NAME)

        # Track response cost
        responder_cost = track_cost(responder_usage)
        executor_output.metadata["responder_cost"] = responder_cost

        # Calculate total cost
        run_cost = aggregate_costs(planner_cost, responder_cost)
        executor_output.metadata["run_cost"] = run_cost

        # Log agent completion
        duration = time.perf_counter() - start_time
        _log_agent_complete(
            executor_output.execution_status,
            run_cost,
            duration,
            request_id
        )

        return responder_output, run_cost

    except PlannerValidationError as e:
        duration = time.perf_counter() - start_time
        logger_api.error(
            f"AGENT_VALIDATION_ERROR | request_id={request_id} | "
            f"duration={duration:.2f}s | error={str(e)[:200]}"
        )
        raise


    except QuotaExceeded as e:
        duration = time.perf_counter() - start_time
        logger_api.warning(
            f"AGENT_QUOTA_STOP | request_id={request_id} | "
            f"duration={duration:.2f}s | reason={str(e)}"
        )
        return "⚠️ Daily quota reached. Please try again later or switch models."


    except Exception as e:
        duration = time.perf_counter() - start_time
        logger_api.error(
            f"AGENT_ERROR | request_id={request_id} | "
            f"duration={duration:.2f}s | error={str(e)[:200]}"
        )
        raise


# ═══════════════════════════════════════════════════════════════════════════════
# EXECUTION WITH RECOVERY
# ═══════════════════════════════════════════════════════════════════════════════

def run_with_recovery(
    *,
    quota,
    user_input: str,
    initial_plan: PlannerOutput,
    planner_cost: Dict[str, Any],
    request_id: Optional[str] = None
) -> Tuple[ExecutionResult, PlannerOutput]:
    """
    Execute plan with automatic recovery on failure.
    
    Recovery strategies:
        - TRANSIENT failures → Retry same plan (up to MAX_RETRIES_PER_STEP)
        - STRUCTURAL failures → Replan (up to MAX_REPLANS_PER_RUN)
        - TERMINAL failures → Stop immediately
        
    Args:
        user_input: Original user query
        initial_plan: Validated execution plan
        planner_cost: Cost of initial planning
        request_id: Optional request ID for tracking
        
    Returns:
        Tuple of (ExecutionResult, final_plan)
    """
    plan = initial_plan
    retries: Dict[int, int] = {}  # step_id → retry_count
    replans = 0

    logger_api.info(
        f"RECOVERY_START | request_id={request_id} | "
        f"max_retries={MAX_RETRIES_PER_STEP} | max_replans={MAX_REPLANS_PER_RUN}"
    )

    while True:
        # Execute current plan
        executor_output = execute_plan(plan, execution_id=request_id)
        
        # Success - return immediately
        if executor_output.execution_status == "completed":
            logger_api.info(
                f"RECOVERY_SUCCESS | request_id={request_id} | "
                f"retries={sum(retries.values())} | replans={replans}"
            )
            return executor_output, plan

        # Failure - analyze and decide recovery strategy
        error = executor_output.metadata.get("error", "")
        failed_step_id = executor_output.metadata.get("failed_step_id")
        failed_tool = _get_tool_name(plan, failed_step_id)

        logger_api.warning(
            f"RECOVERY_FAILURE | request_id={request_id} | "
            f"step_id={failed_step_id} | tool={failed_tool} | error={error[:100]}"
        )

        # Classify failure type
        failure_type = classify_failure(error=error, tool_name=failed_tool)

        logger_api.info(
            f"FAILURE_CLASSIFIED | request_id={request_id} | "
            f"type={failure_type.value} | step_id={failed_step_id}"
        )

        # Strategy 1: TRANSIENT → Retry
        if failure_type == FailureType.TRANSIENT:
            retries.setdefault(failed_step_id, 0)
            retries[failed_step_id] += 1
            
            if retries[failed_step_id] <= MAX_RETRIES_PER_STEP:
                logger_api.info(
                    f"RETRY_ATTEMPT | request_id={request_id} | "
                    f"step_id={failed_step_id} | attempt={retries[failed_step_id]}/{MAX_RETRIES_PER_STEP}"
                )
                continue  # Re-run same plan

            logger_api.warning(
                f"RETRY_EXHAUSTED | request_id={request_id} | "
                f"step_id={failed_step_id} | attempts={retries[failed_step_id]}"
            )
            return executor_output, plan

        # Strategy 2: STRUCTURAL → Replan
        if failure_type == FailureType.STRUCTURAL:
            if replans < MAX_REPLANS_PER_RUN:
                replans += 1

                log_replan_trigger("structural_failure", failed_step_id)
                log_replan_attempt(replans, MAX_REPLANS_PER_RUN)

                try:
                    if not quota.can_call(MODEL_NAME):
                        raise QuotaExceeded(
                            "Quota exhausted during replanning phase"
                        )

                    # Attempt to repair plan
                    plan = replan_gateway(
                        original_plan=plan,
                        execution_result=executor_output,
                        user_input=user_input,
                        request_id=request_id
                    )
                    quota.record_call(MODEL_NAME)

                    logger_api.info(
                        f"REPLAN_SUCCESS | request_id={request_id} | "
                        f"attempt={replans}/{MAX_REPLANS_PER_RUN}"
                    )
                    continue  # Re-run with new plan

                except Exception as e:
                    logger_api.error(
                        f"REPLAN_FAILED | request_id={request_id} | "
                        f"attempt={replans} | error={str(e)[:200]}"
                    )
                    return executor_output, plan

            logger_api.warning(
                f"REPLAN_EXHAUSTED | request_id={request_id} | attempts={replans}"
            )
            return executor_output, plan

        # Strategy 3: TERMINAL → Stop
        logger_api.warning(
            f"TERMINAL_FAILURE | request_id={request_id} | "
            f"step_id={failed_step_id} | stopping"
        )
        return executor_output, plan


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def _validate_user_input(user_input: str):
    """Validate user input"""
    if not user_input or not user_input.strip():
        raise ValueError("User input cannot be empty")
    
    if len(user_input) > 2000:
        raise ValueError("User input too long (max 2000 characters)")


def _get_tool_name(plan: PlannerOutput, step_id: Optional[int]) -> Optional[str]:
    """Get tool name for a given step ID"""
    if step_id is None:
        return None

    for step in plan.steps:
        if step.step_id == step_id:
            return step.tool_name

    return None


def _determine_response_strategy(planner_cost: Dict[str, Any]) -> str:
    """
    Determine response generation strategy based on token usage.
    
    If we're approaching token budget limits, use compressed responses.
    """
    budget_state = planner_cost.get("budget_state", "safe")

    if budget_state in ("critical", "exceeded"):
        logger_api.warning(f"BUDGET_CRITICAL | using compressed responses")
        return "compressed"

    return "normal"


# ═══════════════════════════════════════════════════════════════════════════════
# LOGGING HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _log_agent_start(user_input: str, request_id: str):
    """Log agent processing start"""
    log_data = {
        "request_id": request_id,
        "query_length": len(user_input)
    }
    logger_api.info(f"AGENT_START | {LogContext.format_dict(log_data)}")


def _log_agent_complete(
    status: str,
    run_cost: Dict[str, Any],
    duration: float,
    request_id: str
):
    """Log agent processing completion"""
    log_data = {
        "request_id": request_id,
        "status": status,
        "total_tokens": run_cost.get("total_tokens", 0),
        "budget_state": run_cost.get("budget_state", "unknown"),
        "duration": f"{duration:.2f}s"
    }
    logger_api.info(f"AGENT_COMPLETE | {LogContext.format_dict(log_data)}")