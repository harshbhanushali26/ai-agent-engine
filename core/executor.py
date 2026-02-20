"""
Plan Execution Module

Executes validated plans by running tools in sequence,
resolving dependencies, and managing state.
"""

import time
from typing import Optional

from tools.schemas import PlannerOutput, ExecutionResult, Step
from app.runner import run_tool
from core.state import DependencyState
from infra.logger import (
    logger_executor,
    log_execution_start,
    log_execution_complete,
    log_step_start,
    log_step_complete,
    log_dependency_resolution,
    LogContext
)


# ═══════════════════════════════════════════════════════════════════════════════
# EXCEPTIONS
# ═══════════════════════════════════════════════════════════════════════════════

class DependencyResolutionError(Exception):
    """Raised when dependency resolution fails"""
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════════

def execute_plan(
    planner_output: PlannerOutput,
    execution_id: Optional[str] = None
) -> ExecutionResult:
    """
    Execute a validated plan.
    
    Executes steps in sequence, resolving dependencies and
    managing state. Stops on first failure.
    
    Args:
        planner_output: Validated plan to execute
        execution_id: Optional ID for tracking this execution
        
    Returns:
        ExecutionResult with status and step results
    """
    # Handle impossible plans
    if planner_output.plan_status == "impossible":
        logger_executor.info("PLAN_IMPOSSIBLE | skipping execution")
        return _create_skipped_result()
    
    # Log execution start
    log_execution_start(len(planner_output.steps), execution_id)
    start_time = time.perf_counter()
    
    # Initialize execution state
    dependency_state = DependencyState()
    step_results = []
    executed_steps = 0
    
    try:
        # Execute each step in sequence
        for step in planner_output.steps:
            step_result = _execute_single_step(
                step=step,
                dependency_state=dependency_state,
                execution_id=execution_id
            )
            
            step_results.append(step_result)
            executed_steps += 1
            
            # Check for failure
            if not step_result["success"]:
                logger_executor.error(
                    f"STEP_FAILED | step_id={step.step_id} | tool={step.tool_name} | "
                    f"error={step_result['data'].get('error', 'unknown')[:100]}"
                )
                
                duration = time.perf_counter() - start_time
                log_execution_complete(executed_steps, "failed", duration)
                
                return _create_failed_result(
                    step_results=step_results,
                    executed_steps=executed_steps,
                    failed_step=step,
                    error=step_result["data"].get("error")
                )
            
            # Store result for future dependencies
            dependency_state.store(step.step_id, step_result["data"])
        
        # All steps completed successfully
        duration = time.perf_counter() - start_time
        log_execution_complete(executed_steps, "completed", duration)
        
        return ExecutionResult(
            execution_status="completed",
            step_results=step_results,
            executed_steps=executed_steps,
            metadata={"duration_seconds": duration}
        )
        
    except DependencyResolutionError as e:
        logger_executor.error(f"DEPENDENCY_ERROR | error={str(e)[:200]}")
        
        duration = time.perf_counter() - start_time
        log_execution_complete(executed_steps, "failed", duration)
        
        return ExecutionResult(
            execution_status="failed",
            step_results=step_results,
            executed_steps=executed_steps,
            metadata={
                "error": str(e),
                "error_type": "dependency_resolution",
                "duration_seconds": duration
            }
        )
        
    except Exception as e:
        logger_executor.error(f"EXECUTION_ERROR | error={str(e)[:200]}")
        
        duration = time.perf_counter() - start_time
        log_execution_complete(executed_steps, "failed", duration)
        
        return ExecutionResult(
            execution_status="failed",
            step_results=step_results,
            executed_steps=executed_steps,
            metadata={
                "error": str(e),
                "error_type": "unexpected",
                "duration_seconds": duration
            }
        )


# ═══════════════════════════════════════════════════════════════════════════════
# STEP EXECUTION
# ═══════════════════════════════════════════════════════════════════════════════

def _execute_single_step(
    step: Step,
    dependency_state: DependencyState,
    execution_id: Optional[str]
) -> dict:
    """
    Execute a single step with dependency resolution.
    
    Args:
        step: Step to execute
        dependency_state: Dependency state manager
        execution_id: Optional execution ID for context
        
    Returns:
        Step result dictionary
        
    Raises:
        DependencyResolutionError: If dependency resolution fails
    """
    # Log step start
    log_step_start(step.step_id, step.tool_name, step.instruction)
    step_start = time.perf_counter()
    
    # Resolve dependencies
    dependencies = step.metadata.get("dependencies", [])
    
    if dependencies:
        log_dependency_resolution(step.step_id, len(dependencies))
        logger_executor.debug(
            f"RESOLVE_START | step_id={step.step_id} | deps={len(dependencies)}"
        )
        
        try:
            resolved_args = dependency_state.resolve_dependencies(
                tool_args=step.tool_args,
                dependencies=dependencies
            )
            
            logger_executor.debug(
                f"RESOLVE_COMPLETE | step_id={step.step_id}"
            )
            
        except KeyError as e:
            logger_executor.error(
                f"RESOLVE_FAILED | step_id={step.step_id} | error={str(e)}"
            )
            raise DependencyResolutionError(
                f"Step {step.step_id}: Failed to resolve dependency - {str(e)}"
            )
    else:
        resolved_args = step.tool_args
    
    # Execute tool
    logger_executor.debug(
        f"EXECUTE_TOOL | step_id={step.step_id} | tool={step.tool_name}"
    )
    
    tool_result = run_tool(
        tool_name=step.tool_name,
        tool_args=resolved_args,
        context={
            "step_id": step.step_id,
            "execution_id": execution_id
        }
    )
    
    # Log step completion
    step_duration = (time.perf_counter() - step_start) * 1000
    log_step_complete(
        step.step_id,
        step.tool_name,
        tool_result["success"],
        step_duration
    )
    
    return {
        "step_id": step.step_id,
        "tool_name": step.tool_name,
        "success": tool_result["success"],
        "data": tool_result,
        "duration_ms": step_duration
    }


# ═══════════════════════════════════════════════════════════════════════════════
# RESULT BUILDERS
# ═══════════════════════════════════════════════════════════════════════════════

def _create_skipped_result() -> ExecutionResult:
    """Create result for skipped execution (impossible plan)"""
    return ExecutionResult(
        execution_status="skipped",
        step_results=[],
        executed_steps=0,
        metadata={"reason": "plan_impossible"}
    )


def _create_failed_result(
    step_results: list,
    executed_steps: int,
    failed_step: Step,
    error: Optional[str]
) -> ExecutionResult:
    """Create result for failed execution"""
    return ExecutionResult(
        execution_status="failed",
        step_results=step_results,
        executed_steps=executed_steps,
        metadata={
            "failed_step_id": failed_step.step_id,
            "failed_tool": failed_step.tool_name,
            "error": error or "Unknown error"
        }
    )