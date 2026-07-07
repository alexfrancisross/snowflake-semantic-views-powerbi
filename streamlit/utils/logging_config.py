"""
Logging configuration for the Power BI Semantic Model Generator.

Provides structured logging with different levels for development vs production,
and integration with Streamlit's display for user-facing messages.

Usage:
    from logging_config import get_logger, log_user_action, log_error

    logger = get_logger(__name__)
    logger.info("Processing started")

    log_user_action("selected_object", {"db": "MYDB", "table": "MYTABLE"})
    log_error("Failed to load metadata", exc_info=True)
"""

import logging
import os
import sys
from datetime import datetime
from functools import wraps
from typing import Any, Callable, Optional
import streamlit as st

from .config import CONFIG


# =============================================================================
# LOGGING SETUP
# =============================================================================

# Log format for file/console output
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Map string log levels to logging constants
LOG_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def get_log_level() -> int:
    """Get log level from LOG_LEVEL environment variable.

    Reads the LOG_LEVEL environment variable and maps it to a logging level.
    Defaults to WARNING for production (minimal output).

    Usage:
        # Local development (verbose):
        LOG_LEVEL=DEBUG streamlit run streamlit_app.py

        # Local development (normal):
        LOG_LEVEL=INFO streamlit run streamlit_app.py

        # Production (minimal - default):
        streamlit run streamlit_app.py

    Returns:
        Logging level constant (e.g., logging.WARNING)
    """
    level_str = os.environ.get("LOG_LEVEL", "WARNING").upper()
    return LOG_LEVEL_MAP.get(level_str, logging.WARNING)


# Log level based on environment variable (defaults to WARNING for production)
DEFAULT_LOG_LEVEL = get_log_level()


def setup_logging(
    level: int = DEFAULT_LOG_LEVEL,
    log_to_console: bool = True,
    log_to_file: bool = False,
    log_file_path: str = None,
) -> logging.Logger:
    """Configure the root logger for the application.

    Args:
        level: Logging level (default INFO)
        log_to_console: Whether to log to stderr
        log_to_file: Whether to log to a file
        log_file_path: Path to log file (if log_to_file is True)

    Returns:
        Configured root logger
    """
    # Create formatter
    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    # Get root logger for our app
    root_logger = logging.getLogger("pbi_generator")
    root_logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # Console handler
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # File handler
    if log_to_file and log_file_path:
        file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger for a specific module.

    Args:
        name: Module name (usually __name__)

    Returns:
        Logger instance for the module
    """
    # Prefix with our app namespace
    if not name.startswith("pbi_generator"):
        name = f"pbi_generator.{name}"
    return logging.getLogger(name)


# Initialize logging on module import
_root_logger = setup_logging()


# =============================================================================
# STRUCTURED LOGGING HELPERS
# =============================================================================

def log_user_action(
    action: str,
    details: dict[str, Any] = None,
    logger: logging.Logger = None
) -> None:
    """Log a user action for analytics/debugging.

    Args:
        action: Action name (e.g., "selected_object", "generated_pbit")
        details: Additional details as key-value pairs
        logger: Logger to use (defaults to root)

    Example:
        log_user_action("selected_object", {
            "database": "MYDB",
            "schema": "PUBLIC",
            "object": "CUSTOMERS",
            "type": "TABLE"
        })
    """
    if logger is None:
        logger = get_logger("user_actions")

    detail_str = ""
    if details:
        detail_str = " | " + " | ".join(f"{k}={v}" for k, v in details.items())

    logger.info(f"ACTION: {action}{detail_str}")


def log_performance(
    operation: str,
    duration_ms: float,
    details: dict[str, Any] = None,
    logger: logging.Logger = None
) -> None:
    """Log performance metrics for an operation.

    Args:
        operation: Operation name
        duration_ms: Duration in milliseconds
        details: Additional details
        logger: Logger to use
    """
    if logger is None:
        logger = get_logger("performance")

    detail_str = ""
    if details:
        detail_str = " | " + " | ".join(f"{k}={v}" for k, v in details.items())

    logger.info(f"PERF: {operation} | {duration_ms:.2f}ms{detail_str}")


def log_error(
    message: str,
    error: Exception = None,
    details: dict[str, Any] = None,
    logger: logging.Logger = None,
    exc_info: bool = False
) -> None:
    """Log an error with structured details.

    Args:
        message: Error message
        error: Exception object (optional)
        details: Additional context
        logger: Logger to use
        exc_info: Whether to include traceback
    """
    if logger is None:
        logger = get_logger("errors")

    detail_str = ""
    if details:
        detail_str = " | " + " | ".join(f"{k}={v}" for k, v in details.items())

    error_str = ""
    if error:
        error_str = f" | error_type={type(error).__name__} | error_msg={str(error)}"

    logger.error(f"ERROR: {message}{error_str}{detail_str}", exc_info=exc_info)


# =============================================================================
# DECORATORS
# =============================================================================

def log_function_call(logger: logging.Logger = None):
    """Decorator to log function entry and exit.

    Args:
        logger: Logger to use

    Example:
        @log_function_call()
        def process_data(data):
            ...
    """
    def decorator(func: Callable) -> Callable:
        nonlocal logger
        if logger is None:
            logger = get_logger(func.__module__)

        @wraps(func)
        def wrapper(*args, **kwargs):
            func_name = func.__name__
            logger.debug(f"ENTER: {func_name}")
            try:
                result = func(*args, **kwargs)
                logger.debug(f"EXIT: {func_name}")
                return result
            except Exception as e:
                logger.error(f"EXCEPTION in {func_name}: {e}", exc_info=True)
                raise

        return wrapper
    return decorator


def timed(logger: logging.Logger = None):
    """Decorator to time function execution.

    Args:
        logger: Logger to use

    Example:
        @timed()
        def slow_operation():
            ...
    """
    def decorator(func: Callable) -> Callable:
        nonlocal logger
        if logger is None:
            logger = get_logger("performance")

        @wraps(func)
        def wrapper(*args, **kwargs):
            import time
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                duration = (time.perf_counter() - start) * 1000
                log_performance(func.__name__, duration, logger=logger)

        return wrapper
    return decorator


# =============================================================================
# STREAMLIT INTEGRATION
# =============================================================================

class StreamlitLogHandler(logging.Handler):
    """Custom log handler that displays messages in Streamlit.

    Only shows WARNING and above to avoid cluttering the UI.
    """

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record to Streamlit."""
        try:
            msg = self.format(record)

            if record.levelno >= logging.ERROR:
                st.error(f"Error: {record.getMessage()}")
            elif record.levelno >= logging.WARNING:
                st.warning(f"Warning: {record.getMessage()}")
            # INFO and DEBUG are not shown in UI

        except Exception:
            self.handleError(record)


