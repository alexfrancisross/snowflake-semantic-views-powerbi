"""
Metadata fetcher for Snowflake objects.
Retrieves database, schema, semantic view, view, and table listings and column metadata.

Performance: Uses @st.cache_data for query results with 5-minute TTL.
Parallel fetching: Uses ThreadPoolExecutor for batch metadata loading.
"""

from typing import Any, Literal
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError
import streamlit as st

from .logging_config import get_logger
from .host_builder import resolve_server_host
from .validation import escape_identifier, build_qualified_name

logger = get_logger(__name__)

# Cache TTL in seconds (30 minutes for database metadata - rarely changes)
CACHE_TTL_SECONDS = 1800

# Query timeout in seconds (prevent indefinite hanging on large tables)
# Metadata queries should complete quickly, cardinality analysis may take longer
DEFAULT_QUERY_TIMEOUT_SECONDS = 30
CARDINALITY_QUERY_TIMEOUT_SECONDS = 60

# Error codes/messages that indicate "no data" vs actual errors
# These are Snowflake-specific error patterns
PERMISSION_ERROR_PATTERNS = [
    "access denied",
    "insufficient privileges",
    "not authorized",
    "permission denied",
    "does not exist or not authorized",
]

NO_DATA_ERROR_PATTERNS = [
    "does not exist",
    "object does not exist",
    "cannot be found",
    "no results",
]


def classify_snowflake_error(error: Exception) -> tuple[str, str]:
    """
    Classify a Snowflake error to determine appropriate handling.

    Args:
        error: The exception to classify

    Returns:
        Tuple of (category, log_level) where:
        - category: "permission", "not_found", "timeout", "connection", "unknown"
        - log_level: "debug", "warning", "error"
    """
    error_str = str(error).lower()
    error_type = type(error).__name__

    # Check for permission errors - these are important to surface
    for pattern in PERMISSION_ERROR_PATTERNS:
        if pattern in error_str:
            return ("permission", "warning")

    # Check for "not found" errors - often normal (empty schema, etc.)
    for pattern in NO_DATA_ERROR_PATTERNS:
        if pattern in error_str:
            return ("not_found", "debug")

    # Check for timeout errors
    if "timeout" in error_str or "timed out" in error_str:
        return ("timeout", "warning")

    # Check for connection errors
    if any(x in error_str for x in ["connection", "network", "refused", "reset"]):
        return ("connection", "error")

    # Check exception type for more specific handling
    if "ProgrammingError" in error_type:
        # SQL syntax errors or invalid object references
        return ("sql_error", "warning")

    if "DatabaseError" in error_type or "OperationalError" in error_type:
        return ("database_error", "error")

    # Unknown error - log at warning level to make it visible
    return ("unknown", "warning")


def log_snowflake_error(
    error: Exception,
    operation: str,
    context: str = "",
    suppress: bool = True,
    show_in_ui: bool = False
) -> None:
    """
    Log a Snowflake error with appropriate level based on error type.

    Args:
        error: The exception to log
        operation: Description of the operation that failed
        context: Additional context (e.g., database.schema name)
        suppress: If False, re-raise the error after logging
        show_in_ui: If True, also surface a warning via st.warning() so the
            user sees why a list came back empty instead of it looking like
            "nothing exists" (previously fetchers swallowed all exceptions).
    """
    category, log_level = classify_snowflake_error(error)

    # Build the log message
    ctx_str = f" for {context}" if context else ""
    msg = f"{operation}{ctx_str}: {error}"

    # Add category hint for certain error types
    if category == "permission":
        msg = f"[Permission Error] {msg}"
    elif category == "timeout":
        msg = f"[Timeout] {msg}"
    elif category == "connection":
        msg = f"[Connection Error] {msg}"

    # Log at appropriate level
    if log_level == "debug":
        logger.debug(msg)
    elif log_level == "warning":
        logger.warning(msg)
    else:  # error
        logger.error(msg, exc_info=True)

    if show_in_ui and log_level != "debug":
        st.warning(msg)

    # Re-raise if not suppressing
    if not suppress:
        raise


def execute_with_timeout(
    session: Any,
    query: str,
    timeout_seconds: int = DEFAULT_QUERY_TIMEOUT_SECONDS,
    description: str = "query"
) -> list:
    """
    Execute a Snowflake query with a timeout to prevent indefinite hanging.

    Uses ThreadPoolExecutor to wrap the query execution with a timeout.
    If the query takes longer than the timeout, returns an empty list and logs a warning.

    Args:
        session: Snowpark session
        query: SQL query to execute
        timeout_seconds: Maximum time to wait for query completion
        description: Human-readable description for logging

    Returns:
        Query results as a list, or empty list on timeout/error
    """
    def run_query():
        return session.sql(query).collect()

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(run_query)
        try:
            return future.result(timeout=timeout_seconds)
        except FuturesTimeoutError:
            logger.warning(
                f"Query timeout ({timeout_seconds}s) for {description}: {query[:100]}..."
            )
            return []
        except Exception as e:
            logger.warning(f"Query error for {description}: {e}")
            return []

# Object types supported by the app
ObjectType = Literal["SEMANTIC_VIEW", "VIEW", "TABLE"]


def get_session_cache_key(session: Any) -> str:
    """Extract a cache key from the Snowflake session to ensure per-user caching.

    This is critical for multi-user environments where different users have
    different permissions and should see different database/schema lists.

    The result is cached in session_state to avoid repeated SQL queries.

    Args:
        session: Snowpark session

    Returns:
        A string that uniquely identifies this user's session for caching
    """
    # Check session_state cache first to avoid repeated SQL queries
    cache_key_state = "_snowflake_user_cache_key"
    if cache_key_state in st.session_state:
        return st.session_state[cache_key_state]

    try:
        # Get username and role from session - most reliable identifier
        # This ensures each user gets their own cache entries
        user_info = session.sql("SELECT CURRENT_USER() as user, CURRENT_ROLE() as role").collect()
        if user_info:
            user = user_info[0]["USER"]
            role = user_info[0]["ROLE"]
            key = f"{user}_{role}"
            st.session_state[cache_key_state] = key
            return key
    except Exception as e:
        log_snowflake_error(
            e,
            operation="Getting user info for cache key"
        )

    # Fallback: use session object id (less ideal but still per-session)
    fallback_key = f"session_{id(session)}"
    st.session_state[cache_key_state] = fallback_key
    return fallback_key


@dataclass
class ColumnMetadata:
    """Represents a column in a view or table."""
    name: str           # Display name in Power BI (e.g., "SHIP_MODE" or "SHIP_MODE_2" for duplicates)
    data_type: str
    kind: str  # "DIMENSION", "METRIC", "FACT", or "COLUMN" (for regular views/tables)
    description: str | None = None
    expression: str | None = None
    is_nullable: bool = True
    is_primary_key: bool = False
    source_column: str | None = None  # Original column name from Snowflake (for sourceColumn in PBIT)
    # Power BI-specific column properties (typically set via column_overrides in test config)
    is_hidden: bool = False  # isHidden in Power BI model
    data_category: str | None = None  # "Country", "City", "WebUrl", "ImageUrl", etc.
    format_string: str | None = None  # "$#,##0.00", "0.00%", custom formats


@dataclass
class TableMetadata:
    """Table-level metadata."""
    comment: str | None = None
    row_count: int | None = None


@dataclass
class ConstraintMetadata:
    """Represents a database constraint (PK, FK, UNIQUE)."""
    constraint_name: str
    constraint_type: str  # "PRIMARY KEY", "FOREIGN KEY", "UNIQUE"
    table_name: str
    columns: list[str]


@dataclass
class CardinalityInfo:
    """Cardinality information for a relationship."""
    from_cardinality: Literal["one", "many"]  # Cardinality on the FK (from) side
    to_cardinality: Literal["one", "many"]    # Cardinality on the PK (to) side
    detected_by: Literal["pk_fk", "data_analysis", "user_override"]
    confidence: float  # 0.0-1.0, higher is more confident
    avg_rows_per_key: float | None = None  # Average rows on "many" side per key


@dataclass
class FanOutRisk:
    """Fan-out risk assessment for a relationship."""
    risk_level: Literal["none", "low", "medium", "high", "critical"]
    reason: str
    affected_measures: list[str]  # Columns that could be inflated
    inflation_factor: float | None = None  # Estimated inflation (e.g., 3.64x)
    recommendation: str = ""


