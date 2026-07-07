"""
Comprehensive error handling for the Power BI Semantic Model Generator.

Provides custom exceptions, error display helpers, and error recovery patterns
for consistent error handling throughout the application.

Usage:
    from error_handling import (
        AppError,
        handle_error,
        show_error_with_help,
        safe_execute,
    )

    try:
        result = risky_operation()
    except SnowflakeConnectionError as e:
        handle_error(e)
"""

from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import Any, Callable, Optional, TypeVar
import traceback
import streamlit as st

from .logging_config import get_logger, log_error

logger = get_logger(__name__)

T = TypeVar("T")


# =============================================================================
# ERROR CATEGORIES
# =============================================================================

class ErrorCategory(Enum):
    """Categories of errors for consistent handling."""
    CONNECTION = "connection"
    AUTHENTICATION = "authentication"
    PERMISSION = "permission"
    NOT_FOUND = "not_found"
    VALIDATION = "validation"
    GENERATION = "generation"
    SNOWFLAKE = "snowflake"
    POWER_BI = "power_bi"
    INTERNAL = "internal"
    UNKNOWN = "unknown"


# =============================================================================
# CUSTOM EXCEPTIONS
# =============================================================================

@dataclass
class ErrorContext:
    """Context information for an error."""
    operation: str
    details: dict[str, Any] = None
    suggestion: str = None
    docs_url: str = None


class AppError(Exception):
    """Base exception for application errors.

    Provides structured error information including category, user-friendly
    message, technical details, and suggested actions.
    """

    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        context: ErrorContext = None,
        cause: Exception = None,
    ):
        super().__init__(message)
        self.message = message
        self.category = category
        self.context = context
        self.cause = cause

    def __str__(self) -> str:
        return self.message


class SnowflakeConnectionError(AppError):
    """Error connecting to Snowflake."""

    def __init__(self, message: str, context: ErrorContext = None, cause: Exception = None):
        super().__init__(
            message,
            category=ErrorCategory.CONNECTION,
            context=context or ErrorContext(
                operation="Snowflake Connection",
                suggestion="Check your connection settings in ~/.snowflake/connections.toml",
            ),
            cause=cause,
        )


class SnowflakeAuthenticationError(AppError):
    """Authentication failed with Snowflake."""

    def __init__(self, message: str, context: ErrorContext = None, cause: Exception = None):
        super().__init__(
            message,
            category=ErrorCategory.AUTHENTICATION,
            context=context or ErrorContext(
                operation="Snowflake Authentication",
                suggestion="Verify your username, password, or private key configuration",
            ),
            cause=cause,
        )


class SnowflakePermissionError(AppError):
    """Insufficient permissions in Snowflake."""

    def __init__(self, message: str, resource: str = None, cause: Exception = None):
        super().__init__(
            message,
            category=ErrorCategory.PERMISSION,
            context=ErrorContext(
                operation="Snowflake Access",
                details={"resource": resource} if resource else None,
                suggestion="Contact your Snowflake administrator to grant necessary permissions",
            ),
            cause=cause,
        )


class ObjectNotFoundError(AppError):
    """Requested object was not found."""

    def __init__(
        self,
        object_type: str,
        object_name: str,
        cause: Exception = None
    ):
        super().__init__(
            f"{object_type} '{object_name}' not found",
            category=ErrorCategory.NOT_FOUND,
            context=ErrorContext(
                operation=f"Fetch {object_type}",
                details={"object_type": object_type, "object_name": object_name},
                suggestion=f"Verify the {object_type.lower()} exists and you have access to it",
            ),
            cause=cause,
        )


class MetadataFetchError(AppError):
    """Error fetching metadata from Snowflake."""

    def __init__(
        self,
        message: str,
        database: str = None,
        schema: str = None,
        object_name: str = None,
        cause: Exception = None
    ):
        details = {}
        if database:
            details["database"] = database
        if schema:
            details["schema"] = schema
        if object_name:
            details["object"] = object_name

        super().__init__(
            message,
            category=ErrorCategory.SNOWFLAKE,
            context=ErrorContext(
                operation="Fetch Metadata",
                details=details if details else None,
                suggestion="Check that the object exists and you have SELECT permissions",
            ),
            cause=cause,
        )


