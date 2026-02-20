# ═══════════════════════════════════════════════════════════════════════════════
# DEPENDENCY STATE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════
from typing import Dict, Any, List, Optional
from infra.logger import logger_executor

class DependencyState:
    """
    Manages step outputs and resolves dependencies.
    
    Stores outputs from executed steps and resolves dependencies
    for subsequent steps by injecting stored values into tool arguments.
    
    Example:
        >>> state = DependencyState()
        >>> state.store(1, {"data": {"value": "2026-01-29"}})
        >>> 
        >>> dependencies = [{"from_step": 1, "from_field": "data.value", "to_arg": "base_datetime"}]
        >>> resolved = state.resolve_dependencies(
        ...     tool_args={"operation": "add_days", "days": 5, "base_datetime": None},
        ...     dependencies=dependencies
        ... )
        >>> resolved["base_datetime"]
        "2026-01-29"
    """
    
    def __init__(self):
        """Initialize empty state"""
        self._state: Dict[int, Any] = {}
        logger_executor.debug("DEPENDENCY_STATE | initialized")
    
    def store(self, step_id: int, output: Dict[str, Any]):
        """
        Store output from an executed step.
        
        Args:
            step_id: ID of the step
            output: Output from tool execution (complete tool_response dict)
        """
        self._state[step_id] = output
        
        logger_executor.debug(
            f"STATE_STORE | step_id={step_id} | "
            f"has_data={'data' in output}"
        )
    
    def resolve_dependencies(
        self,
        *,
        tool_args: dict,
        dependencies: List[Dict[str, Any]]
    ) -> dict:
        """
        Resolve dependencies by injecting stored values into tool arguments.
        
        Creates a copy of tool_args and replaces None values with
        outputs from previous steps based on dependency declarations.
        
        Args:
            tool_args: Original tool arguments (may contain None for deps)
            dependencies: List of dependency declarations
            
        Returns:
            Resolved tool arguments with dependencies filled in
            
        Raises:
            KeyError: If referenced step hasn't been executed
            KeyError: If referenced step output is missing expected data
            
        Example:
            dependencies = [
                {
                    "from_step": 1,
                    "from_field": "data.value",
                    "to_arg": "text"
                }
            ]
        """
        # Create copy to avoid modifying original
        resolved = dict(tool_args)
        
        for dep in dependencies:
            from_step = dep["from_step"]
            to_arg = dep["to_arg"]
            
            # Check if step was executed
            if from_step not in self._state:
                logger_executor.error(
                    f"RESOLVE_ERROR | from_step={from_step} | "
                    f"error=step not executed"
                )
                raise KeyError(f"Step {from_step} not executed or not found in state")
            
            # Extract value from stored output
            try:
                step_output = self._state[from_step]
                
                # Navigate to data.value
                if "data" not in step_output:
                    raise KeyError(f"Step {from_step} output missing 'data' field")
                
                if "value" not in step_output["data"]:
                    raise KeyError(f"Step {from_step} output missing 'data.value' field")
                
                value = step_output["data"]["value"]
                
                # Inject into resolved args
                resolved[to_arg] = value
                
                logger_executor.debug(
                    f"RESOLVE_DEP | from_step={from_step} | to_arg={to_arg} | "
                    f"value_type={type(value).__name__}"
                )
                
            except KeyError as e:
                logger_executor.error(
                    f"RESOLVE_ERROR | from_step={from_step} | error={str(e)}"
                )
                raise
        
        logger_executor.debug(
            f"RESOLVE_COMPLETE | resolved_args={len(resolved)} | "
            f"dependencies={len(dependencies)}"
        )
        
        return resolved
    
    def get_step_output(self, step_id: int) -> Optional[Dict[str, Any]]:
        """
        Get stored output for a step.
        
        Args:
            step_id: Step ID
            
        Returns:
            Stored output or None if not found
        """
        return self._state.get(step_id)
    
    def has_step(self, step_id: int) -> bool:
        """Check if step output is stored"""
        return step_id in self._state
    
    def clear(self):
        """Clear all stored state"""
        self._state.clear()
        logger_executor.debug("DEPENDENCY_STATE | cleared")
    
    def get_all_outputs(self) -> Dict[int, Any]:
        """Get all stored outputs (for debugging)"""
        return dict(self._state)