@dataclass
class RelationshipMetadata:
    """Represents a relationship between two tables.

    Supports both single-column and composite (multi-column) foreign keys.
    For composite keys, from_columns and to_columns contain multiple column names.

    Backwards compatible: accepts either string or list for column parameters.
    """
    name: str | None
    from_table: str
    from_columns: str | list[str]  # Accepts string or list for backwards compat
    to_table: str
    to_columns: str | list[str]  # Accepts string or list for backwards compat
    # Full qualified names for cross-schema relationships
    from_database: str | None = None
    from_schema: str | None = None
    to_database: str | None = None
    to_schema: str | None = None
    # Cardinality and fan-out risk (added for v3.1)
    cardinality: CardinalityInfo | None = None
    fan_out_risk: FanOutRisk | None = None

    def __post_init__(self):
        """Normalize column parameters to lists."""
        # Convert string to list for backwards compatibility
        if isinstance(self.from_columns, str):
            object.__setattr__(self, 'from_columns', [self.from_columns])
        if isinstance(self.to_columns, str):
            object.__setattr__(self, 'to_columns', [self.to_columns])

    # Backwards compatibility properties for single-column access
    @property
    def from_column(self) -> str:
        """Get first from column (backwards compatibility)."""
        cols = self.from_columns if isinstance(self.from_columns, list) else [self.from_columns]
        return cols[0] if cols else ""

    @property
    def to_column(self) -> str:
        """Get first to column (backwards compatibility)."""
        cols = self.to_columns if isinstance(self.to_columns, list) else [self.to_columns]
        return cols[0] if cols else ""

    @property
    def is_composite(self) -> bool:
        """Check if this is a composite (multi-column) relationship."""
        from_cols = self.from_columns if isinstance(self.from_columns, list) else [self.from_columns]
        to_cols = self.to_columns if isinstance(self.to_columns, list) else [self.to_columns]
        return len(from_cols) > 1 or len(to_cols) > 1

    @property
    def relationship_id(self) -> str:
        """Generate a unique ID for this relationship."""
        from_cols = self.from_columns if isinstance(self.from_columns, list) else [self.from_columns]
        to_cols = self.to_columns if isinstance(self.to_columns, list) else [self.to_columns]
        from_str = "_".join(from_cols)
        to_str = "_".join(to_cols)
        return f"{self.from_table}_{from_str}_{self.to_table}_{to_str}"


@dataclass
class SemanticViewMetadata:
    """Represents metadata for a semantic view, view, or table."""
    database: str
    schema: str
    view: str  # Name of the object (semantic view, view, or table)
    columns: list[ColumnMetadata]
    object_type: ObjectType = "SEMANTIC_VIEW"  # Type of the object
    table_metadata: TableMetadata | None = None  # Table-level comment and stats
    constraints: list[ConstraintMetadata] | None = None  # PK/FK/UNIQUE constraints
    relationships: list[RelationshipMetadata] | None = None  # FK relationships (outgoing)

    @property
    def full_name(self) -> str:
        """Returns the fully qualified object name."""
        return f"{self.database}.{self.schema}.{self.view}"

    @property
    def is_semantic_view(self) -> bool:
        """Check if this is a semantic view."""
        return self.object_type == "SEMANTIC_VIEW"


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def _get_databases_cached(_session: Any, user_cache_key: str) -> list[str]:
    """Internal cached function for get_databases.

    Args:
        _session: Snowpark session (underscore prefix for cache compatibility)
        user_cache_key: User-specific cache key for multi-user isolation

    Returns:
        List of database names
    """
    result = _session.sql("SHOW DATABASES").collect()
    return [row["name"] for row in result]


def get_databases(session: Any) -> list[str]:
    """
    Get list of databases accessible to the current user.

    Uses caching with user-specific keys to ensure multi-user isolation.
    Different users with different permissions see different database lists.

    Args:
        session: Snowpark session

    Returns:
        List of database names
    """
    user_key = get_session_cache_key(session)
    return _get_databases_cached(session, user_key)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def _get_schemas_cached(_session: Any, database: str, user_cache_key: str) -> list[str]:
    """Internal cached function for get_schemas.

    Args:
        _session: Snowpark session (underscore prefix for cache compatibility)
        database: Database name
        user_cache_key: User-specific cache key for multi-user isolation

    Returns:
        List of schema names (excluding INFORMATION_SCHEMA)
    """
    result = _session.sql(f'SHOW SCHEMAS IN DATABASE {escape_identifier(database)}').collect()
    return [
        row["name"]
        for row in result
        if row["name"] != "INFORMATION_SCHEMA"
    ]


def get_schemas(session: Any, database: str) -> list[str]:
    """
    Get list of schemas in a database.

    Uses caching with user-specific keys to ensure multi-user isolation.

    Args:
        session: Snowpark session
        database: Database name

    Returns:
        List of schema names (excluding INFORMATION_SCHEMA)
    """
    user_key = get_session_cache_key(session)
    return _get_schemas_cached(session, database, user_key)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def _get_semantic_views_cached(_session: Any, database: str, schema: str, user_cache_key: str) -> list[str]:
    """Internal cached function for get_semantic_views.

    Args:
        _session: Snowpark session (underscore prefix for cache compatibility)
        database: Database name
        schema: Schema name
        user_cache_key: User-specific cache key for multi-user isolation

    Returns:
        List of semantic view names
    """
    try:
        result = _session.sql(
            f'SHOW SEMANTIC VIEWS IN SCHEMA {escape_identifier(database)}.{escape_identifier(schema)}'
        ).collect()
        return [row["name"] for row in result]
    except Exception as e:
        # Use smart error classification to log at appropriate level
        log_snowflake_error(
            e,
            operation="Fetching semantic views",
            context=f"{database}.{schema}",
            show_in_ui=True
        )
        return []


def get_semantic_views(session: Any, database: str, schema: str) -> list[str]:
    """
    Get list of semantic views in a schema.

    Uses caching with user-specific keys to ensure multi-user isolation.

    Args:
        session: Snowpark session
        database: Database name
        schema: Schema name

    Returns:
        List of semantic view names
    """
    user_key = get_session_cache_key(session)
    return _get_semantic_views_cached(session, database, schema, user_key)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def _get_views_cached(_session: Any, database: str, schema: str, user_cache_key: str) -> list[str]:
    """Internal cached function for get_views.

    Args:
        _session: Snowpark session (underscore prefix for cache compatibility)
        database: Database name
        schema: Schema name
        user_cache_key: User-specific cache key for multi-user isolation

    Returns:
        List of view names
    """
    try:
        result = _session.sql(
            f'SHOW VIEWS IN SCHEMA {escape_identifier(database)}.{escape_identifier(schema)}'
        ).collect()
        return [row["name"] for row in result]
    except Exception as e:
        log_snowflake_error(
            e,
            operation="Fetching views",
            context=f"{database}.{schema}",
            show_in_ui=True
        )
        return []


def get_views(session: Any, database: str, schema: str) -> list[str]:
    """
    Get list of regular views in a schema.

    Uses caching with user-specific keys to ensure multi-user isolation.

    Args:
        session: Snowpark session
        database: Database name
        schema: Schema name

    Returns:
        List of view names
    """
    user_key = get_session_cache_key(session)
    return _get_views_cached(session, database, schema, user_key)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def _get_tables_cached(_session: Any, database: str, schema: str, user_cache_key: str) -> list[str]:
    """Internal cached function for get_tables.

    Args:
        _session: Snowpark session (underscore prefix for cache compatibility)
        database: Database name
        schema: Schema name
        user_cache_key: User-specific cache key for multi-user isolation

    Returns:
        List of table names
    """
    try:
        result = _session.sql(
            f'SHOW TABLES IN SCHEMA {escape_identifier(database)}.{escape_identifier(schema)}'
        ).collect()
        return [row["name"] for row in result]
    except Exception as e:
        log_snowflake_error(
            e,
            operation="Fetching tables",
            context=f"{database}.{schema}",
            show_in_ui=True
        )
        return []


def get_tables(session: Any, database: str, schema: str) -> list[str]:
    """
    Get list of tables in a schema.

    Uses caching with user-specific keys to ensure multi-user isolation.

    Args:
        session: Snowpark session
        database: Database name
        schema: Schema name

    Returns:
        List of table names
    """
    user_key = get_session_cache_key(session)
    return _get_tables_cached(session, database, schema, user_key)