class ValidationError(AppError):
    """Input validation failed."""

    def __init__(
        self,
        message: str,
        field: str = None,
        value: Any = None,
        cause: Exception = None
    ):
        details = {}
        if field:
            details["field"] = field
        if value is not None:
            details["value"] = str(value)[:50]  # Truncate

        super().__init__(
            message,
            category=ErrorCategory.VALIDATION,
            context=ErrorContext(
                operation="Input Validation",
                details=details if details else None,
            ),
            cause=cause,
        )


class GenerationError(AppError):
    """Error generating output (PBIT, TMDL, etc.)."""

    def __init__(
        self,
        message: str,
        output_type: str = None,
        cause: Exception = None
    ):
        super().__init__(
            message,
            category=ErrorCategory.GENERATION,
            context=ErrorContext(
                operation=f"Generate {output_type or 'Output'}",
                details={"output_type": output_type} if output_type else None,
                suggestion="Try generating a different format or check the error details",
            ),
            cause=cause,
        )


class PowerBIError(AppError):
    """Error related to Power BI operations."""

    def __init__(self, message: str, cause: Exception = None):
        super().__init__(
            message,
            category=ErrorCategory.POWER_BI,
            context=ErrorContext(
                operation="Power BI Operation",
                suggestion="Ensure Power BI Desktop is installed and accessible",
            ),
            cause=cause,
        )


# =============================================================================
# ERROR DISPLAY HELPERS
# =============================================================================

def show_error(
    message: str,
    details: str = None,
    suggestion: str = None,
    show_details: bool = True,
) -> None:
    """Display an error message in Streamlit with consistent styling.

    Args:
        message: Main error message
        details: Technical details (shown in expander)
        suggestion: Suggested action for the user
    """
    st.error(f"**Error:** {message}")

    if suggestion:
        st.info(f"**Suggestion:** {suggestion}")

    if details and show_details:
        with st.expander("Technical Details", expanded=False):
            st.code(details, language="text")


def show_error_with_help(
    error: AppError,
    show_traceback: bool = False,
) -> None:
    """Display an AppError with full context and help.

    Args:
        error: The AppError to display
        show_traceback: Whether to show the full traceback
    """
    # Main error message
    st.error(f"**{error.category.value.title()} Error:** {error.message}")

    # Context details
    if error.context:
        ctx = error.context

        if ctx.suggestion:
            st.info(f"**Suggestion:** {ctx.suggestion}")

        if ctx.details:
            with st.expander("Error Details", expanded=False):
                for key, value in ctx.details.items():
                    st.text(f"{key}: {value}")

        if ctx.docs_url:
            st.markdown(f"[View Documentation]({ctx.docs_url})")

    # Original exception
    if error.cause and show_traceback:
        with st.expander("Technical Details", expanded=False):
            st.code(traceback.format_exception(type(error.cause), error.cause, error.cause.__traceback__))


def show_warning(
    message: str,
    details: str = None,
) -> None:
    """Display a warning message in Streamlit.

    Args:
        message: Warning message
        details: Additional details
    """
    st.warning(f"**Warning:** {message}")

    if details:
        st.caption(details)


def show_recoverable_error(
    message: str,
    retry_label: str = "Retry",
    on_retry: Callable = None,
    suggestion: str = None,
) -> bool:
    """Display an error with a retry button.

    Args:
        message: Error message
        retry_label: Label for retry button
        on_retry: Callback function for retry
        suggestion: Suggested action

    Returns:
        True if retry button was clicked
    """
    st.error(f"**Error:** {message}")

    if suggestion:
        st.info(f"**Suggestion:** {suggestion}")

    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button(retry_label, type="primary"):
            if on_retry:
                on_retry()
            return True

    return False


# =============================================================================
# ERROR HANDLING UTILITIES
# =============================================================================

