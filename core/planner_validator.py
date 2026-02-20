from typing import Dict, Any
from tools.registry import TOOL_REGISTRY
from pydantic import ValidationError


# =========================
# Exception
# =========================

class PlannerValidationError(Exception):
    pass


# =========================
# Failure Helper
# =========================

def _fail(category: str, message: str, step=None):
    error = {
        "category": category,
        "message": message,
        "step_id": step.step_id if step else None,
        "tool_name": step.tool_name if step else None,
    }
    raise PlannerValidationError(error)


# =========================
# Public Entry
# =========================

def validate_plan(plan, user_query: str) -> Dict[str, Any]:
    _validate_schema(plan)
    _validate_fail_reason(plan)
    _validate_tools(plan)
    _validate_dependencies(plan)
    _validate_no_cycles(plan)
    _validate_query_intent(plan, user_query)
    _validate_datetime_usage(plan, user_query)
    _validate_pipelines(plan)

    return {
        "valid": True,
        "normalized_plan": plan
    }


# =========================
# Schema Validation
# =========================

def _validate_schema(plan):
    if plan.plan_status not in {"possible", "impossible"}:
        _fail("SCHEMA_ERROR", "Invalid plan_status")

    if plan.plan_status == "impossible":
        if plan.steps:
            _fail("SCHEMA_ERROR", "Impossible plan must have empty steps")
        return

    if not isinstance(plan.steps, list):
        _fail("SCHEMA_ERROR", "steps must be a list")

    if not plan.steps:
        _fail("SCHEMA_ERROR", "Possible plan must contain steps")

    expected_id = 1
    seen_ids = set()

    for step in plan.steps:
        if step.step_id in seen_ids:
            _fail("SCHEMA_ERROR", f"Duplicate step_id {step.step_id}", step)

        if step.step_id != expected_id:
            _fail("SCHEMA_ERROR", "step_id must be sequential starting from 1", step)

        seen_ids.add(step.step_id)
        expected_id += 1

        if not isinstance(step.instruction, str) or not step.instruction.strip():
            _fail("SCHEMA_ERROR", "instruction must be a non-empty string", step)

        if not isinstance(step.tool_args, dict):
            _fail("SCHEMA_ERROR", "tool_args must be an object", step)

        if not isinstance(step.metadata, dict):
            _fail("SCHEMA_ERROR", "metadata must be an object", step)

        if step.step_id == 1 and step.metadata.get("dependencies"):
            _fail("SCHEMA_ERROR", "Step 1 must not have dependencies", step)


def _validate_fail_reason(plan):
    if plan.plan_status == "impossible":
        if not plan.fail_reason:
            _fail("SCHEMA_ERROR", "fail_reason required when plan_status is impossible")
    else:
        if getattr(plan, "fail_reason", None):
            _fail("SCHEMA_ERROR", "fail_reason forbidden when plan_status is possible")


# =========================
# Tool Validation
# =========================

def _validate_tools(plan):
    for step in plan.steps:
        tool_name = step.tool_name

        if tool_name not in TOOL_REGISTRY:
            _fail("TOOL_ERROR", f"Unknown tool: {tool_name}", step)

        _validate_no_inline_dependencies(step)

        # Schema-level validation
        schema = TOOL_REGISTRY[tool_name]["schema"]
        
        filtered_args = _filter_dependency_placeholders(step)
        
        try:
            parsed = schema.model_validate(filtered_args)
        except ValidationError as e:
            _fail("SCHEMA_ERROR", str(e), step)

        # Tool-specific rules
        if tool_name == "datetime":
            _validate_datetime(step)

        elif tool_name == "normalize_datetime":
            _validate_normalize_datetime(step)

        elif tool_name == "text_transform":
            _validate_text_transform(step)

        elif tool_name == "calculator":
            _validate_calculator(step)

        elif tool_name == "extract_from_text":
            _validate_extract_from_text(step)

        elif tool_name == "weather":
            _validate_weather(step)

        elif tool_name == "web_search":
            _validate_web_search(step)