def get_objects_by_type(
    session: Any,
    database: str,
    schema: str,
    object_type: ObjectType
) -> list[str]:
    """
    Get list of objects by type in a schema.

    Delegates to type-specific cached functions.

    Args:
        session: Snowpark session
        database: Database name
        schema: Schema name
        object_type: Type of object to fetch

    Returns:
        List of object names
    """
    if object_type == "SEMANTIC_VIEW":
        return get_semantic_views(session, database, schema)
    elif object_type == "VIEW":
        return get_views(session, database, schema)
    elif object_type == "TABLE":
        return get_tables(session, database, schema)
    else:
        return []


@dataclass
class ObjectInfo:
    """Represents a database object with its type."""
    name: str
    object_type: ObjectType


def get_all_objects(
    session: Any,
    database: str,
    schema: str
) -> list[ObjectInfo]:
    """
    Get all objects (tables, views, semantic views) in a schema.

    Reuses cached type-specific functions for better performance.

    Args:
        session: Snowpark session
        database: Database name
        schema: Schema name

    Returns:
        List of ObjectInfo with name and type
    """
    objects: list[ObjectInfo] = []
    seen_names: set[str] = set()

    # Get semantic views first (uses cached function)
    for name in get_semantic_views(session, database, schema):
        if name not in seen_names:
            objects.append(ObjectInfo(name=name, object_type="SEMANTIC_VIEW"))
            seen_names.add(name)

    # Get tables (uses cached function)
    for name in get_tables(session, database, schema):
        if name not in seen_names:
            objects.append(ObjectInfo(name=name, object_type="TABLE"))
            seen_names.add(name)

    # Get views - excluding semantic views already added (uses cached function)
    for name in get_views(session, database, schema):
        if name not in seen_names:
            objects.append(ObjectInfo(name=name, object_type="VIEW"))
            seen_names.add(name)

    # Sort by name for consistent display
    objects.sort(key=lambda x: x.name)

    return objects


def _row_to_dict(row: Any) -> dict:
    """
    Convert a Snowpark Row to a dictionary.

    Args:
        row: Snowpark Row object

    Returns:
        Dictionary with row data
    """
    # Try as_dict() method first (Snowpark Row)
    if hasattr(row, 'as_dict'):
        return row.as_dict()
    # Try asDict() method (alternative)
    if hasattr(row, 'asDict'):
        return row.asDict()
    # If it's already dict-like, return as-is
    if isinstance(row, dict):
        return row
    # Fallback: try to convert using column names
    try:
        return dict(row)
    except Exception as e:
        logger.debug(f"Failed to convert row to dict: {type(row).__name__} - {e}")
        return {}


def _get_row_value(row_dict: dict, key: str, default: Any = None) -> Any:
    """
    Get a value from a row dictionary, case-insensitive.

    Args:
        row_dict: Row as dictionary
        key: Key to look up
        default: Default value if key not found

    Returns:
        Value or default
    """
    # Try exact match first
    if key in row_dict:
        return row_dict[key]
    # Try uppercase
    if key.upper() in row_dict:
        return row_dict[key.upper()]
    # Try lowercase
    if key.lower() in row_dict:
        return row_dict[key.lower()]
    return default


def _escape_sql_string(value: str) -> str:
    """
    Escape a string value for safe use in SQL single-quoted strings.

    Prevents SQL injection by escaping single quotes (doubling them).

    Args:
        value: String value to escape

    Returns:
        Escaped string safe for SQL interpolation
    """
    if value is None:
        return ""
    return value.replace("'", "''")


def get_table_comment(
    session: Any,
    database: str,
    schema: str,
    table_name: str
) -> str | None:
    """
    Get the comment for a table or view from INFORMATION_SCHEMA.

    Args:
        session: Snowpark session
        database: Database name
        schema: Schema name
        table_name: Table or view name

    Returns:
        Comment string or None if not found
    """
    try:
        # Escape values to prevent SQL injection
        safe_schema = _escape_sql_string(schema)
        safe_table_name = _escape_sql_string(table_name)
        result = session.sql(f"""
            SELECT comment
            FROM {escape_identifier(database)}.INFORMATION_SCHEMA.TABLES
            WHERE table_schema = '{safe_schema}'
              AND table_name = '{safe_table_name}'
        """).collect()
        if result and len(result) > 0:
            row_dict = _row_to_dict(result[0])
            comment = _get_row_value(row_dict, "comment")
            # Return None if comment is empty string or "None"
            if comment and comment != "None" and comment.strip():
                return comment
    except Exception as e:
        log_snowflake_error(
            e,
            operation="Fetching table comment",
            context=f"{database}.{schema}.{table_name}"
        )
    return None


def get_semantic_view_comment(
    session: Any,
    database: str,
    schema: str,
    view_name: str
) -> str | None:
    """
    Get the comment for a semantic view from SHOW SEMANTIC VIEWS.

    Args:
        session: Snowpark session
        database: Database name
        schema: Schema name
        view_name: Semantic view name

    Returns:
        Comment string or None if not found
    """
    try:
        # Escape view_name to prevent SQL injection
        safe_view_name = _escape_sql_string(view_name)
        result = session.sql(
            f'SHOW SEMANTIC VIEWS LIKE \'{safe_view_name}\' IN SCHEMA '
            f'{escape_identifier(database)}.{escape_identifier(schema)}'
        ).collect()
        if result and len(result) > 0:
            row_dict = _row_to_dict(result[0])
            comment = _get_row_value(row_dict, "comment")
            # Return None if comment is empty string or "None"
            if comment and comment != "None" and comment.strip():
                return comment
    except Exception as e:
        log_snowflake_error(
            e,
            operation="Fetching semantic view comment",
            context=f"{database}.{schema}.{view_name}"
        )
    return None


def get_table_constraints(
    session: Any,
    database: str,
    schema: str,
    table_name: str
) -> list[ConstraintMetadata]:
    """
    Get constraints (PK, FK, UNIQUE) for a table.

    Args:
        session: Snowpark session
        database: Database name
        schema: Schema name
        table_name: Table name

    Returns:
        List of ConstraintMetadata objects
    """
    constraints = []

    try:
        # Escape values to prevent SQL injection
        safe_schema = _escape_sql_string(schema)
        safe_table_name = _escape_sql_string(table_name)
        # Get constraint info from INFORMATION_SCHEMA
        result = session.sql(f"""
            SELECT
                tc.constraint_name,
                tc.constraint_type,
                tc.table_name
            FROM {escape_identifier(database)}.INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
            WHERE tc.table_schema = '{safe_schema}'
              AND tc.table_name = '{safe_table_name}'
            ORDER BY tc.constraint_type, tc.constraint_name
        """).collect()

        for row in result:
            row_dict = _row_to_dict(row)
            constraint_name = _get_row_value(row_dict, "constraint_name", "")
            constraint_type = _get_row_value(row_dict, "constraint_type", "")

            # Get columns for this constraint
            columns = get_constraint_columns(
                session, database, schema, table_name, constraint_name
            )

            constraints.append(ConstraintMetadata(
                constraint_name=constraint_name,
                constraint_type=constraint_type,
                table_name=table_name,
                columns=columns
            ))

    except Exception as e:
        log_snowflake_error(
            e,
            operation="Fetching constraints",
            context=f"{database}.{schema}.{table_name}"
        )

    return constraints


def get_constraint_columns(
    session: Any,
    database: str,
    schema: str,
    table_name: str,
    constraint_name: str
) -> list[str]:
    """
    Get column names for a specific constraint.

    Args:
        session: Snowpark session
        database: Database name
        schema: Schema name
        table_name: Table name
        constraint_name: Constraint name

    Returns:
        List of column names in the constraint
    """
    columns = []

    try:
        # Try to get columns from SHOW PRIMARY KEYS or similar
        # Snowflake's INFORMATION_SCHEMA doesn't have KEY_COLUMN_USAGE for all constraints
        # Use SHOW commands instead
        if "PK_" in constraint_name or "PRIMARY" in constraint_name.upper():
            result = session.sql(
                f'SHOW PRIMARY KEYS IN TABLE {build_qualified_name(database, schema, table_name)}'
            ).collect()
            for row in result:
                row_dict = _row_to_dict(row)
                col_name = _get_row_value(row_dict, "column_name", "")
                if col_name:
                    columns.append(col_name)
        else:
            # For FK constraints, try SHOW IMPORTED KEYS
            result = session.sql(
                f'SHOW IMPORTED KEYS IN TABLE {build_qualified_name(database, schema, table_name)}'
            ).collect()
            for row in result:
                row_dict = _row_to_dict(row)
                fk_name = _get_row_value(row_dict, "fk_name", "")
                if fk_name == constraint_name:
                    col_name = _get_row_value(row_dict, "fk_column_name", "")
                    if col_name:
                        columns.append(col_name)

    except Exception as e:
        log_snowflake_error(
            e,
            operation="Fetching constraint columns",
            context=f"{table_name}.{constraint_name}"
        )

    return columns