def enable_streamlit_logging(level: int = logging.WARNING) -> None:
    """Enable logging to Streamlit UI.

    Only warnings and errors are shown to avoid UI clutter.

    Args:
        level: Minimum level to show in Streamlit (default WARNING)
    """
    handler = StreamlitLogHandler()
    handler.setLevel(level)

    root = logging.getLogger("pbi_generator")
    root.addHandler(handler)


# =============================================================================
# DEBUG HELPERS
# =============================================================================

def log_session_state(logger: logging.Logger = None) -> None:
    """Log current session state for debugging.

    Args:
        logger: Logger to use
    """
    if logger is None:
        logger = get_logger("debug")

    logger.debug("=== SESSION STATE ===")
    for key, value in st.session_state.items():
        # Truncate long values
        value_str = str(value)
        if len(value_str) > 100:
            value_str = value_str[:100] + "..."
        logger.debug(f"  {key}: {value_str}")
    logger.debug("=====================")


def log_app_state(logger: logging.Logger = None) -> None:
    """Log current AppState for debugging.

    Args:
        logger: Logger to use
    """
    if logger is None:
        logger = get_logger("debug")

    try:
        from session_manager import get_app_state
        state = get_app_state()

        logger.debug("=== APP STATE ===")
        logger.debug(f"  wizard_step: {state.wizard_step}")
        logger.debug(f"  selection.count: {state.selection.count}")
        logger.debug(f"  tree.loaded_schemas: {len(state.tree.loaded_schemas)} databases")
        logger.debug(f"  model.relationships: {len(state.model.selected_relationships)} tracked")
        logger.debug(f"  config.pbi_mode: {state.config.pbi_mode}")
        logger.debug(f"  config.dark_mode: {state.config.dark_mode}")
        logger.debug("=================")
    except Exception as e:
        logger.debug(f"Could not log app state: {e}")
