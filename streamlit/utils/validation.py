"""
Input validation helpers for the Power BI Semantic Model Generator.

This module provides validation functions for user inputs, particularly
for Snowflake identifiers and SQL-related values, to prevent errors
and potential security issues.

Usage:
    from validation import (
        validate_identifier,
        validate_semantic_view_name,
        sanitize_for_display,
    )

    is_valid, error = validate_identifier("MY_TABLE")
    if not is_valid:
        st.error(error)
"""

import re
from dataclasses import dataclass
from typing import Optional

from .config import CONFIG


# =============================================================================
# VALIDATION RESULT
# =============================================================================

@dataclass
class ValidationResult:
    """Result of a validation check.

    Attributes:
        is_valid: Whether validation passed
        error_message: Error message if validation failed (None if valid)
        sanitized_value: Cleaned/sanitized value (None if invalid)
    """
    is_valid: bool
    error_message: Optional[str] = None
    sanitized_value: Optional[str] = None

    @staticmethod
    def success(value: str = None) -> "ValidationResult":
        """Create a successful validation result."""
        return ValidationResult(is_valid=True, sanitized_value=value)

    @staticmethod
    def failure(message: str) -> "ValidationResult":
        """Create a failed validation result."""
        return ValidationResult(is_valid=False, error_message=message)


# =============================================================================
# SNOWFLAKE IDENTIFIER VALIDATION
# =============================================================================

# Pattern for unquoted Snowflake identifiers
# Must start with letter or underscore, contain only alphanumeric, underscore, or dollar sign
UNQUOTED_IDENTIFIER_PATTERN = re.compile(r'^[A-Za-z_][A-Za-z0-9_$]*$')

# Pattern for quoted identifiers (allows most characters except quotes)
QUOTED_IDENTIFIER_PATTERN = re.compile(r'^[^"]+$')

# Reserved words that shouldn't be used as identifiers (subset)
SNOWFLAKE_RESERVED_WORDS = frozenset({
    "SELECT", "FROM", "WHERE", "AND", "OR", "NOT", "NULL", "TRUE", "FALSE",
    "ORDER", "BY", "GROUP", "HAVING", "LIMIT", "OFFSET", "JOIN", "LEFT",
    "RIGHT", "INNER", "OUTER", "FULL", "CROSS", "ON", "AS", "IN", "IS",
    "BETWEEN", "LIKE", "CASE", "WHEN", "THEN", "ELSE", "END", "CREATE",
    "ALTER", "DROP", "TABLE", "VIEW", "DATABASE", "SCHEMA", "INSERT",
    "UPDATE", "DELETE", "GRANT", "REVOKE", "ALL", "ANY", "SOME", "EXISTS",
    "UNION", "INTERSECT", "EXCEPT", "DISTINCT", "ASC", "DESC", "NULLS",
    "FIRST", "LAST", "FETCH", "NEXT", "ROWS", "ONLY", "PERCENT", "WITH",
})