def get_table_relationships(
    session: Any,
    database: str,
    schema: str,
    table_name: str
) -> list[RelationshipMetadata]:
    """
    Get foreign key relationships for a table (outgoing references).

    Supports composite (multi-column) foreign keys by grouping rows by fk_name.

    Args:
        session: Snowpark session
        database: Database name
        schema: Schema name
        table_name: Table name

    Returns:
        List of RelationshipMetadata objects for FK relationships
    """
    relationships = []

    try:
        # Use SHOW IMPORTED KEYS to get FK relationships
        result = session.sql(
            f'SHOW IMPORTED KEYS IN TABLE {build_qualified_name(database, schema, table_name)}'
        ).collect()

        # Group rows by fk_name to detect composite keys
        # Composite FKs have multiple rows sharing the same fk_name
        fk_groups: dict[str, list[dict]] = {}
        for row in result:
            row_dict = _row_to_dict(row)
            fk_name = _get_row_value(row_dict, "fk_name", "")
            if fk_name:
                if fk_name not in fk_groups:
                    fk_groups[fk_name] = []
                fk_groups[fk_name].append(row_dict)

        # Create relationships from grouped FKs
        for fk_name, rows in fk_groups.items():
            # Sort by key_sequence to maintain column order for composite keys
            rows.sort(key=lambda r: int(_get_row_value(r, "key_sequence", "1")))

            # Extract column lists
            from_columns = []
            to_columns = []
            pk_table = ""
            pk_schema = schema
            pk_database = database

            for row_dict in rows:
                fk_column = _get_row_value(row_dict, "fk_column_name", "")
                pk_column = _get_row_value(row_dict, "pk_column_name", "")
                if fk_column and pk_column:
                    from_columns.append(fk_column)
                    to_columns.append(pk_column)
                # Get table info from first row (same for all rows in composite)
                if not pk_table:
                    pk_table = _get_row_value(row_dict, "pk_table_name", "")
                    pk_schema = _get_row_value(row_dict, "pk_schema_name", schema)
                    pk_database = _get_row_value(row_dict, "pk_database_name", database)

            if from_columns and to_columns and pk_table:
                relationships.append(RelationshipMetadata(
                    name=fk_name,
                    from_table=table_name,
                    from_columns=from_columns,
                    to_table=pk_table,
                    to_columns=to_columns,
                    from_database=database,
                    from_schema=schema,
                    to_database=pk_database,
                    to_schema=pk_schema
                ))

    except Exception as e:
        log_snowflake_error(
            e,
            operation="Fetching relationships",
            context=f"{database}.{schema}.{table_name}"
        )

    return relationships


def _get_description_with_fallback(description: str | None, expression: str | None) -> str | None:
    """
    Get description, using expression as fallback if description is empty.

    Args:
        description: Explicit description from metadata
        expression: Expression/formula for the column

    Returns:
        Description string (or expression wrapped in brackets as fallback)
    """
    if description and description != "None" and description.strip():
        return description
    if expression and expression != "None" and expression.strip():
        return f"[Expression: {expression}]"
    return None


def _resolve_duplicate_column_names(columns: list[dict]) -> list[tuple[str, str]]:
    """
    Resolve duplicate column names by adding numeric suffixes.
    First occurrence keeps original name, subsequent get _2, _3, etc.

    This mimics how other Power BI connectors handle duplicate columns
    (e.g., CDM connector uses b2, f2, g2 suffixes).

    Args:
        columns: List of column dicts with 'name' key

    Returns:
        List of (display_name, source_column) tuples where:
        - display_name: Name shown in Power BI (with suffix if duplicate)
        - source_column: Original column name from Snowflake
    """
    # Count occurrences of each column name
    name_counts: dict[str, int] = {}
    for col in columns:
        name = col.get('name', '')
        name_counts[name] = name_counts.get(name, 0) + 1

    # Track which instance of each name we're on
    name_instance: dict[str, int] = {}
    results = []

    for col in columns:
        col_name = col.get('name', '')
        source_column = col_name  # Always original name

        if name_counts[col_name] > 1:
            # Duplicate name - add suffix
            instance = name_instance.get(col_name, 1)
            name_instance[col_name] = instance + 1
            # First occurrence keeps original, subsequent get _2, _3, etc.
            display_name = col_name if instance == 1 else f"{col_name}_{instance}"
        else:
            # Unique name - no suffix needed
            display_name = col_name

        results.append((display_name, source_column))

    return results


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def get_semantic_view_metadata(
    _session: Any,
    database: str,
    schema: str,
    view: str
) -> SemanticViewMetadata:
    """
    Get complete metadata for a semantic view including all columns.

    Uses original column names from Snowflake (no TABLE.COLUMN prefixing).
    Duplicate column names are resolved with numeric suffixes (_2, _3, etc.).
    The source_column field preserves the original name for DirectQuery compatibility.

    Uses caching to avoid repeated metadata queries (5-minute TTL).
    Note: _session prefix indicates non-hashable parameter.

    Args:
        _session: Snowpark session (underscore prefix for cache compatibility)
        database: Database name
        schema: Schema name
        view: Semantic view name

    Returns:
        SemanticViewMetadata with all column information
    """
    session = _session  # Alias for cleaner code below
    full_view = build_qualified_name(database, schema, view)

    # Collect raw column data (without TABLE.COLUMN prefixing)
    raw_columns: list[dict] = []

    # Get semantic view comment
    view_comment = get_semantic_view_comment(session, database, schema, view)
    table_meta = TableMetadata(comment=view_comment) if view_comment else None

    # Helper function to fetch and parse semantic columns
    def fetch_semantic_columns(query: str, kind: str, default_type: str) -> list[dict]:
        """Fetch semantic columns (dimensions/metrics/facts) and parse results."""
        columns = []
        try:
            # Use timeout to prevent hanging on metadata queries
            rows = execute_with_timeout(
                session,
                query,
                timeout_seconds=DEFAULT_QUERY_TIMEOUT_SECONDS,
                description=f"SHOW SEMANTIC {kind}S"
            )
            for row in rows:
                row_dict = _row_to_dict(row)
                raw_desc = _get_row_value(row_dict, "comment")
                expr = _get_row_value(row_dict, "expression")
                col_name = _get_row_value(row_dict, "name", "")
                columns.append({
                    'name': col_name,
                    'data_type': _get_row_value(row_dict, "data_type", default_type),
                    'kind': kind,
                    'description': _get_description_with_fallback(raw_desc, expr),
                    'expression': expr
                })
        except Exception as e:
            log_snowflake_error(
                e,
                operation=f"Fetching semantic {kind.lower()}s",
                context=full_view
            )
        return columns

    # Run all three SHOW SEMANTIC queries in parallel for better performance
    # This reduces latency from ~3 sequential queries to ~1 parallel batch
    with ThreadPoolExecutor(max_workers=3) as executor:
        future_dims = executor.submit(
            fetch_semantic_columns,
            f"SHOW SEMANTIC DIMENSIONS IN {full_view}",
            "DIMENSION",
            "VARCHAR"
        )
        future_metrics = executor.submit(
            fetch_semantic_columns,
            f"SHOW SEMANTIC METRICS IN {full_view}",
            "METRIC",
            "NUMBER"
        )
        future_facts = executor.submit(
            fetch_semantic_columns,
            f"SHOW SEMANTIC FACTS IN {full_view}",
            "FACT",
            "VARCHAR"
        )

        # Collect results (order: dimensions, metrics, facts)
        raw_columns.extend(future_dims.result())
        raw_columns.extend(future_metrics.result())
        raw_columns.extend(future_facts.result())

    # Resolve duplicate column names with numeric suffixes (_2, _3, etc.)
    resolved_names = _resolve_duplicate_column_names(raw_columns)

    # Create ColumnMetadata objects with display names and source columns
    columns = []
    for i, col_data in enumerate(raw_columns):
        display_name, source_column = resolved_names[i]
        columns.append(ColumnMetadata(
            name=display_name,
            data_type=col_data['data_type'],
            kind=col_data['kind'],
            description=col_data['description'],
            expression=col_data['expression'],
            source_column=source_column
        ))

    # Deduplicate by display name (same column can appear in multiple semantic kinds)
    seen_names: set[str] = set()
    unique_columns = []
    for col in columns:
        if col.name not in seen_names:
            seen_names.add(col.name)
            unique_columns.append(col)

    return SemanticViewMetadata(
        database=database,
        schema=schema,
        view=view,
        columns=unique_columns,
        object_type="SEMANTIC_VIEW",
        table_metadata=table_meta
    )


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def get_table_or_view_metadata(
    _session: Any,
    database: str,
    schema: str,
    object_name: str,
    object_type: ObjectType
) -> SemanticViewMetadata:
    """
    Get complete metadata for a regular view or table using DESCRIBE.

    Uses caching to avoid repeated metadata queries (5-minute TTL).
    Note: _session prefix indicates non-hashable parameter.

    Args:
        _session: Snowpark session (underscore prefix for cache compatibility)
        database: Database name
        schema: Schema name
        object_name: View or table name
        object_type: "VIEW" or "TABLE"

    Returns:
        SemanticViewMetadata with all column information
    """
    session = _session  # Alias for cleaner code below
    full_name = build_qualified_name(database, schema, object_name)
    columns = []

    # Get table/view comment
    table_comment = get_table_comment(session, database, schema, object_name)
    table_meta = TableMetadata(comment=table_comment) if table_comment else None

    try:
        # Use DESCRIBE to get column information
        result = session.sql(f"DESCRIBE TABLE {full_name}").collect()
        for row in result:
            row_dict = _row_to_dict(row)
            col_name = _get_row_value(row_dict, "name", "")
            col_type = _get_row_value(row_dict, "type", "VARCHAR")
            col_comment = _get_row_value(row_dict, "comment", None)
            col_nullable = _get_row_value(row_dict, "null?", "Y")
            col_primary_key = _get_row_value(row_dict, "primary key", "N")

            # Skip metadata columns if any
            if col_name.startswith("$"):
                continue

            # Clean up comment if it's "None" string
            if col_comment and (col_comment == "None" or not col_comment.strip()):
                col_comment = None

            columns.append(ColumnMetadata(
                name=col_name,
                data_type=col_type,
                kind="COLUMN",  # Regular columns don't have semantic kinds
                description=col_comment,
                expression=None,
                is_nullable=(col_nullable == "Y"),
                is_primary_key=(col_primary_key == "Y")
            ))
    except Exception as e:
        log_snowflake_error(
            e,
            operation=f"Describing {object_type.lower()}",
            context=f"{database}.{schema}.{object_name}"
        )

    # Fetch constraints and relationships for tables only (not views)
    constraints = None
    relationships = None
    if object_type == "TABLE":
        constraints = get_table_constraints(session, database, schema, object_name)
        relationships = get_table_relationships(session, database, schema, object_name)

    return SemanticViewMetadata(
        database=database,
        schema=schema,
        view=object_name,
        columns=columns,
        object_type=object_type,
        table_metadata=table_meta,
        constraints=constraints,
        relationships=relationships
    )


