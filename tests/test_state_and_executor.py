"""
Unit and integration tests for state management, step resumption, and tool execution.
"""

import pytest
from core.state import DependencyState
from tools.schemas import Step, PlannerOutput
from core.executor import execute_plan
from app.runner import _is_non_retriable_failure


# ═══════════════════════════════════════════════════════════════════════════════
# DEPENDENCY STATE TESTS (BUG-02)
# ═══════════════════════════════════════════════════════════════════════════════

def test_dependency_state_resolves_standard_value():
    """Verify standard data.value resolution."""
    state = DependencyState()
    state.store(1, {"tool": "calculator", "success": True, "data": {"value": 42}})

    dependencies = [{"from_step": 1, "from_field": "data.value", "to_arg": "number"}]
    resolved = state.resolve_dependencies(
        tool_args={"operation": "print", "number": None},
        dependencies=dependencies
    )
    assert resolved["number"] == 42


def test_dependency_state_resolves_nested_paths():
    """Verify arbitrary nested dot notation (e.g. data.user.id)."""
    state = DependencyState()
    state.store(1, {
        "tool": "custom",
        "success": True,
        "data": {
            "metadata": {"count": 15, "nested": {"target": "hello"}}
        }
    })

    dependencies = [
        {"from_step": 1, "from_field": "data.metadata.count", "to_arg": "count"},
        {"from_step": 1, "from_field": "data.metadata.nested.target", "to_arg": "msg"}
    ]
    resolved = state.resolve_dependencies(
        tool_args={"count": None, "msg": None},
        dependencies=dependencies
    )
    assert resolved["count"] == 15
    assert resolved["msg"] == "hello"


def test_dependency_state_missing_field_raises_key_error():
    """Verify missing fields raise explicit KeyError."""
    state = DependencyState()
    state.store(1, {"tool": "calculator", "success": True, "data": {"value": 10}})

    dependencies = [{"from_step": 1, "from_field": "data.nonexistent", "to_arg": "target"}]
    with pytest.raises(KeyError, match="missing 'data.nonexistent'"):
        state.resolve_dependencies(
            tool_args={"target": None},
            dependencies=dependencies
        )


# ═══════════════════════════════════════════════════════════════════════════════
# STEP RESUMPTION TESTS (BUG-03)
# ═══════════════════════════════════════════════════════════════════════════════

def test_execute_plan_skips_already_completed_steps():
    """Verify execute_plan preserves existing state and doesn't re-execute step 1."""
    existing_state = DependencyState()
    # Step 1 was already run and produced "hello"
    existing_state.store(1, {
        "tool": "text_transform",
        "success": True,
        "data": {"value": "hello"}
    })
    existing_results = [{
        "step_id": 1,
        "tool_name": "text_transform",
        "success": True,
        "data": {"value": "hello"},
        "duration_ms": 1.0
    }]

    # Plan with 2 steps: Step 1 (already done) and Step 2 (depends on Step 1)
    plan = PlannerOutput(
        goal="Calculate sum",
        plan_status="possible",
        steps=[
            Step(
                step_id=1,
                instruction="Step 1",
                tool_name="text_transform",
                tool_args={"text": "hello", "operation": "lowercase"}
            ),
            Step(
                step_id=2,
                instruction="Step 2",
                tool_name="text_transform",
                tool_args={"text": None, "operation": "uppercase"},
                metadata={"dependencies": [{"from_step": 1, "from_field": "data.value", "to_arg": "text"}]}
            )
        ]
    )

    result = execute_plan(
        plan,
        execution_id="test_resume",
        existing_state=existing_state,
        existing_results=existing_results
    )

    assert result.execution_status == "completed"
    assert result.executed_steps == 2
    # Verify Step 2 received the value from Step 1 without Step 1 being recomputed
    step_2_result = [r for r in result.step_results if r["step_id"] == 2][0]
    assert step_2_result["success"] is True
    assert step_2_result["data"]["data"]["value"] == "HELLO"


# ═══════════════════════════════════════════════════════════════════════════════
# RUNNER RETRY CLASSIFICATION TESTS (BUG-01)
# ═══════════════════════════════════════════════════════════════════════════════

def test_runner_retry_classification():
    """Verify non-retriable vs retriable tool failure classification."""
    # 1. Deterministic tool failures should NEVER retry
    assert _is_non_retriable_failure({"success": False, "error": "division by zero"}, deterministic=True) is True

    # 2. Semantic errors (bad syntax, value error) should NOT retry
    assert _is_non_retriable_failure({"success": False, "error": "ValueError: invalid literal"}, deterministic=False) is True

    # 3. Transient errors (timeout, connection error, rate limit) SHOULD retry (returns False)
    assert _is_non_retriable_failure({"success": False, "error": "Connection timeout 503"}, deterministic=False) is False
    assert _is_non_retriable_failure({"success": False, "error": "rate limit exceeded"}, deterministic=False) is False