def validate_identifier(
    value: str,
    allow_empty: bool = False,
    max_length: int = None,
    allow_reserved: bool = False,
) -> ValidationResult:
    """Validate a Snowflake identifier (table name, column name, etc.).

    Snowflake identifiers must:
    - Start with a letter (A-Z, a-z) or underscore (_)
    - Contain only letters, digits (0-9), underscores (_), or dollar signs ($)
    - Be no longer than 255 characters
    - Not be a reserved word (unless allow_reserved=True)

    Args:
        value: The identifier to validate
        allow_empty: Whether empty string is valid
        max_length: Maximum length (defaults to CONFIG.MAX_IDENTIFIER_LENGTH)
        allow_reserved: Whether to allow reserved words

    Returns:
        ValidationResult with validation status and error message if invalid
    """
    max_len = max_length or CONFIG.MAX_IDENTIFIER_LENGTH

    # Check for None
    if value is None:
        if allow_empty:
            return ValidationResult.success("")
        return ValidationResult.failure("Identifier cannot be None")

    # Strip whitespace
    value = value.strip()

    # Check empty
    if not value:
        if allow_empty:
            return ValidationResult.success("")
        return ValidationResult.failure("Identifier cannot be empty")

    # Check length
    if len(value) > max_len:
        return ValidationResult.failure(
            f"Identifier cannot exceed {max_len} characters (got {len(value)})"
        )

    # Check pattern
    if not UNQUOTED_IDENTIFIER_PATTERN.match(value):
        # Check for specific issues to give better error messages
        if value[0].isdigit():
            return ValidationResult.failure(
                "Identifier cannot start with a digit"
            )
        if " " in value:
            return ValidationResult.failure(
                "Identifier cannot contain spaces (use underscores instead)"
            )
        if any(c in value for c in "!@#%^&*()-+=[]{}|;:',.<>?/\\"):
            return ValidationResult.failure(
                "Identifier contains invalid characters. "
                "Use only letters, digits, underscores, and dollar signs."
            )
        return ValidationResult.failure(
            "Identifier must start with a letter or underscore and contain "
            "only letters, digits, underscores, or dollar signs"
        )

    # Check reserved words
    if not allow_reserved and value.upper() in SNOWFLAKE_RESERVED_WORDS:
        return ValidationResult.failure(
            f"'{value}' is a reserved word and cannot be used as an identifier"
        )

    return ValidationResult.success(value)


def validate_semantic_view_name(name: str) -> ValidationResult:
    """Validate a semantic view name.

    Semantic view names follow standard identifier rules.

    Args:
        name: The semantic view name to validate

    Returns:
        ValidationResult with validation status
    """
    result = validate_identifier(name, allow_empty=False, allow_reserved=False)

    if not result.is_valid:
        return result

    # Additional semantic view naming conventions
    if name.upper().startswith("SYS_"):
        return ValidationResult.failure(
            "Semantic view names cannot start with 'SYS_' (reserved prefix)"
        )

    return result


def validate_qualified_name(
    database: str,
    schema: str,
    name: str
) -> ValidationResult:
    """Validate a fully qualified object name (database.schema.object).

    Args:
        database: Database name
        schema: Schema name
        name: Object name

    Returns:
        ValidationResult for the complete qualified name
    """
    # Validate each component
    db_result = validate_identifier(database, allow_empty=False)
    if not db_result.is_valid:
        return ValidationResult.failure(f"Database name: {db_result.error_message}")

    schema_result = validate_identifier(schema, allow_empty=False)
    if not schema_result.is_valid:
        return ValidationResult.failure(f"Schema name: {schema_result.error_message}")

    name_result = validate_identifier(name, allow_empty=False)
    if not name_result.is_valid:
        return ValidationResult.failure(f"Object name: {name_result.error_message}")

    # Return combined qualified name
    qualified = f"{database}.{schema}.{name}"
    return ValidationResult.success(qualified)


# =============================================================================
# SQL VALUE VALIDATION
# =============================================================================

def validate_limit_value(value: str | int) -> ValidationResult:
    """Validate a LIMIT clause value.

    Args:
        value: The limit value (string or int)

    Returns:
        ValidationResult with validated integer value as string
    """
    try:
        num = int(value)
        if num < 0:
            return ValidationResult.failure("LIMIT cannot be negative")
        if num > 1_000_000_000:
            return ValidationResult.failure("LIMIT exceeds maximum allowed value")
        return ValidationResult.success(str(num))
    except (ValueError, TypeError):
        return ValidationResult.failure("LIMIT must be a valid integer")


def validate_aggregation(aggregation: str) -> ValidationResult:
    """Validate an aggregation function name.

    Args:
        aggregation: The aggregation function name

    Returns:
        ValidationResult with uppercase aggregation name
    """
    from config import SNOWFLAKE_AGGREGATIONS

    if not aggregation:
        return ValidationResult.failure("Aggregation cannot be empty")

    agg_upper = aggregation.strip().upper()

    if agg_upper not in SNOWFLAKE_AGGREGATIONS:
        valid_aggs = ", ".join(SNOWFLAKE_AGGREGATIONS)
        return ValidationResult.failure(
            f"'{aggregation}' is not a valid aggregation. "
            f"Supported: {valid_aggs}"
        )

    return ValidationResult.success(agg_upper)