def get_view_metadata(
    session: Any,
    database: str,
    schema: str,
    view: str,
    object_type: ObjectType = "SEMANTIC_VIEW"
) -> SemanticViewMetadata:
    """
    Get complete metadata for any object type.

    Args:
        session: Snowpark session
        database: Database name
        schema: Schema name
        view: Object name (semantic view, view, or table)
        object_type: Type of object

    Returns:
        SemanticViewMetadata with all column information
    """
    if object_type == "SEMANTIC_VIEW":
        return get_semantic_view_metadata(session, database, schema, view)
    else:
        return get_table_or_view_metadata(session, database, schema, view, object_type)


def get_multiple_views_metadata(
    session: Any,
    database: str,
    schema: str,
    views: list[str],
    object_type: ObjectType = "SEMANTIC_VIEW"
) -> list[SemanticViewMetadata]:
    """
    Get metadata for multiple objects.

    Args:
        session: Snowpark session
        database: Database name
        schema: Schema name
        views: List of object names
        object_type: Type of objects

    Returns:
        List of SemanticViewMetadata objects
    """
    return [
        get_view_metadata(session, database, schema, view, object_type)
        for view in views
    ]


def get_metadata_batch_parallel(
    session: Any,
    objects: list[tuple[str, str, str, str]],
    max_workers: int = 8,
) -> list[SemanticViewMetadata]:
    """
    Get metadata for multiple objects in parallel using ThreadPoolExecutor.

    Args:
        session: Snowpark session
        objects: List of (database, schema, name, object_type) tuples
        max_workers: Maximum number of parallel workers (default 8)

    Returns:
        List of SemanticViewMetadata objects (in same order as input)
    """
    if not objects:
        return []

    # For small batches, sequential is fine
    if len(objects) <= 2:
        return [
            get_view_metadata(session, db, schema, name, obj_type)
            for db, schema, name, obj_type in objects
        ]

    results: dict[int, SemanticViewMetadata] = {}
    errors: dict[int, str] = {}

    def fetch_single(index: int, db: str, schema: str, name: str, obj_type: str):
        """Fetch metadata for a single object."""
        try:
            return index, get_view_metadata(session, db, schema, name, obj_type), None
        except Exception as e:
            return index, None, str(e)

    # Use ThreadPoolExecutor for parallel fetching
    with ThreadPoolExecutor(max_workers=min(max_workers, len(objects))) as executor:
        futures = {
            executor.submit(fetch_single, i, db, schema, name, obj_type): i
            for i, (db, schema, name, obj_type) in enumerate(objects)
        }

        for future in as_completed(futures):
            index, metadata, error = future.result()
            if metadata:
                results[index] = metadata
            elif error:
                errors[index] = error

    # Return results in original order, skipping errors
    ordered_results = []
    for i in range(len(objects)):
        if i in results:
            ordered_results.append(results[i])
        elif i in errors:
            # Log error but don't fail the whole batch
            db, schema, name, _ = objects[i]
            st.warning(f"Failed to load metadata for {db}.{schema}.{name}: {errors[i]}")

    return ordered_results


def get_connection_info(session: Any) -> dict[str, str]:
    """
    Get connection information from the session.

    Args:
        session: Snowpark session

    Returns:
        Dictionary with server and warehouse info
    """
    # Get current account, warehouse, and region (region is required to keep
    # legacy locator accounts from losing their region segment - issue #2)
    result = session.sql(
        "SELECT CURRENT_ACCOUNT() AS account, CURRENT_WAREHOUSE() AS warehouse, "
        "CURRENT_REGION() AS region"
    ).collect()

    account = result[0]["ACCOUNT"] if result else "unknown"
    # NOTE: CURRENT_WAREHOUSE() can return a non-empty result set with a NULL
    # value when no warehouse is active for the session - don't silently mask
    # that with a fake default; let the caller decide how to prompt the user.
    warehouse = result[0]["WAREHOUSE"] if result else None
    region = result[0]["REGION"] if result else None

    server = resolve_server_host(current_account=account, current_region=region)

    return {
        "server": server,
        "warehouse": warehouse,
        "warehouse_missing": warehouse is None,
        "account": account
    }


def detect_cardinality_from_constraints(
    session: Any,
    database: str,
    schema: str,
    from_table: str,
    from_column: str,
    to_table: str,
    to_column: str
) -> CardinalityInfo | None:
    """
    Detect cardinality from PK/FK constraints in Snowflake.

    The relationship goes from FK table (from) to PK table (to).
    - If to_column is PK -> to side is "one"
    - FK side (from) is typically "many" unless it's also a PK

    Args:
        session: Snowpark session
        database: Database name
        schema: Schema name
        from_table: Table with FK (many side typically)
        from_column: FK column name
        to_table: Table with PK (one side typically)
        to_column: PK column name

    Returns:
        CardinalityInfo or None if constraints can't be determined
    """
    try:
        # Check if to_column is a primary key
        pk_result = session.sql(
            f'SHOW PRIMARY KEYS IN TABLE {build_qualified_name(database, schema, to_table)}'
        ).collect()

        to_is_pk = any(
            _get_row_value(_row_to_dict(row), "column_name", "").upper() == to_column.upper()
            for row in pk_result
        )

        # Check if from_column is the SOLE primary key (would make it 1:1)
        # Important: Composite keys (like LINEITEM's L_ORDERKEY + L_LINENUMBER)
        # should NOT be treated as 1:1 just because the FK column is part of the PK
        from_pk_result = session.sql(
            f'SHOW PRIMARY KEYS IN TABLE {build_qualified_name(database, schema, from_table)}'
        ).collect()

        # Get all PK columns for the from_table
        from_pk_columns = [
            _get_row_value(_row_to_dict(row), "column_name", "").upper()
            for row in from_pk_result
        ]

        # Only consider it 1:1 if from_column is the ONLY PK column (not part of composite)
        from_is_sole_pk = (
            len(from_pk_columns) == 1 and
            from_column.upper() in from_pk_columns
        )

        if to_is_pk:
            # Standard FK relationship: many (from) to one (to)
            # Only "one" on from side if from_column is the SOLE primary key
            from_card = "one" if from_is_sole_pk else "many"
            return CardinalityInfo(
                from_cardinality=from_card,
                to_cardinality="one",
                detected_by="pk_fk",
                confidence=0.95 if from_is_sole_pk else 0.9
            )

        return None

    except Exception as e:
        log_snowflake_error(
            e,
            operation="Detecting cardinality from constraints",
            context=f"{from_table}->{to_table}"
        )
        return None


