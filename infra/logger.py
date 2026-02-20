"""
Centralized Logging Configuration

Provides structured logging for the AI agent system with:
- Component-specific loggers
- Consistent formatting
- Performance metrics
- Error tracking
- Debug capabilities
"""

import logging
import sys
from typing import Optional
from datetime import datetime


# ═══════════════════════════════════════════════════════════════════════════════
# LOGGER CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

def setup_logging(level: str = "INFO", log_file: Optional[str] = None):
    """
    Configure logging for the entire application.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path to write logs to
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Create formatters
    console_formatter = logging.Formatter(
        fmt="%(asctime)s | %(name)-15s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    file_formatter = logging.Formatter(
        fmt="%(asctime)s | %(name)s | %(levelname)s | %(filename)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(console_formatter)
    
    # Root logger configuration
    root_logger = logging.getLogger()
    
    # Prevent duplicate logs if setup_logging() is called again
    if root_logger.handlers:
        root_logger.handlers.clear()
    
    root_logger.setLevel(log_level)
    root_logger.addHandler(console_handler)
    
    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
    
    # Silence noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


# ═══════════════════════════════════════════════════════════════════════════════
# COMPONENT LOGGERS
# ═══════════════════════════════════════════════════════════════════════════════

# Initialize logging (call this once at app startup)
setup_logging(level="INFO")

# Component-specific loggers
logger_planner = logging.getLogger("agent.planner")
logger_validator = logging.getLogger("agent.validator")
logger_executor = logging.getLogger("agent.executor")
logger_tool = logging.getLogger("agent.tool")
logger_replanner = logging.getLogger("agent.replanner")
logger_api = logging.getLogger("agent.api")


# ═══════════════════════════════════════════════════════════════════════════════
# STRUCTURED LOGGING HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

class LogContext:
    """Helper for consistent structured logging"""
    
    @staticmethod
    def format_dict(data: dict) -> str:
        """Format dictionary for logging"""
        return " | ".join(f"{k}={v}" for k, v in data.items())
    
    @staticmethod
    def format_step(step_id: int, tool_name: str, **kwargs) -> str:
        """Format step information"""
        context = {"step_id": step_id, "tool": tool_name, **kwargs}
        return LogContext.format_dict(context)
    
    @staticmethod
    def format_timing(duration_seconds: float) -> str:
        """Format timing information"""
        return f"{duration_seconds * 1000:.2f}ms"


# ═══════════════════════════════════════════════════════════════════════════════
# LOGGING UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

def log_plan_start(user_query: str, request_id: Optional[str] = None):
    """Log the start of plan generation"""
    context = {"query": user_query[:100]}  # Truncate long queries
    if request_id:
        context["request_id"] = request_id
    logger_planner.info(f"PLAN_START | {LogContext.format_dict(context)}")


def log_plan_result(plan_status: str, num_steps: int, duration_ms: float):
    """Log plan generation result"""
    context = {
        "status": plan_status,
        "steps": num_steps,
        "duration_ms": f"{duration_ms:.2f}"
    }
    logger_planner.info(f"PLAN_COMPLETE | {LogContext.format_dict(context)}")


def log_validation_start(num_steps: int):
    """Log validation start"""
    logger_validator.info(f"VALIDATION_START | steps={num_steps}")


def log_validation_error(category: str, message: str, step_id: Optional[int] = None):
    """Log validation error"""
    context = {"category": category, "message": message}
    if step_id:
        context["step_id"] = step_id
    logger_validator.error(f"VALIDATION_ERROR | {LogContext.format_dict(context)}")


def log_execution_start(num_steps: int, execution_id: Optional[str] = None):
    """Log execution start"""
    context = {"steps": num_steps}
    if execution_id:
        context["execution_id"] = execution_id
    logger_executor.info(f"EXECUTION_START | {LogContext.format_dict(context)}")


def log_execution_complete(executed_steps: int, status: str, duration_seconds: float):
    """Log execution completion"""
    context = {
        "executed_steps": executed_steps,
        "status": status,
        "duration": LogContext.format_timing(duration_seconds)
    }
    logger_executor.info(f"EXECUTION_COMPLETE | {LogContext.format_dict(context)}")


def log_step_start(step_id: int, tool_name: str, instruction: str):
    """Log step execution start"""
    context = {
        "step_id": step_id,
        "tool": tool_name,
        "instruction": instruction[:80]  # Truncate long instructions
    }
    logger_executor.debug(f"STEP_START | {LogContext.format_dict(context)}")


def log_step_complete(step_id: int, tool_name: str, success: bool, duration_ms: float):
    """Log step execution completion"""
    context = {
        "step_id": step_id,
        "tool": tool_name,
        "success": success,
        "duration_ms": f"{duration_ms:.2f}"
    }
    level = logger_executor.info if success else logger_executor.error
    level(f"STEP_COMPLETE | {LogContext.format_dict(context)}")


def log_dependency_resolution(step_id: int, num_dependencies: int):
    """Log dependency resolution"""
    logger_executor.debug(f"RESOLVE_DEPS | step_id={step_id} | count={num_dependencies}")


def log_replan_trigger(reason: str, failed_step: int):
    """Log replanning trigger"""
    context = {"reason": reason, "failed_step": failed_step}
    logger_replanner.warning(f"REPLAN_TRIGGER | {LogContext.format_dict(context)}")


def log_replan_attempt(attempt: int, max_attempts: int):
    """Log replan attempt"""
    logger_replanner.info(f"REPLAN_ATTEMPT | attempt={attempt}/{max_attempts}")


# ═══════════════════════════════════════════════════════════════════════════════
# BACKWARD COMPATIBILITY
# ═══════════════════════════════════════════════════════════════════════════════

# For existing code that uses `logger` directly
logger = logger_tool  # Default to tool logger