# =============================================================================
# SANITIZATION FUNCTIONS
# =============================================================================

def sanitize_for_display(value: str, max_length: int = 100) -> str:
    """Sanitize a value for safe display in the UI.

    - Strips whitespace
    - Truncates to max length
    - Escapes HTML entities
    - Replaces control characters

    Args:
        value: The value to sanitize
        max_length: Maximum display length

    Returns:
        Sanitized string safe for display
    """
    if value is None:
        return ""

    # Strip whitespace
    value = str(value).strip()

    # Replace control characters
    value = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', value)

    # Truncate if needed
    if len(value) > max_length:
        value = value[:max_length - 3] + "..."

    return value


def escape_sql_string(value: str) -> str:
    """Escape a string for use in SQL.

    Doubles single quotes for SQL safety.

    Args:
        value: The string to escape

    Returns:
        SQL-safe escaped string
    """
    if value is None:
        return ""
    return str(value).replace("'", "''")


def escape_identifier(value: str) -> str:
    """Escape an identifier for use in SQL with double quotes.

    Args:
        value: The identifier to escape

    Returns:
        Double-quoted identifier safe for SQL
    """
    if value is None:
        return '""'
    # Double any existing double quotes
    escaped = str(value).replace('"', '""')
    return f'"{escaped}"'


def build_qualified_name(database: str, schema: str, name: str) -> str:
    """Build a fully qualified and properly escaped object name.

    Args:
        database: Database name
        schema: Schema name
        name: Object name

    Returns:
        Escaped fully qualified name: "DATABASE"."SCHEMA"."NAME"
    """
    return f'{escape_identifier(database)}.{escape_identifier(schema)}.{escape_identifier(name)}'


# =============================================================================
# UI VALIDATION HELPERS
# =============================================================================

def validate_and_show_error(
    value: str,
    validator_func,
    field_name: str = "Value",
    **validator_kwargs
) -> tuple[bool, str | None]:
    """Validate a value and optionally show error in Streamlit.

    Convenience function for form validation in Streamlit.

    Args:
        value: The value to validate
        validator_func: Validation function to call
        field_name: Name of the field for error messages
        **validator_kwargs: Additional arguments for validator

    Returns:
        Tuple of (is_valid, sanitized_value or None)

    Example:
        is_valid, clean_name = validate_and_show_error(
            user_input,
            validate_identifier,
            "Table name"
        )
        if not is_valid:
            return  # Error already shown
    """
    import streamlit as st

    result = validator_func(value, **validator_kwargs)

    if not result.is_valid:
        st.error(f"**{field_name}:** {result.error_message}")
        return False, None

    return True, result.sanitized_value


def create_identifier_input(
    label: str,
    key: str,
    default_value: str = "",
    help_text: str = None,
    validate_on_change: bool = True,
) -> tuple[str, bool]:
    """Create a Streamlit text input with identifier validation.

    Args:
        label: Input label
        key: Streamlit widget key
        default_value: Default value
        help_text: Help text to display
        validate_on_change: Whether to validate immediately

    Returns:
        Tuple of (current_value, is_valid)

    Example:
        name, is_valid = create_identifier_input(
            "Semantic View Name",
            "sv_name",
            default_value="MY_VIEW"
        )
    """
    import streamlit as st

    value = st.text_input(
        label,
        value=default_value,
        key=key,
        help=help_text or "Must start with letter/underscore, alphanumeric only"
    )

    if validate_on_change and value:
        result = validate_identifier(value)
        if not result.is_valid:
            st.caption(f":red[{result.error_message}]")
            return value, False

    return value, True