def analyze_cardinality_from_data(
    session: Any,
    database: str,
    schema: str,
    from_table: str,
    from_column: str,
    to_table: str,
    to_column: str,
    sample_size: int = 100000
) -> CardinalityInfo | None:
    """
    Fallback: Analyze actual data to determine cardinality using COUNT DISTINCT.

    Args:
        session: Snowpark session
        database: Database name
        schema: Schema name
        from_table: From table name
        from_column: From column name
        to_table: To table name
        to_column: To column name
        sample_size: Maximum rows to analyze

    Returns:
        CardinalityInfo based on data analysis, or None if analysis fails
    """
    try:
        # Analyze the join cardinality
        # IMPORTANT: Limit BOTH sides of the join to prevent scanning large tables
        query = f"""
            SELECT
                COUNT(*) as total_rows,
                COUNT(DISTINCT f.{escape_identifier(from_column)}) as distinct_from,
                COUNT(DISTINCT t.{escape_identifier(to_column)}) as distinct_to,
                COUNT(*) * 1.0 / NULLIF(COUNT(DISTINCT t.{escape_identifier(to_column)}), 0) as avg_rows_per_to
            FROM (SELECT {escape_identifier(from_column)} FROM {build_qualified_name(database, schema, from_table)} LIMIT {sample_size}) f
            JOIN (SELECT {escape_identifier(to_column)} FROM {build_qualified_name(database, schema, to_table)} LIMIT {sample_size}) t
                ON f.{escape_identifier(from_column)} = t.{escape_identifier(to_column)}
        """
        # Use timeout to prevent hanging on large table joins
        result = execute_with_timeout(
            session,
            query,
            timeout_seconds=CARDINALITY_QUERY_TIMEOUT_SECONDS,
            description=f"cardinality analysis {from_table}->{to_table}"
        )

        if not result:
            return None

        row_dict = _row_to_dict(result[0])
        total_rows = _get_row_value(row_dict, "total_rows", 0) or 0
        distinct_from = _get_row_value(row_dict, "distinct_from", 0) or 0
        distinct_to = _get_row_value(row_dict, "distinct_to", 0) or 0
        avg_rows_per_to = _get_row_value(row_dict, "avg_rows_per_to", 1.0) or 1.0

        if total_rows == 0:
            return None

        # Determine cardinality based on ratios
        from_ratio = total_rows / max(distinct_from, 1)
        to_ratio = total_rows / max(distinct_to, 1)

        # If avg rows per to_key > 1.5, it's likely many-to-one
        # If from_ratio is close to 1, from side is "one"
        from_card = "one" if from_ratio < 1.2 else "many"
        to_card = "one" if to_ratio < 1.2 else "many"

        # Calculate confidence based on sample size and distinctness
        confidence = min(0.8, 0.5 + (total_rows / sample_size) * 0.3)

        return CardinalityInfo(
            from_cardinality=from_card,
            to_cardinality=to_card,
            detected_by="data_analysis",
            confidence=confidence,
            avg_rows_per_key=float(avg_rows_per_to)
        )

    except Exception as e:
        log_snowflake_error(
            e,
            operation="Analyzing cardinality from data",
            context=f"{from_table}->{to_table}"
        )
        return None


def _calculate_avg_rows_per_key(
    session: Any,
    database: str,
    schema: str,
    from_table: str,
    from_column: str,
    to_table: str,
    to_column: str,
    sample_size: int = 100000
) -> float | None:
    """
    Calculate average rows per key for fan-out risk assessment.

    Returns the average number of rows in from_table per distinct key in to_table.
    This indicates how much "fan-out" occurs when joining from to_table to from_table.

    Args:
        session: Snowpark session
        database, schema: Database location
        from_table, from_column: FK table and column
        to_table, to_column: PK table and column
        sample_size: Maximum rows to analyze

    Returns:
        Average rows per key, or None if calculation fails
    """
    try:
        # IMPORTANT: Limit BOTH sides of the join to prevent scanning large tables
        query = f"""
            SELECT
                COUNT(*) * 1.0 / NULLIF(COUNT(DISTINCT t.{escape_identifier(to_column)}), 0) as avg_rows_per_key
            FROM (SELECT {escape_identifier(from_column)} FROM {build_qualified_name(database, schema, from_table)} LIMIT {sample_size}) f
            JOIN (SELECT {escape_identifier(to_column)} FROM {build_qualified_name(database, schema, to_table)} LIMIT {sample_size}) t
                ON f.{escape_identifier(from_column)} = t.{escape_identifier(to_column)}
        """
        # Use timeout to prevent hanging on large table joins
        result = execute_with_timeout(
            session,
            query,
            timeout_seconds=CARDINALITY_QUERY_TIMEOUT_SECONDS,
            description=f"avg_rows_per_key {from_table}->{to_table}"
        )
        if result:
            row_dict = _row_to_dict(result[0])
            avg = _get_row_value(row_dict, "avg_rows_per_key", None)
            if avg is not None:
                return float(avg)
        return None
    except Exception as e:
        log_snowflake_error(
            e,
            operation="Calculating avg_rows_per_key",
            context=f"{from_table}->{to_table}"
        )
        return None


def detect_cardinality(
    session: Any,
    database: str,
    schema: str,
    from_table: str,
    from_column: str,
    to_table: str,
    to_column: str
) -> CardinalityInfo:
    """
    Detect cardinality using constraints first, then data analysis as fallback.
    Always calculates avg_rows_per_key for fan-out risk assessment.

    Args:
        session: Snowpark session
        database: Database name
        schema: Schema name
        from_table: From table name
        from_column: From column name
        to_table: To table name
        to_column: To column name

    Returns:
        CardinalityInfo (defaults to many-to-one if detection fails)
    """
    # Try constraint-based detection first
    result = detect_cardinality_from_constraints(
        session, database, schema, from_table, from_column, to_table, to_column
    )
    if result:
        # Constraints found - now calculate avg_rows_per_key for fan-out risk
        avg_rows = _calculate_avg_rows_per_key(
            session, database, schema, from_table, from_column, to_table, to_column
        )
        return CardinalityInfo(
            from_cardinality=result.from_cardinality,
            to_cardinality=result.to_cardinality,
            detected_by=result.detected_by,
            confidence=result.confidence,
            avg_rows_per_key=avg_rows
        )

    # Fall back to data analysis (already calculates avg_rows_per_key)
    result = analyze_cardinality_from_data(
        session, database, schema, from_table, from_column, to_table, to_column
    )
    if result:
        return result

    # Default: assume many-to-one (most common FK pattern)
    return CardinalityInfo(
        from_cardinality="many",
        to_cardinality="one",
        detected_by="pk_fk",  # Default assumption
        confidence=0.5
    )