def handle_error(
    error: Exception,
    operation: str = None,
    show_in_ui: bool = True,
    reraise: bool = False,
    suggestion: str = None,
    details: str = None,
) -> None:
    """Handle an exception with logging and optional UI display.

    Args:
        error: The exception to handle
        operation: Description of the operation that failed
        show_in_ui: Whether to show error in Streamlit
        reraise: Whether to re-raise the exception after handling
        suggestion: Custom suggestion for the user (overrides default)
        details: Custom details to show (overrides traceback)
    """
    # Log the error
    log_error(
        message=operation or "Operation failed",
        error=error,
        exc_info=True,
    )

    # Display in UI
    if show_in_ui:
        if isinstance(error, AppError):
            show_error_with_help(error)
        else:
            show_error(
                message=str(error),
                details=details or traceback.format_exc(),
                suggestion=suggestion or "If this error persists, please contact support",
            )

    # Re-raise if requested
    if reraise:
        raise error


def safe_execute(
    func: Callable[..., T],
    *args,
    default: T = None,
    operation: str = None,
    show_error_ui: bool = True,
    **kwargs
) -> T:
    """Safely execute a function with error handling.

    Args:
        func: Function to execute
        *args: Positional arguments for func
        default: Default value to return on error
        operation: Description for error messages
        show_error_ui: Whether to show errors in Streamlit
        **kwargs: Keyword arguments for func

    Returns:
        Function result or default value on error
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        handle_error(e, operation=operation, show_in_ui=show_error_ui)
        return default


def error_boundary(
    operation: str = None,
    default: Any = None,
    show_error_ui: bool = True,
):
    """Decorator to add error handling to a function.

    Args:
        operation: Description for error messages
        default: Default value to return on error
        show_error_ui: Whether to show errors in Streamlit

    Example:
        @error_boundary(operation="Loading databases")
        def load_databases():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                handle_error(
                    e,
                    operation=operation or func.__name__,
                    show_in_ui=show_error_ui,
                )
                return default

        return wrapper
    return decorator


# =============================================================================
# SNOWFLAKE ERROR CONVERSION
# =============================================================================

def convert_snowflake_error(error: Exception, context: dict = None) -> AppError:
    """Convert a Snowflake exception to an appropriate AppError.

    Args:
        error: The Snowflake exception
        context: Additional context (database, schema, object, etc.)

    Returns:
        Appropriate AppError subclass
    """
    error_str = str(error).lower()
    context = context or {}

    # Authentication errors
    if any(x in error_str for x in ["authentication", "password", "login", "credentials"]):
        return SnowflakeAuthenticationError(
            "Authentication failed. Please check your credentials.",
            cause=error,
        )

    # Permission errors
    if any(x in error_str for x in ["permission", "access denied", "insufficient privileges", "not authorized"]):
        resource = context.get("object") or context.get("schema") or context.get("database")
        return SnowflakePermissionError(
            f"Insufficient permissions to access the requested resource.",
            resource=resource,
            cause=error,
        )

    # Not found errors
    if any(x in error_str for x in ["does not exist", "not found", "unknown"]):
        obj_type = context.get("object_type", "Object")
        obj_name = context.get("object") or context.get("schema") or context.get("database") or "Unknown"
        return ObjectNotFoundError(obj_type, obj_name, cause=error)

    # Connection errors
    if any(x in error_str for x in ["connection", "network", "timeout", "unreachable"]):
        return SnowflakeConnectionError(
            "Failed to connect to Snowflake. Check your network connection.",
            cause=error,
        )

    # Default to metadata fetch error
    return MetadataFetchError(
        str(error),
        database=context.get("database"),
        schema=context.get("schema"),
        object_name=context.get("object"),
        cause=error,
    )


# =============================================================================
# CONTEXT MANAGERS
# =============================================================================

class error_context:
    """Context manager for error handling with automatic conversion.

    Example:
        with error_context("Loading databases", database="MYDB"):
            result = session.sql("SHOW DATABASES").collect()
    """

    def __init__(
        self,
        operation: str,
        show_in_ui: bool = True,
        **context
    ):
        self.operation = operation
        self.show_in_ui = show_in_ui
        self.context = context

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val is not None:
            # Convert to AppError if needed
            if not isinstance(exc_val, AppError):
                exc_val = convert_snowflake_error(exc_val, self.context)

            handle_error(
                exc_val,
                operation=self.operation,
                show_in_ui=self.show_in_ui,
            )

            # Suppress the exception after handling
            return True

        return False