def _validate_no_inline_dependencies(step):
    def contains_dependency(value):
        if isinstance(value, dict):
            if "from_step" in value or "from_field" in value:
                return True
            return any(contains_dependency(v) for v in value.values())
        if isinstance(value, list):
            return any(contains_dependency(v) for v in value)
        return False

    if contains_dependency(step.tool_args):
        _fail(
            "DEPENDENCY_ERROR",
            "Dependencies must not be embedded inside tool_args; "
            "use metadata.dependencies only",
            step
        )


# =========================
# Dependency Validation
# =========================

def _validate_dependencies(plan):
    step_ids = {s.step_id for s in plan.steps}

    for step in plan.steps:
        deps = step.metadata.get("dependencies", [])

        if not isinstance(deps, list):
            _fail("DEPENDENCY_ERROR", "dependencies must be a list", step)

        for dep in deps:
            # if dep.get("from_field") != "data":
            #     _fail("DEPENDENCY_ERROR", "from_field must be 'data'", step)
            
            if dep["from_field"] != "data.value":
                _fail(
                    "DEPENDENCY_ERROR",
                    "Dependencies must target 'data.value'",
                    step
                )

            from_step = dep.get("from_step")
            to_arg = dep.get("to_arg")

            if from_step not in step_ids:
                _fail("DEPENDENCY_ERROR", f"Dependency from missing step {from_step}", step)

            if from_step >= step.step_id:
                _fail("DEPENDENCY_ERROR", "Dependency must reference earlier step", step)

            if not _to_arg_root_exists(step.tool_args, to_arg):
                _fail("DEPENDENCY_ERROR", f"Invalid to_arg '{to_arg}'", step)


def _validate_no_cycles(plan):
    graph = {s.step_id: [] for s in plan.steps}

    for s in plan.steps:
        for d in s.metadata.get("dependencies", []):
            graph[s.step_id].append(d["from_step"])

    visited, stack = set(), set()

    def dfs(node):
        if node in stack:
            _fail("DEPENDENCY_ERROR", "Cyclic dependency detected")
        if node in visited:
            return
        stack.add(node)
        for parent in graph[node]:
            dfs(parent)
        stack.remove(node)
        visited.add(node)

    for step_id in graph:
        dfs(step_id)


# =========================
# Query Intent Validation
# =========================

def _validate_query_intent(plan, user_query: str):
    q = user_query.lower()
    
    # 1. Check for DATE DIFFERENCE patterns (highest priority)
    date_diff_indicators = [
        ("between" in q and "and" in q),
        ("from" in q and "to" in q),
        "until" in q,
        "since" in q
    ]
    
    # Check if query mentions specific dates
    has_specific_dates = any(month in q for month in [
        "january", "february", "march", "april", "may", "june",
        "july", "august", "september", "october", "november", "december"
    ]) or any(word in q for word in ["today", "tomorrow", "yesterday"])
    
    is_date_difference = any(date_diff_indicators) and has_specific_dates
    
    if is_date_difference:
        # Date difference queries SHOULD use datetime, NOT calculator
        has_calculator = any(s.tool_name == "calculator" for s in plan.steps)
        if has_calculator:
            # Find the calculator step
            calc_step = next((s for s in plan.steps if s.tool_name == "calculator"), None)
            _fail(
                "INTENT_ERROR",
                "Date difference queries should use datetime.date_diff, not calculator",
                calc_step
            )
        return  # Date difference queries are valid
    
    # 2. Check for PURE ARITHMETIC (no date context)
    arithmetic_markers = ["how many", "total", "calculate", "sum"]
    is_arithmetic = any(marker in q for marker in arithmetic_markers)
    
    date_words = [
        "date", "day", "week", "month", "year", "days", "weeks", "months", "years",
        "today", "tomorrow", "yesterday", 
        "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"
    ]
    has_date_words = any(word in q for word in date_words)
    
    # Pure arithmetic: "How many hours in 7 days?"
    if is_arithmetic and not has_date_words and not has_specific_dates:
        for step in plan.steps:
            if step.tool_name == "datetime":
                _fail(
                    "INTENT_ERROR",
                    "Pure arithmetic queries should use calculator, not datetime",
                    step
                )

# =========================
# Datetime Rules
# =========================