def assess_fan_out_risk(
    relationship: RelationshipMetadata,
    from_table_metadata: "SemanticViewMetadata",
    to_table_metadata: "SemanticViewMetadata"
) -> FanOutRisk:
    """
    Assess fan-out risk for a relationship.

    Fan-out occurs when:
    - Relationship is many-to-one (from is "many", to is "one")
    - Measures exist on the "one" side (to_table)
    - Grouping by attributes on the "many" side (from_table)

    Args:
        relationship: The relationship to assess
        from_table_metadata: Metadata for the from (FK/many) table
        to_table_metadata: Metadata for the to (PK/one) table

    Returns:
        FanOutRisk assessment
    """
    cardinality = relationship.cardinality

    # If no cardinality info, assume potential risk
    if not cardinality:
        return FanOutRisk(
            risk_level="medium",
            reason="Cardinality unknown - potential fan-out risk",
            affected_measures=[],
            recommendation="Configure cardinality to assess fan-out risk"
        )

    # Only many-to-one relationships have fan-out risk
    if cardinality.from_cardinality != "many" or cardinality.to_cardinality != "one":
        return FanOutRisk(
            risk_level="none",
            reason="No fan-out risk for this cardinality",
            affected_measures=[],
            recommendation=""
        )

    # Find numeric columns on the "one" side (potential measures)
    numeric_types = {"NUMBER", "DECIMAL", "NUMERIC", "INT", "INTEGER", "BIGINT",
                     "SMALLINT", "FLOAT", "DOUBLE", "REAL"}
    affected_measures = []

    for col in to_table_metadata.columns:
        # Check if column type is numeric (potential measure)
        col_type_upper = col.data_type.upper().split("(")[0]
        if col_type_upper in numeric_types:
            # Exclude likely key columns
            col_upper = col.name.upper()
            is_key_column = (
                col.is_primary_key or
                col_upper.endswith("_ID") or
                col_upper.endswith("ID") or
                col_upper.endswith("_KEY") or
                col_upper.endswith("KEY") or
                "KEY" in col_upper  # Catches O_CUSTKEY, L_ORDERKEY, etc.
            )
            if not is_key_column:
                affected_measures.append(col.name)

    if not affected_measures:
        return FanOutRisk(
            risk_level="low",
            reason="Many-to-one relationship but no obvious measures on 'one' side",
            affected_measures=[],
            recommendation="No action needed unless aggregating numeric columns from " +
                          f"{to_table_metadata.view}"
        )

    # Calculate risk level based on inflation factor
    inflation = cardinality.avg_rows_per_key or 1.0
    if inflation > 3.0:
        risk_level = "critical"
    elif inflation > 2.0:
        risk_level = "high"
    elif inflation > 1.5:
        risk_level = "medium"
    else:
        risk_level = "low"

    return FanOutRisk(
        risk_level=risk_level,
        reason=f"Aggregating {', '.join(affected_measures[:3])}{'...' if len(affected_measures) > 3 else ''} "
               f"from {to_table_metadata.view} grouped by {from_table_metadata.view} attributes "
               f"may inflate values by ~{inflation:.1f}x",
        affected_measures=affected_measures,
        inflation_factor=inflation,
        recommendation=f"Use Snowflake Semantic View to define metrics at {to_table_metadata.view} level"
    )


def enrich_relationship_with_cardinality(
    session: Any,
    relationship: RelationshipMetadata,
    from_table_metadata: "SemanticViewMetadata",
    to_table_metadata: "SemanticViewMetadata"
) -> RelationshipMetadata:
    """
    Enrich a relationship with cardinality and fan-out risk information.

    Args:
        session: Snowpark session
        relationship: The relationship to enrich
        from_table_metadata: Metadata for the from table
        to_table_metadata: Metadata for the to table

    Returns:
        RelationshipMetadata with cardinality and fan_out_risk populated
    """
    database = relationship.from_database or from_table_metadata.database
    schema = relationship.from_schema or from_table_metadata.schema

    # Detect cardinality
    cardinality = detect_cardinality(
        session, database, schema,
        relationship.from_table, relationship.from_column,
        relationship.to_table, relationship.to_column
    )
    relationship.cardinality = cardinality

    # Assess fan-out risk
    fan_out_risk = assess_fan_out_risk(
        relationship, from_table_metadata, to_table_metadata
    )
    relationship.fan_out_risk = fan_out_risk

    return relationship


def get_primary_key_columns(metadata: SemanticViewMetadata) -> list[str]:
    """
    Get list of primary key columns for a table.

    Args:
        metadata: Table metadata containing column definitions.

    Returns:
        List of PK column names. Empty if no PK detected.
    """
    return [col.name for col in metadata.columns if col.is_primary_key]


def has_composite_primary_key(metadata: SemanticViewMetadata) -> bool:
    """
    Check if table has a composite (multi-column) primary key.

    Tables like LINEITEM have composite PKs (L_ORDERKEY + L_LINENUMBER).
    This affects relationship cardinality - composite PKs require M:M
    relationships in bridge tables per Microsoft best practices.

    Args:
        metadata: Table metadata containing column definitions.

    Returns:
        True if table has 2+ PK columns (like LINEITEM).
    """
    pk_cols = get_primary_key_columns(metadata)
    return len(pk_cols) > 1


# ============================================================================
# Multi-Table Relationship Detection (3+ tables)
# ============================================================================

SchemaType = Literal["star", "chain", "unknown"]


def detect_all_relationships(
    session: Any,
    tables: list[SemanticViewMetadata]
) -> list[RelationshipMetadata]:
    """
    Find all FK relationships between a set of tables.

    Scans each table for IMPORTED KEYS (FKs) and filters to only include
    relationships where both tables are in the provided list.

    Args:
        session: Snowpark session
        tables: List of table metadata objects to find relationships between

    Returns:
        List of RelationshipMetadata objects for relationships between the tables
    """
    relationships: list[RelationshipMetadata] = []
    table_names = {t.view.upper() for t in tables}

    for table in tables:
        # Get all FK relationships from this table
        table_rels = get_table_relationships(
            session, table.database, table.schema, table.view
        )

        # Filter to only include relationships where to_table is in our list
        for rel in table_rels:
            if rel.to_table.upper() in table_names:
                # Enrich with cardinality info
                to_table_meta = next(
                    (t for t in tables if t.view.upper() == rel.to_table.upper()),
                    None
                )
                if to_table_meta:
                    enriched_rel = enrich_relationship_with_cardinality(
                        session, rel, table, to_table_meta
                    )
                    relationships.append(enriched_rel)
                else:
                    relationships.append(rel)

    return relationships


def detect_schema_type(
    tables: list[SemanticViewMetadata],
    relationships: list[RelationshipMetadata]
) -> SchemaType:
    """
    Detect whether the tables form a star schema or chain relationship pattern.

    Star Schema: One central table (fact) with multiple dimension tables
                 connected directly to it. Example:
                     DIM_A ← FACT -> DIM_B
                            ↓
                          DIM_C

    Chain: Tables connected in sequence. Example:
           LINEITEM -> ORDERS -> CUSTOMER

    Args:
        tables: List of table metadata objects
        relationships: Detected relationships between tables

    Returns:
        "star" if star schema pattern detected
        "chain" if chain relationship pattern detected
        "unknown" if pattern cannot be determined
    """
    if not relationships or len(tables) < 2:
        return "unknown"

    # Build adjacency info: count incoming and outgoing relationships per table
    outgoing_count: dict[str, int] = {}  # FK holder (many side)
    incoming_count: dict[str, int] = {}  # PK holder (one side)

    for table in tables:
        outgoing_count[table.view.upper()] = 0
        incoming_count[table.view.upper()] = 0

    for rel in relationships:
        from_upper = rel.from_table.upper()
        to_upper = rel.to_table.upper()
        if from_upper in outgoing_count:
            outgoing_count[from_upper] += 1
        if to_upper in incoming_count:
            incoming_count[to_upper] += 1

    # Star schema: one table has multiple outgoing FKs (fact -> dims)
    # OR one table receives multiple incoming FKs from different tables
    max_outgoing = max(outgoing_count.values()) if outgoing_count else 0
    max_incoming = max(incoming_count.values()) if incoming_count else 0

    # Chain: each table has at most 1 outgoing and 1 incoming (linear)
    is_chain = all(v <= 1 for v in outgoing_count.values()) and \
               all(v <= 1 for v in incoming_count.values())

    if max_outgoing >= 2 or max_incoming >= 2:
        return "star"
    elif is_chain and len(relationships) == len(tables) - 1:
        return "chain"
    else:
        return "unknown"


def identify_base_table(
    tables: list[SemanticViewMetadata],
    relationships: list[RelationshipMetadata]
) -> SemanticViewMetadata | None:
    """
    Identify the base/fact table (many-side) for granularity rules.

    The base table is where metrics should be defined. It's the table at
    the "many" end of relationships - typically the fact table that has
    FK references to dimension tables.

    Rules:
    1. Table with most outgoing FKs (holds FKs to other tables) = fact/base
    2. Table with composite PK is likely the fact table
    3. If tie, prefer table with more columns (facts have more detail)

    Args:
        tables: List of table metadata objects
        relationships: Detected relationships between tables

    Returns:
        The base table metadata, or None if cannot be determined
    """
    if not tables:
        return None

    if len(tables) == 1:
        return tables[0]

    # Count outgoing FKs per table (more FKs = more likely to be fact table)
    outgoing_fk_count: dict[str, int] = {t.view.upper(): 0 for t in tables}
    for rel in relationships:
        from_upper = rel.from_table.upper()
        if from_upper in outgoing_fk_count:
            outgoing_fk_count[from_upper] += 1

    # Score each table
    scores: dict[str, float] = {}
    for table in tables:
        name_upper = table.view.upper()
        score = 0.0

        # More outgoing FKs = more likely fact table
        score += outgoing_fk_count.get(name_upper, 0) * 10

        # Composite PK suggests fact table (e.g., LINEITEM has L_ORDERKEY + L_LINENUMBER)
        if has_composite_primary_key(table):
            score += 5

        # More columns suggests fact table (detail data)
        score += len(table.columns) * 0.1

        # Tables named with common fact patterns
        if any(pattern in name_upper for pattern in ["FACT", "LINEITEM", "SALES", "ORDER_ITEMS", "TRANSACTIONS"]):
            score += 3

        scores[name_upper] = score

    # Find table with highest score
    if not scores:
        return tables[0]

    best_table_name = max(scores, key=lambda k: scores[k])
    return next((t for t in tables if t.view.upper() == best_table_name), tables[0])


def get_tables_by_granularity(
    base_table: SemanticViewMetadata,
    tables: list[SemanticViewMetadata],
    relationships: list[RelationshipMetadata]
) -> dict[str, Literal["base", "dimension"]]:
    """
    Classify tables as base (fact) or dimension based on relationships to base table.

    Args:
        base_table: The identified base/fact table
        tables: All tables in the semantic view
        relationships: Relationships between tables

    Returns:
        Dict mapping table name (uppercase) to "base" or "dimension"
    """
    result: dict[str, Literal["base", "dimension"]] = {}
    base_upper = base_table.view.upper()

    for table in tables:
        name_upper = table.view.upper()
        if name_upper == base_upper:
            result[name_upper] = "base"
        else:
            result[name_upper] = "dimension"

    return result


def can_have_metrics(
    table: SemanticViewMetadata,
    base_table: SemanticViewMetadata,
    tables: list[SemanticViewMetadata],
    relationships: list[RelationshipMetadata]
) -> bool:
    """
    Check if a table can have metrics defined (must be base table or same granularity).

    Snowflake's granularity rules:
    - Metrics can only be on the base table (many-side / fact table)
    - Dimensions can be on any table
    - Facts can only be on the base table

    Args:
        table: The table to check
        base_table: The identified base/fact table
        tables: All tables in the semantic view
        relationships: Relationships between tables

    Returns:
        True if metrics are allowed on this table
    """
    return table.view.upper() == base_table.view.upper()


def can_have_facts(
    table: SemanticViewMetadata,
    base_table: SemanticViewMetadata,
    tables: list[SemanticViewMetadata],
    relationships: list[RelationshipMetadata]
) -> bool:
    """
    Check if a table can have facts defined (must be base table).

    Args:
        table: The table to check
        base_table: The identified base/fact table
        tables: All tables in the semantic view
        relationships: Relationships between tables

    Returns:
        True if facts are allowed on this table
    """
    return table.view.upper() == base_table.view.upper()


# ============================================================================
# Indirect Connection Detection (for Import Mode Warnings)
# ============================================================================

def detect_indirect_connections(
    base_table: str,
    tables: list[SemanticViewMetadata],
    relationships: list[RelationshipMetadata]
) -> dict[str, list[str]]:
    """
    Detect tables connected to base_table through intermediate tables.

    In Snowflake semantic views, dimensions must be at equal or lower granularity
    than the base (fact) table. Tables connected indirectly (through intermediate
    tables) often have higher granularity, which can cause errors in Import mode.

    Example: In TPCH, PARTSUPP connects to LINEITEM through PART and SUPPLIER,
    not directly. This causes granularity constraint violations in Import mode.

    Args:
        base_table: Name of the base/fact table
        tables: All tables in the semantic view
        relationships: Relationships between tables

    Returns:
        Dict of {table_name: [intermediate_tables]} for indirectly connected tables.
        Empty dict if all tables are directly connected.
    """
    from collections import defaultdict, deque

    # Build bidirectional adjacency graph from relationships
    graph: dict[str, set[str]] = defaultdict(set)
    for rel in relationships:
        graph[rel.from_table].add(rel.to_table)
        graph[rel.to_table].add(rel.from_table)

    table_names = {t.view for t in tables}
    indirect_tables: dict[str, list[str]] = {}

    for table in tables:
        if table.view.upper() == base_table.upper():
            continue

        # BFS to find shortest path from this table to base_table
        visited = {table.view}
        queue: deque[tuple[str, list[str]]] = deque([(table.view, [table.view])])
        found_path: list[str] | None = None

        while queue:
            current, path = queue.popleft()

            if current.upper() == base_table.upper():
                found_path = path
                break

            for neighbor in graph.get(current, set()):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

        # If path length > 2, it's indirect (source -> intermediate -> base)
        # path includes: [source, ...intermediates..., base]
        if found_path and len(found_path) > 2:
            # Intermediates are everything between source and base
            intermediates = [
                t for t in found_path[1:-1]
                if t in table_names
            ]
            if intermediates:
                indirect_tables[table.view] = intermediates

    return indirect_tables


# ============================================================================
# Multi-Path Relationship Detection (for Semantic View DDL Validation)
# ============================================================================

def detect_multi_path_conflicts(
    tables: list[SemanticViewMetadata],
    relationships: list[RelationshipMetadata],
    base_table: str,
) -> list[dict]:
    """
    Detect multi-path relationships that would cause Snowflake semantic view errors.

    Snowflake semantic views don't support ambiguous relationship paths. When there
    are two different paths from the base table to another table, Snowflake fails with:
    "Multi-path relationship between X and Y is not supported."

    Example conflict:
    - Direct path: LINEITEM -> SUPPLIER (via L_SUPPKEY)
    - Indirect path: LINEITEM -> PARTSUPP -> SUPPLIER (via composite key)

    Args:
        tables: All tables in the semantic view
        relationships: Relationships between tables
        base_table: Name of the base/fact table

    Returns:
        List of conflicts, each containing:
        {
            "target_table": "SUPPLIER",
            "paths": [
                ["LINEITEM", "SUPPLIER"],
                ["LINEITEM", "PARTSUPP", "SUPPLIER"]
            ],
            "conflicting_relationships": [rel1, rel2, ...]
        }
        Empty list if no conflicts detected.
    """
    from collections import defaultdict

    # Build BIDIRECTIONAL adjacency graph from relationships
    # Semantic views can traverse relationships in BOTH directions
    # (from fact to dim, or from dim to other dim via fact)
    graph: dict[str, set[str]] = defaultdict(set)
    for rel in relationships:
        from_upper = rel.from_table.upper()
        to_upper = rel.to_table.upper()
        graph[from_upper].add(to_upper)
        graph[to_upper].add(from_upper)

    base_upper = base_table.upper()
    conflicts: list[dict] = []

    def find_all_paths(start: str, end: str, max_depth: int = 10) -> list[list[str]]:
        """Find all paths between start and end using DFS with depth limit."""
        def dfs(current: str, path: list[str], depth: int) -> list[list[str]]:
            if depth > max_depth:
                return []
            if current == end:
                return [path]

            paths = []
            for neighbor in graph.get(current, set()):
                if neighbor not in path:
                    paths.extend(dfs(neighbor, path + [neighbor], depth + 1))
            return paths

        return dfs(start, [start], 0)

    # Get set of table names for filtering
    table_names_upper = {t.view.upper() for t in tables}

    # Check each table to see if there are multiple paths from base_table
    for table in tables:
        target_upper = table.view.upper()
        if target_upper == base_upper:
            continue

        # Find all paths from base table to this target table
        all_paths = find_all_paths(base_upper, target_upper)

        # Filter to only include paths that go through tables in our semantic view
        valid_paths = [
            path for path in all_paths
            if all(node in table_names_upper for node in path)
        ]

        if len(valid_paths) > 1:
            # Multiple paths detected - this is a conflict
            # Find relationships involved in these paths
            involved_relationships = []
            for rel in relationships:
                rel_from = rel.from_table.upper()
                rel_to = rel.to_table.upper()
                for path in valid_paths:
                    for i in range(len(path) - 1):
                        if (path[i] == rel_from and path[i+1] == rel_to) or \
                           (path[i] == rel_to and path[i+1] == rel_from):
                            if rel not in involved_relationships:
                                involved_relationships.append(rel)

            conflicts.append({
                "target_table": table.view,
                "paths": valid_paths,
                "conflicting_relationships": involved_relationships,
            })

    return conflicts