def _validate_datetime(step):
    """
    Validates datetime tool usage.
    
    Rules:
    1. operation="now" is always valid
    2. Literal strings "now", "today", "tomorrow" are FORBIDDEN in datetime value fields
    3. DateTime value fields can be None if provided via dependency
    4. Some fields (like days, unit) must be literals
    """
    op = step.tool_args.get("operation")
    
    # Rule: Check for forbidden literal strings in datetime VALUE fields only
    # (NOT in the "operation" field where "now" is valid)
    forbidden_literals = ["now", "today", "tomorrow", "yesterday"]
    datetime_value_fields = ["base_datetime", "start_datetime", "end_datetime"]
    
    for field in datetime_value_fields:
        value = step.tool_args.get(field)
        if isinstance(value, str) and value.lower() in forbidden_literals:
            _fail(
                "DATETIME_ERROR",
                f"Field '{field}' cannot accept literal string '{value}' - "
                f"use normalize_datetime or datetime(operation='now') first",
                step
            )
    
    # Validate operation-specific requirements
    if op == "now":
        # No additional parameters required
        pass
    
    elif op == "add_days":
        # days must be present (literal integer)
        if step.tool_args.get("days") is None:
            _fail("DATETIME_ERROR", "add_days operation requires 'days' parameter", step)
        
        # base_datetime must be present (literal or dependency)
        if (step.tool_args.get("base_datetime") is None and 
            not _has_dependency(step, "base_datetime")):
            _fail(
                "DATETIME_ERROR",
                "add_days operation requires 'base_datetime' (as literal or dependency)",
                step
            )
    
    elif op == "day_of_week":
        # base_datetime must be present (literal or dependency)
        if (step.tool_args.get("base_datetime") is None and 
            not _has_dependency(step, "base_datetime")):
            _fail(
                "DATETIME_ERROR",
                "day_of_week operation requires 'base_datetime' (as literal or dependency)",
                step
            )
    
    elif op == "date_diff":
        # Required fields for date_diff
        required_fields = {
            "start_datetime": "start datetime",
            "end_datetime": "end datetime",
            "unit": "time unit"
        }
        
        for field, description in required_fields.items():
            has_value = step.tool_args.get(field) is not None
            has_dependency = _has_dependency(step, field)
            
            if not has_value and not has_dependency:
                _fail(
                    "DATETIME_ERROR",
                    f"date_diff operation requires {description} (as literal or dependency)",
                    step
                )
    
    else:
        # Unknown operation
        _fail("DATETIME_ERROR", f"Unknown datetime operation: '{op}'", step)


def _validate_normalize_datetime(step):
    # text is required and must be a literal (can't come from dependency for this tool)
    text = step.tool_args.get("text")
    if not text:
        _fail("DATETIME_ERROR", "normalize_datetime requires text parameter", step)
    
    # reference_datetime can be None, literal, or from dependency
    # No validation needed - all cases are valid


def _validate_datetime_usage(plan, user_query: str):
    q = user_query.lower()
    
    # Check for conversion patterns (these should use calculator, not datetime)
    is_conversion = (
        ("convert" in q and any(unit in q for unit in ["hour", "minute", "second", "day", "week"])) or
        (q.count(" in ") == 1 and any(unit in q for unit in ["hours", "minutes", "seconds"]))
    )
    
    if is_conversion:
        for step in plan.steps:
            if step.tool_name == "datetime":
                _fail(
                    "DATETIME_ERROR",
                    "datetime forbidden for time unit conversion queries - use calculator",
                    step
                )


# =========================
# Pipeline Rules
# =========================

def _validate_pipelines(plan):
    tools = [s.tool_name for s in plan.steps]
    
    # Web search pipeline validation
    for i, step in enumerate(plan.steps):
        if step.tool_name == "web_search":
            # Check if this is the last step
            if i == len(plan.steps) - 1:
                # If web_search is the final step, it MUST be followed by combine_search_results
                # Exception: single-step plan where user just wants raw search results
                if len(plan.steps) > 1:
                    _fail(
                        "PIPELINE_ERROR",
                        "web_search must be followed by combine_search_results",
                        step
                    )
            else:
                # If there are more steps, next one MUST be combine_search_results
                next_step = plan.steps[i + 1]
                if next_step.tool_name != "combine_search_results":
                    _fail(
                        "PIPELINE_ERROR",
                        "web_search must be immediately followed by combine_search_results",
                        step
                    )
    
    # Weather + Calculator validation
    for i, step in enumerate(plan.steps):
        if step.tool_name == "weather":
            weather_step_id = step.step_id
            # Check all subsequent steps
            for future_step in plan.steps[i+1:]:
                if future_step.tool_name == "calculator":
                    # Check if calculator depends on weather
                    for dep in future_step.metadata.get("dependencies", []):
                        if dep.get("from_step") == weather_step_id:
                            _fail(
                                "PIPELINE_ERROR",
                                "weather results cannot be used in calculator",
                                future_step
                            )

# =========================
# Text Rules
# =========================



def _validate_text_transform(step):
    # operation must be present
    if "operation" not in step.tool_args:
        _fail("TEXT_ERROR", "text_transform requires operation parameter", step)
    
    # text can be None if it comes from dependency
    if step.tool_args.get("text") is None and not _has_dependency(step, "text"):
        _fail("TEXT_ERROR", "text_transform requires text (literal or dependency)", step)



# =========================
# Calculator Rules
# =========================


def _validate_calculator(step):
    # expression must be present
    if not step.tool_args.get("expression"):
        _fail("ARITHMETIC_ERROR", "calculator requires expression parameter", step)
    
    # CRITICAL: Calculator CANNOT accept dependencies
    # All values must be literals from the user query
    if step.metadata.get("dependencies"):
        _fail(
            "ARITHMETIC_ERROR", 
            "calculator cannot accept dependencies - all values must be literal numbers from the query",
            step
        )


# =========================
# Extract Rules
# =========================

def _validate_extract_from_text(step):
    # text can be None if it comes from dependency
    if step.tool_args.get("text") is None and not _has_dependency(step, "text"):
        _fail("EXTRACT_ERROR", "extract_from_text requires text (literal or dependency)", step)
    
    # extract_type is required
    if not step.tool_args.get("extract_type"):
        _fail("EXTRACT_ERROR", "extract_from_text requires extract_type", step)
    
    # If extracting datetime, reference is strongly recommended (but not strictly required)
    # You can make this a hard requirement if needed
    if step.tool_args.get("extract_type") == "datetime":
        if not step.tool_args.get("reference"):
            _fail(
                "EXTRACT_ERROR",
                "datetime extraction requires reference parameter for better accuracy",
                step
            )



# =========================
# Weather Rules
# =========================

def _validate_weather(step):
    # Validate locations
    locations = step.tool_args.get("locations", [])
    if not locations:
        _fail("WEATHER_ERROR", "weather requires locations list", step)
    if len(locations) > 5:
        _fail("WEATHER_ERROR", "weather accepts maximum 5 locations", step)
    
    # Validate days_ahead
    days_ahead = step.tool_args.get("days_ahead")
    if days_ahead is None:
        _fail("WEATHER_ERROR", "weather requires days_ahead parameter", step)
    
    # days_ahead MUST be a literal integer, NOT from dependency
    if not isinstance(days_ahead, int):
        _fail(
            "WEATHER_ERROR", 
            "days_ahead must be a literal integer (0-14), not from dependency",
            step
        )
    
    if not (0 <= days_ahead <= 14):
        _fail("WEATHER_ERROR", "days_ahead must be between 0 and 14", step)

# =========================
# Web Rules
# =========================

def _validate_web_search(step):
    # query must be present
    if not step.tool_args.get("query"):
        _fail("WEB_ERROR", "web_search requires query parameter", step)


# =========================
# Helpers
# =========================

def _has_dependency(step, to_arg):
    return any(d["to_arg"] == to_arg for d in step.metadata.get("dependencies", []))


def _to_arg_root_exists(tool_args: dict, to_arg: str) -> bool:
    root = to_arg.split(".", 1)[0]
    return root in tool_args

def _filter_dependency_placeholders(step):
    filtered = {}

    for arg, value in step.tool_args.items():
        if value is None and _has_dependency(step, arg):
            # Dependency will fill this later → skip plan-time validation
            continue
        filtered[arg] = value

    return filtered
