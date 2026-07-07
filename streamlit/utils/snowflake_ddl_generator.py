"""
Snowflake DDL generator for fan-out fixes.

Generates DDL statements to create:
1. Semantic Views - Define metrics at the correct grain level (Snowflake-native)
2. Bridge Tables - Factless fact tables for M:M relationships (Microsoft best practice)

Also provides DAX measure suggestions for query-time fan-out handling.

Reference: https://learn.microsoft.com/en-us/power-bi/guidance/relationships-many-to-many
"""

from dataclasses import dataclass, field
from typing import Literal

from .logging_config import get_logger
from .metadata_fetcher import (
    RelationshipMetadata,
    SemanticViewMetadata,
    detect_multi_path_conflicts,
)

logger = get_logger(__name__)


# Supported Snowflake aggregation functions for semantic view metrics
# Note: PERCENTILE_CONT and LISTAGG require special syntax not supported here
SNOWFLAKE_AGGREGATIONS = [
    "SUM",
    "AVG",
    "COUNT",
    "MIN",
    "MAX",
    "COUNT_DISTINCT",
    "MEDIAN",
    "STDDEV",
    "VARIANCE",
]


def format_metric_expression(aggregation: str, column: str) -> str:
    """
    Format metric aggregation expression for Snowflake semantic views.

    Handles special cases like COUNT_DISTINCT which needs COUNT(DISTINCT col) syntax.

    Args:
        aggregation: The aggregation function (SUM, AVG, COUNT_DISTINCT, etc.)
        column: The column name to aggregate

    Returns:
        Properly formatted aggregation expression
    """
    agg_upper = aggregation.upper()
    if agg_upper == "COUNT_DISTINCT":
        return f"COUNT(DISTINCT {column})"
    else:
        return f"{agg_upper}({column})"


@dataclass
class SemanticColumnConfig:
    """Configuration for a column in a semantic view."""
    source_column: str          # Original column name from table
    semantic_name: str          # Name in the semantic view (can be customized)
    kind: Literal["DIMENSION", "METRIC", "FACT"]  # Column kind
    data_type: str              # Data type from source
    aggregation: str | None = None     # Aggregation function for metrics (SUM, AVG, etc.)
    description: str | None = None     # Column description (user override or from metadata)
    table_alias: str | None = None     # Table alias for multi-table semantic views
    requires_coalesce: bool = False    # Whether to wrap in COALESCE (for nullable FK in self-ref joins)
    coalesce_default: str | None = None  # Default value for COALESCE (e.g., "'(No Manager)'")


@dataclass
class DDLResult:
    """Result of DDL generation."""
    ddl: str                    # The generated DDL statement
    object_name: str            # Fully qualified name of the object
    object_type: str            # "SEMANTIC_VIEW" | "TABLE" | "VIEW"
    description: str            # Human-readable description


# Common alias-to-role mappings for semantic naming
ALIAS_ROLE_MAPPINGS = {
    "MGR": "MANAGER",
    "MANAGER": "MANAGER",
    "EMP": "EMPLOYEE",
    "EMPLOYEE": "EMPLOYEE",
    "PARENT": "PARENT",
    "CHILD": "CHILD",
    "SRC": "SOURCE",
    "SOURCE": "SOURCE",
    "TGT": "TARGET",
    "TARGET": "TARGET",
    "DIM": "",  # Don't add prefix for generic DIM suffix
    "FACT": "",  # Don't add prefix for generic FACT suffix
}


def detect_duplicate_dimensions(
    configs: list[SemanticColumnConfig],
) -> dict[str, list[tuple[int, SemanticColumnConfig]]]:
    """
    Detect duplicate dimension names across configs.

    This is critical for self-referential tables where the same base table
    appears multiple times with different aliases (e.g., EMP and MGR both
    referencing EMPLOYEE table, both having EMP_NAME column).

    Args:
        configs: List of column configurations

    Returns:
        Dict mapping duplicate semantic_name to list of (index, config) tuples.
        Only includes names that appear more than once with kind="DIMENSION".

    Example:
        >>> configs = [
        ...     SemanticColumnConfig("EMP_NAME", "EMP_NAME", "DIMENSION", "VARCHAR", table_alias="EMP"),
        ...     SemanticColumnConfig("EMP_NAME", "EMP_NAME", "DIMENSION", "VARCHAR", table_alias="MGR"),
        ... ]
        >>> detect_duplicate_dimensions(configs)
        {"EMP_NAME": [(0, config1), (1, config2)]}
    """
    name_to_configs: dict[str, list[tuple[int, SemanticColumnConfig]]] = {}

    for idx, cfg in enumerate(configs):
        if cfg.kind == "DIMENSION":
            name_upper = cfg.semantic_name.upper()
            if name_upper not in name_to_configs:
                name_to_configs[name_upper] = []
            name_to_configs[name_upper].append((idx, cfg))

    # Return only duplicates (more than one occurrence)
    return {k: v for k, v in name_to_configs.items() if len(v) > 1}


def resolve_duplicate_dimension_names(
    configs: list[SemanticColumnConfig],
    relationships: list[RelationshipMetadata] | None = None,
) -> tuple[list[SemanticColumnConfig], list[str]]:
    """
    Resolve duplicate dimension names by auto-renaming based on table alias.

    For self-referential tables (same table with different aliases), creates
    unique dimension names using semantic role prefixes:
    - EMP.EMP_NAME -> EMPLOYEE_NAME (if EMP alias, uses EMPLOYEE role)
    - MGR.EMP_NAME -> MANAGER_NAME (if MGR alias, uses MANAGER role)

    Args:
        configs: List of column configurations (modified in place)
        relationships: Optional relationships to infer role from relationship names

    Returns:
        Tuple of (modified configs, list of warning messages about renames)

    Example:
        >>> configs = [
        ...     SemanticColumnConfig("EMP_NAME", "EMP_NAME", "DIMENSION", "VARCHAR", table_alias="EMP"),
        ...     SemanticColumnConfig("EMP_NAME", "EMP_NAME", "DIMENSION", "VARCHAR", table_alias="MGR"),
        ... ]
        >>> resolved, warnings = resolve_duplicate_dimension_names(configs)
        >>> resolved[0].semantic_name
        'EMPLOYEE_NAME'
        >>> resolved[1].semantic_name
        'MANAGER_NAME'
    """
    duplicates = detect_duplicate_dimensions(configs)
    warnings = []

    if not duplicates:
        return configs, warnings

    # Track renamed columns for warning messages
    renames = []

    for dup_name, occurrences in duplicates.items():
        # For each set of duplicates, generate unique names
        for i, (idx, cfg) in enumerate(occurrences):
            alias = (cfg.table_alias or "").upper()

            # Try to find a semantic role from the alias
            role = None

            # Check direct alias mapping
            if alias in ALIAS_ROLE_MAPPINGS:
                role = ALIAS_ROLE_MAPPINGS[alias]
            else:
                # Check if alias contains a known role pattern
                for pattern, mapped_role in ALIAS_ROLE_MAPPINGS.items():
                    if pattern in alias and mapped_role:  # Skip empty mappings
                        role = mapped_role
                        break

            # If no role found, check relationship names for hints
            if not role and relationships:
                for rel in relationships:
                    rel_name_upper = rel.relationship_name.upper() if hasattr(rel, 'relationship_name') else ""
                    # Look for patterns like "EMP_TO_MGR" or "TO_MANAGER"
                    if f"TO_{alias}" in rel_name_upper or f"{alias}_TO" in rel_name_upper:
                        # Use alias as role if found in relationship name
                        role = alias.replace("_DIM", "").replace("_FACT", "")
                        break

            # Generate new name
            if role:
                # Use role as prefix: MANAGER_NAME, EMPLOYEE_NAME
                base_col = cfg.source_column.upper()
                # Remove common suffixes that might be duplicated
                for suffix in ["_NAME", "_ID", "_DATE", "_CODE"]:
                    if base_col.endswith(suffix):
                        new_name = f"{role}{suffix}"
                        break
                else:
                    new_name = f"{role}_{base_col}"
            elif alias:
                # Fallback: use alias as prefix
                alias_clean = alias.replace("_DIM", "").replace("_FACT", "")
                new_name = f"{alias_clean}_{cfg.source_column.upper()}"
            else:
                # Last resort: add numeric suffix
                new_name = f"{cfg.semantic_name.upper()}_{i+1}"

            # Update the config
            old_name = cfg.semantic_name
            cfg.semantic_name = new_name
            renames.append((old_name, new_name, alias))

    if renames:
        warnings.append(
            f"Duplicate dimension names detected and auto-renamed for self-referential table support:\n"
            + "\n".join(f"  - {old} (alias: {alias}) -> {new}" for old, new, alias in renames)
        )

    return configs, warnings


def detect_self_referential_joins(
    tables: list[SemanticViewMetadata],
    relationships: list[RelationshipMetadata],
    table_aliases: dict[str, str],
) -> dict[str, dict]:
    """
    Detect self-referential joins and identify nullable FK patterns.

    A self-referential join is when the same base table appears twice with
    different aliases (e.g., EMPLOYEE as EMP_FACT and EMPLOYEE as MGR_DIM).

    Args:
        tables: List of table metadata objects
        relationships: List of relationships between tables
        table_aliases: Dict mapping table name to alias (e.g., {"EMPLOYEE": "EMP_FACT"})

    Returns:
        Dict mapping referenced_alias to info about the nullable FK:
        {
            "MGR_DIM": {
                "base_table": "EMPLOYEE",
                "from_alias": "EMP_FACT",
                "nullable_fk_columns": ["MANAGER_ID"],
                "to_columns": ["EMP_ID"]
            }
        }
    """
    self_ref_info: dict[str, dict] = {}

    # Build reverse lookup: table name -> list of (alias, table_metadata)
    # A self-referential setup will have the same table name mapped to multiple aliases
    table_name_to_aliases: dict[str, list[tuple[str, SemanticViewMetadata]]] = {}
    for table in tables:
        alias = table_aliases.get(table.view, f"{table.view}_FACT")
        table_upper = table.view.upper()
        if table_upper not in table_name_to_aliases:
            table_name_to_aliases[table_upper] = []
        table_name_to_aliases[table_upper].append((alias, table))

    # Check each relationship for self-referential pattern
    for rel in relationships:
        from_table_upper = rel.from_table.upper()
        to_table_upper = rel.to_table.upper()

        # Self-referential: same base table name
        if from_table_upper == to_table_upper:
            # Find the from_table metadata to check FK nullability
            from_table_meta = next(
                (t for t in tables if t.view.upper() == from_table_upper),
                None
            )

            if not from_table_meta:
                continue

            # Check if FK columns are nullable
            nullable_fk_cols = []
            for fk_col_name in rel.from_columns:
                fk_col = next(
                    (c for c in from_table_meta.columns if c.name.upper() == fk_col_name.upper()),
                    None
                )
                if fk_col and fk_col.is_nullable:
                    nullable_fk_cols.append(fk_col_name)

            if nullable_fk_cols:
                # Get the aliases - from_alias is the "many" side, to_alias is the "one"/referenced side
                from_alias = table_aliases.get(rel.from_table, f"{rel.from_table}_FACT")
                to_alias = table_aliases.get(rel.to_table, f"{rel.to_table}_DIM")

                # If both aliases are the same, we need to differentiate
                # The "to" side (referenced) needs COALESCE
                # In self-referential cases, we look for _DIM suffix or MGR pattern
                if from_alias == to_alias:
                    # Check if there are multiple aliases for this table
                    aliases_for_table = table_name_to_aliases.get(from_table_upper, [])
                    if len(aliases_for_table) >= 2:
                        # Use the second alias as the "to" side
                        to_alias = aliases_for_table[1][0]

                self_ref_info[to_alias] = {
                    "base_table": to_table_upper,
                    "from_alias": from_alias,
                    "nullable_fk_columns": nullable_fk_cols,
                    "to_columns": list(rel.to_columns),
                }

    return self_ref_info


def get_coalesce_default_for_type(
    data_type: str,
    column_name: str | None = None,
    custom_defaults: dict[str, str] | None = None,
) -> str:
    """
    Get the appropriate COALESCE default value for a given data type.

    Args:
        data_type: The Snowflake data type (e.g., "VARCHAR", "NUMBER(10,2)")
        column_name: Optional column name to derive semantic defaults
        custom_defaults: Optional dict of column_name -> default_value overrides

    Returns:
        SQL literal string for the default value
    """
    # Check for custom override first
    if custom_defaults and column_name:
        upper_name = column_name.upper()
        if upper_name in custom_defaults:
            return custom_defaults[upper_name]

    # Normalize type to base category
    base_type = data_type.upper().split("(")[0].strip() if data_type else ""

    # String types - try to generate semantic default based on column name
    if base_type in ("VARCHAR", "CHAR", "CHARACTER", "STRING", "TEXT"):
        if column_name:
            upper_name = column_name.upper()
            if "MANAGER" in upper_name or "MGR" in upper_name:
                return "'(No Manager)'"
            elif "PARENT" in upper_name:
                return "'(No Parent)'"
            elif "SUPERVISOR" in upper_name:
                return "'(No Supervisor)'"
            elif "_NAME" in upper_name:
                return "'(No Name)'"
        return "'(No Value)'"

    # Numeric types
    if base_type in ("NUMBER", "DECIMAL", "NUMERIC", "INT", "INTEGER",
                     "BIGINT", "SMALLINT", "TINYINT", "FLOAT", "DOUBLE", "REAL"):
        return "0"

    # Date/Time types
    if base_type == "DATE":
        return "'1900-01-01'::DATE"
    if base_type in ("DATETIME", "TIMESTAMP", "TIMESTAMP_LTZ",
                     "TIMESTAMP_NTZ", "TIMESTAMP_TZ"):
        return "'1900-01-01 00:00:00'::TIMESTAMP"
    if base_type == "TIME":
        return "'00:00:00'::TIME"

    # Boolean
    if base_type == "BOOLEAN":
        return "FALSE"

    # Default fallback for unknown types (treat as string)
    return "'(No Value)'"


def apply_coalesce_for_self_referential(
    configs: list[SemanticColumnConfig],
    self_ref_info: dict[str, dict],
    custom_defaults: dict[str, str] | None = None,
) -> tuple[list[SemanticColumnConfig], list[str]]:
    """
    Mark columns from referenced self-referential aliases for COALESCE wrapping.

    Args:
        configs: List of column configurations
        self_ref_info: Output from detect_self_referential_joins()
        custom_defaults: Optional custom default values per column

    Returns:
        Tuple of (modified configs, list of info messages about COALESCE applied)
    """
    messages: list[str] = []
    coalesce_applied: list[str] = []

    for cfg in configs:
        alias = (cfg.table_alias or "").upper()

        # Check if this column's alias is a referenced side of self-referential join
        if alias in self_ref_info:
            # Only apply to DIMENSION columns (not metrics/facts)
            if cfg.kind == "DIMENSION":
                cfg.requires_coalesce = True
                cfg.coalesce_default = get_coalesce_default_for_type(
                    cfg.data_type,
                    cfg.semantic_name,
                    custom_defaults
                )
                coalesce_applied.append(
                    f"  - {alias}.{cfg.semantic_name} -> COALESCE(..., {cfg.coalesce_default})"
                )

    if coalesce_applied:
        messages.append(
            "Auto-wrapping columns in COALESCE for nullable FK in self-referential join:\n"
            + "\n".join(coalesce_applied)
        )

    return configs, messages


def detect_role_playing_dimensions(
    relationships: list[RelationshipMetadata],
) -> dict[str, list[RelationshipMetadata]]:
    """
    Detect when multiple FKs from the same source table point to the same target.

    This creates a "role-playing dimension" scenario, e.g.:
    - ORDERS.CREATED_BY -> EMPLOYEE.EMP_ID
    - ORDERS.APPROVED_BY -> EMPLOYEE.EMP_ID

    Power BI needs separate dimension copies to distinguish these relationships.

    Args:
        relationships: List of relationships between tables

    Returns:
        Dict mapping (source_table, target_table) tuple to list of relationships
        Only includes cases where there are 2+ relationships to same target from same source.

    Example:
        >>> rels = [
        ...     RelationshipMetadata("R1", "ORDERS", ["CREATED_BY"], "EMPLOYEE", ["EMP_ID"]),
        ...     RelationshipMetadata("R2", "ORDERS", ["APPROVED_BY"], "EMPLOYEE", ["EMP_ID"]),
        ... ]
        >>> detect_role_playing_dimensions(rels)
        {("ORDERS", "EMPLOYEE"): [R1, R2]}
    """
    # Group relationships by (from_table, to_table)
    groups: dict[tuple[str, str], list[RelationshipMetadata]] = {}

    for rel in relationships:
        key = (rel.from_table.upper(), rel.to_table.upper())
        if key not in groups:
            groups[key] = []
        groups[key].append(rel)

    # Return only groups with multiple relationships (role-playing scenario)
    return {k: v for k, v in groups.items() if len(v) >= 2}


def detect_circular_relationships(
    relationships: list[RelationshipMetadata],
    base_table: str,
) -> list[list[str]]:
    """
    Detect circular relationship chains starting from base_table.

    A circular chain is when following FK relationships leads back to a table
    already in the path, e.g., A -> B -> C -> A.

    Note: Self-referential tables (A -> A) are handled separately and not
    reported as circular chains here.

    Args:
        relationships: List of relationships between tables
        base_table: The starting/base table name

    Returns:
        List of cycles found. Each cycle is a list of table names forming the loop.
        Empty list if no cycles detected.

    Example:
        >>> rels = [
        ...     RelationshipMetadata("R1", "A", ["FK1"], "B", ["PK"]),
        ...     RelationshipMetadata("R2", "B", ["FK2"], "C", ["PK"]),
        ...     RelationshipMetadata("R3", "C", ["FK3"], "A", ["PK"]),  # Creates cycle!
        ... ]
        >>> detect_circular_relationships(rels, "A")
        [["A", "B", "C", "A"]]
    """
    # Build adjacency list (from_table -> list of to_tables)
    graph: dict[str, list[str]] = {}
    for rel in relationships:
        from_t = rel.from_table.upper()
        to_t = rel.to_table.upper()

        # Skip self-referential (handled separately)
        if from_t == to_t:
            continue

        if from_t not in graph:
            graph[from_t] = []
        graph[from_t].append(to_t)

    cycles: list[list[str]] = []
    base_upper = base_table.upper()

    def dfs(node: str, path: list[str], visited: set[str]) -> None:
        """DFS to find cycles."""
        if node in visited:
            # Found a cycle - extract the cycle portion
            if node in path:
                cycle_start = path.index(node)
                cycle = path[cycle_start:] + [node]
                cycles.append(cycle)
            return

        visited.add(node)
        path.append(node)

        for neighbor in graph.get(node, []):
            dfs(neighbor, path.copy(), visited.copy())

    # Start DFS from base table
    if base_upper in graph:
        dfs(base_upper, [], set())

    return cycles


def generate_semantic_view_ddl(
    base_table: SemanticViewMetadata,
    measures: list[str],
    aggregations: dict[str, list[str]],  # {"O_TOTALPRICE": ["SUM", "AVG"]} - used for metrics
    view_name: str,
    database: str,
    schema: str,
    column_configs: list[SemanticColumnConfig] | None = None,
) -> DDLResult:
    """
    Generate CREATE SEMANTIC VIEW DDL.

    Creates a semantic view that defines metrics at the correct grain level,
    preventing fan-out inflation when the view is used in joins.

    Uses Snowflake's correct syntax:
    - TABLES: alias AS full_table_name PRIMARY KEY (col)
    - DIMENSIONS: alias.dimension_name AS alias.column_name
    - METRICS: alias.metric_name AS AGGREGATE(column_name)
    - FACTS: alias.fact_name AS alias.column_name

    Args:
        base_table: The table to create a semantic view for (the "one" side)
        measures: List of measure column names to include as METRIC (legacy)
        aggregations: Dictionary mapping measure names to aggregation functions (legacy)
        view_name: Name for the new semantic view
        database: Database name
        schema: Schema name
        column_configs: Optional list of SemanticColumnConfig for full control.
                       If provided, measures/aggregations are ignored.

    Returns:
        DDLResult with the generated DDL

    Example output:
        CREATE OR REPLACE SEMANTIC VIEW DB.SCHEMA.ORDERS_METRICS
        TABLES (
            o AS DB.SCHEMA.ORDERS PRIMARY KEY (O_ORDERKEY)
        )
        DIMENSIONS (
            o.order_key AS o.O_ORDERKEY
                DESCRIPTION 'Primary key for orders'
        )
        METRICS (
            o.total_price AS SUM(O_TOTALPRICE)
                DESCRIPTION 'Total order value'
        );
    """
    fq_view_name = f"{database}.{schema}.{view_name}"
    fq_table_name = f"{database}.{schema}.{base_table.view}"
    table_alias = base_table.view[0].lower()  # First letter as alias

    # Find primary key column
    pk_cols = [c for c in base_table.columns if c.is_primary_key]
    pk_col_name = pk_cols[0].name if pk_cols else None

    # Build TABLES clause: alias AS full_table_name PRIMARY KEY (col)
    lines = [
        f"CREATE OR REPLACE SEMANTIC VIEW {fq_view_name}",
        "TABLES (",
    ]
    if pk_col_name:
        lines.append(f"    {table_alias} AS {fq_table_name} PRIMARY KEY ({pk_col_name})")
    else:
        lines.append(f"    {table_alias} AS {fq_table_name}")
    lines.append(")")

    # Use column_configs if provided, otherwise fall back to legacy behavior
    if column_configs:
        # New path: use SemanticColumnConfig list
        dim_defs = []
        metric_defs = []
        fact_defs = []

        for cfg in column_configs:
            semantic_name = cfg.semantic_name.lower()
            source_col = cfg.source_column

            # Escape description for SQL (single quotes) - use COMMENT = syntax
            desc_clause = ""
            if cfg.description:
                escaped_desc = cfg.description.replace("'", "''")
                desc_clause = f"\n        COMMENT = '{escaped_desc}'"

            if cfg.kind == "DIMENSION":
                dim_defs.append(
                    f"    {table_alias}.{semantic_name} AS {table_alias}.{source_col}{desc_clause}"
                )
            elif cfg.kind == "METRIC":
                agg = cfg.aggregation or "SUM"
                agg_expr = format_metric_expression(agg, source_col)
                metric_defs.append(
                    f"    {table_alias}.{semantic_name} AS {agg_expr}{desc_clause}"
                )
            elif cfg.kind == "FACT":
                fact_defs.append(
                    f"    {table_alias}.{semantic_name} AS {table_alias}.{source_col}{desc_clause}"
                )

        if dim_defs:
            lines.append("DIMENSIONS (")
            lines.append(",\n".join(dim_defs))
            lines.append(")")

        if metric_defs:
            lines.append("METRICS (")
            lines.append(",\n".join(metric_defs))
            lines.append(")")

        if fact_defs:
            lines.append("FACTS (")
            lines.append(",\n".join(fact_defs))
            lines.append(")")

    else:
        # Legacy path: use measures and aggregations
        dim_defs = []

        # Add primary key as dimension
        if pk_col_name:
            dim_name = pk_col_name.lower()
            dim_defs.append(f"    {table_alias}.{dim_name} AS {table_alias}.{pk_col_name}")

        # Add other dimension columns (limit to key foreign keys)
        dim_cols = [
            c for c in base_table.columns
            if not c.is_primary_key
            and c.kind in ("DIMENSION", "COLUMN")
            and "KEY" in c.name.upper()
        ][:3]  # Limit to 3 FK dimensions

        for col in dim_cols:
            dim_name = col.name.lower()
            dim_defs.append(f"    {table_alias}.{dim_name} AS {table_alias}.{col.name}")

        if dim_defs:
            lines.append("DIMENSIONS (")
            lines.append(",\n".join(dim_defs))
            lines.append(")")

        # Build METRICS clause: alias.metric_name AS AGGREGATE(column_name)
        metric_defs = []
        for measure in measures:
            # Get aggregation function(s) for this measure, default to SUM
            agg_funcs = aggregations.get(measure, ["SUM"])
            agg_func = agg_funcs[0] if agg_funcs else "SUM"
            metric_name = measure.lower()
            metric_defs.append(f"    {table_alias}.{metric_name} AS {agg_func}({measure})")

        if metric_defs:
            lines.append("METRICS (")
            lines.append(",\n".join(metric_defs))
            lines.append(")")

    lines.append(";")

    ddl = "\n".join(lines)

    return DDLResult(
        ddl=ddl,
        object_name=fq_view_name,
        object_type="SEMANTIC_VIEW",
        description=f"Semantic view for {base_table.view} with pre-defined metrics"
    )


class GranularityConstraintError(ValueError):
    """Raised when semantic view configuration violates Snowflake granularity constraints."""
    pass


class MultiPathConflictError(ValueError):
    """Raised when multi-path relationships are detected in semantic view configuration.

    Snowflake semantic views don't support ambiguous relationship paths.
    When there are two different paths from the base table to another table,
    Snowflake fails with "Multi-path relationship between X and Y is not supported."
    """

    def __init__(self, message: str, conflicts: list[dict]):
        self.message = message
        self.conflicts = conflicts
        super().__init__(message)


def _validate_granularity_constraints(
    from_table_configs: list[SemanticColumnConfig] | None,
    to_table_configs: list[SemanticColumnConfig] | None,
    from_table_name: str,
    to_table_name: str,
) -> None:
    """
    Validate that metrics/dimensions don't violate Snowflake's granularity rules.

    Snowflake Rule: Dimensions must be at EQUAL or LOWER granularity than metrics.

    In multi-table semantic views:
    - "many" side (fact table) has HIGHER granularity
    - "one" side (dimension table) has LOWER granularity

    Invalid combination: METRICS on "one" side + DIMENSIONS on "many" side
    This fails because "many" side dimensions have higher granularity than "one" side metrics.

    Raises:
        GranularityConstraintError: If the configuration violates granularity rules.
    """
    from_has_dimensions = any(c.kind == "DIMENSION" for c in (from_table_configs or []))
    to_has_metrics = any(c.kind == "METRIC" for c in (to_table_configs or []))

    if from_has_dimensions and to_has_metrics:
        to_metrics = [c.semantic_name for c in to_table_configs if c.kind == "METRIC"]
        from_dims = [c.semantic_name for c in from_table_configs if c.kind == "DIMENSION"]
        raise GranularityConstraintError(
            f"Granularity constraint violation: Cannot have metrics from '{to_table_name}' "
            f"(dimension table) when there are dimensions from '{from_table_name}' (fact table).\n\n"
            f"Problematic metrics on dimension table: {to_metrics}\n"
            f"Dimensions on fact table: {from_dims}\n\n"
            f"Power BI queries ALL columns together, which triggers this Snowflake error.\n\n"
            f"Solutions:\n"
            f"1. Remove metrics from '{to_table_name}' tab (recommended)\n"
            f"2. OR remove dimensions from '{from_table_name}' tab"
        )


def generate_multi_table_semantic_view_ddl(
    from_table: SemanticViewMetadata,  # The "many" side / fact table (e.g., LINEITEM, SALES_FACT)
    to_table: SemanticViewMetadata,    # The "one" side / dimension table (e.g., ORDERS, CUSTOMERS)
    relationship: RelationshipMetadata,
    view_name: str,
    database: str,
    schema: str,
    from_table_configs: list[SemanticColumnConfig] | None = None,
    to_table_configs: list[SemanticColumnConfig] | None = None,
) -> DDLResult:
    """
    Generate CREATE SEMANTIC VIEW DDL for multi-table semantic views.

    Creates a semantic view that joins two tables following Snowflake's granularity rules.

    IMPORTANT - Snowflake Granularity Constraints:
    - Dimensions must be at EQUAL or LOWER granularity than metrics
    - The "many" side (fact table) has HIGHER granularity
    - The "one" side (dimension table) has LOWER granularity

    Correct pattern for multi-table semantic views:
    - METRICS: Define on the "many" side (fact table) - e.g., SUM(quantity), SUM(amount)
    - DIMENSIONS: Define on the "one" side (dimension table) - e.g., customer_name, region
    - FACTS: Define on the "many" side (fact table) - detail columns
    - Dimensions from the "many" side are also allowed (same granularity as metrics)

    Uses Snowflake's correct syntax with RELATIONSHIPS:
    - TABLES: ALIAS as DB.SCHEMA.TABLE primary key (COL)
    - RELATIONSHIPS: many_side(FK) references one_side(PK)
    - DIMENSIONS: From "one" side (and optionally "many" side)
    - METRICS: From "many" side (aggregations at detail level)
    - FACTS: From "many" side (detail-level data)

    Args:
        from_table: The "many" side / fact table (e.g., LINEITEM) - METRICS go here
        to_table: The "one" side / dimension table (e.g., ORDERS) - DIMENSIONS go here
        relationship: The relationship between tables
        view_name: Name for the new semantic view
        database: Database name
        schema: Schema name
        from_table_configs: Column configs from the "many" side (METRICS, FACTS, some DIMENSIONS)
        to_table_configs: Column configs from the "one" side (DIMENSIONS only)

    Returns:
        DDLResult with the generated DDL

    Example output (based on working CUSTOMER_SALES_SEMANTIC):
        CREATE OR REPLACE SEMANTIC VIEW DB.SCHEMA.LINEITEM_ORDERS_SV
        TABLES (
            ORDERS_DIM as DB.SCHEMA.ORDERS primary key (O_ORDERKEY),
            LINEITEM_FACT as DB.SCHEMA.LINEITEM primary key (L_ORDERKEY, L_LINENUMBER)
        )
        RELATIONSHIPS (
            lineitem_to_orders as LINEITEM_FACT(L_ORDERKEY) references ORDERS_DIM(O_ORDERKEY)
        )
        DIMENSIONS (
            ORDERS_DIM.order_date as ORDERS_DIM.O_ORDERDATE,
            ORDERS_DIM.order_status as ORDERS_DIM.O_ORDERSTATUS
        )
        METRICS (
            LINEITEM_FACT.total_quantity as SUM(L_QUANTITY),
            LINEITEM_FACT.total_extendedprice as SUM(L_EXTENDEDPRICE)
        )
        FACTS (
            LINEITEM_FACT.line_number as LINEITEM_FACT.L_LINENUMBER
        );
    """
    # Validate granularity constraints before generating DDL
    _validate_granularity_constraints(
        from_table_configs=from_table_configs,
        to_table_configs=to_table_configs,
        from_table_name=from_table.view,
        to_table_name=to_table.view,
    )

    fq_view_name = f"{database}.{schema}.{view_name}"
    # Use the source tables' own database/schema from metadata
    fq_from_table = f"{from_table.database}.{from_table.schema}.{from_table.view}"
    fq_to_table = f"{to_table.database}.{to_table.schema}.{to_table.view}"

    # Generate descriptive aliases (like CUSTOMERS_TABLE, SALES_TABLE in working example)
    # Use _DIM suffix for dimension table ("one" side) and _FACT suffix for fact table ("many" side)
    from_alias = f"{from_table.view}_FACT"  # "many" side = fact table
    to_alias = f"{to_table.view}_DIM"       # "one" side = dimension table

    # Get primary key columns
    from_pk_cols = [c for c in from_table.columns if c.is_primary_key]
    to_pk_cols = [c for c in to_table.columns if c.is_primary_key]
    from_pk_names = ",".join(c.name for c in from_pk_cols) if from_pk_cols else None
    to_pk_names = ",".join(c.name for c in to_pk_cols) if to_pk_cols else None

    # Build TABLES clause (use lowercase 'as' and 'primary key' like working example)
    lines = [
        f"CREATE OR REPLACE SEMANTIC VIEW {fq_view_name}",
        "TABLES (",
    ]

    table_defs = []
    # "one" side (dimension table) first
    if to_pk_names:
        table_defs.append(f"    {to_alias} as {fq_to_table} primary key ({to_pk_names})")
    else:
        table_defs.append(f"    {to_alias} as {fq_to_table}")

    # "many" side (fact table) second
    if from_pk_names:
        table_defs.append(f"    {from_alias} as {fq_from_table} primary key ({from_pk_names})")
    else:
        table_defs.append(f"    {from_alias} as {fq_from_table}")

    lines.append(",\n".join(table_defs))
    lines.append(")")

    # Build RELATIONSHIPS clause (use lowercase 'as' and 'references' like working example)
    # Pattern: many_side(FK) references one_side(PK)
    # Supports composite keys: TABLE(col1, col2) references OTHER(col1, col2)
    rel_name = f"{from_table.view.lower()}_to_{to_table.view.lower()}"
    from_cols = ", ".join(relationship.from_columns)
    to_cols = ", ".join(relationship.to_columns)
    lines.append("RELATIONSHIPS (")
    lines.append(f"    {rel_name} as {from_alias}({from_cols}) references {to_alias}({to_cols})")
    lines.append(")")

    def escape_desc(desc: str | None) -> str:
        """Format description as comment clause (use lowercase 'comment' like working example)."""
        if desc:
            escaped = desc.replace("'", "''")
            return f" comment='{escaped}'"
        return ""

    # Collect all configs into a flat list and ensure each has a table_alias
    all_configs: list[SemanticColumnConfig] = []

    # Process to_table configs (the "one" side / dimension table)
    if to_table_configs:
        for cfg in to_table_configs:
            if not cfg.table_alias:
                cfg.table_alias = to_alias
            all_configs.append(cfg)

    # Process from_table configs (the "many" side / fact table)
    if from_table_configs:
        for cfg in from_table_configs:
            if not cfg.table_alias:
                cfg.table_alias = from_alias
            all_configs.append(cfg)

    # Resolve duplicate dimension names for self-referential tables
    # This auto-renames duplicates like EMP.EMP_NAME -> EMPLOYEE_NAME, MGR.EMP_NAME -> MANAGER_NAME
    all_configs, _duplicate_warnings = resolve_duplicate_dimension_names(all_configs, [relationship])

    # Detect self-referential joins with nullable FKs and apply COALESCE
    table_aliases = {from_table.view: from_alias, to_table.view: to_alias}
    tables_list = [from_table, to_table]
    self_ref_info = detect_self_referential_joins(tables_list, [relationship], table_aliases)
    if self_ref_info:
        all_configs, _coalesce_messages = apply_coalesce_for_self_referential(
            all_configs, self_ref_info
        )

    # Collect dimensions, metrics, facts from resolved configs
    dim_defs = []
    metric_defs = []
    fact_defs = []

    for cfg in all_configs:
        alias = cfg.table_alias or ""
        semantic_name = cfg.semantic_name.lower()
        source_col = cfg.source_column
        desc_clause = escape_desc(cfg.description)

        if cfg.kind == "DIMENSION":
            # Build the source expression
            source_expr = f"{alias.lower()}.{source_col.lower()}"

            # Wrap in COALESCE if needed for nullable FK in self-referential join
            if cfg.requires_coalesce and cfg.coalesce_default:
                source_expr = f"COALESCE({source_expr}, {cfg.coalesce_default})"

            dim_defs.append(f"    {alias}.{semantic_name} as {source_expr}{desc_clause}")
        elif cfg.kind == "METRIC":
            agg = cfg.aggregation or "SUM"
            agg_expr = format_metric_expression(agg, f"{alias.lower()}.{source_col.lower()}")
            metric_defs.append(f"    {alias}.{semantic_name} as {agg_expr}{desc_clause}")
        elif cfg.kind == "FACT":
            fact_defs.append(f"    {alias}.{semantic_name} as {alias.lower()}.{source_col.lower()}{desc_clause}")

    # Add clauses if they have content (use lowercase like working example)
    if fact_defs:
        lines.append("FACTS (")
        lines.append(",\n".join(fact_defs))
        lines.append(")")

    if dim_defs:
        lines.append("DIMENSIONS (")
        lines.append(",\n".join(dim_defs))
        lines.append(")")

    if metric_defs:
        lines.append("METRICS (")
        lines.append(",\n".join(metric_defs))
        lines.append(")")

    lines.append(";")
    ddl = "\n".join(lines)

    return DDLResult(
        ddl=ddl,
        object_name=fq_view_name,
        object_type="SEMANTIC_VIEW",
        description=f"Multi-table semantic view joining {from_table.view} and {to_table.view}"
    )


def _validate_n_table_granularity_constraints(
    tables: list[SemanticViewMetadata],
    table_configs: dict[str, list[SemanticColumnConfig]],
    base_table: SemanticViewMetadata,
) -> None:
    """
    Validate granularity constraints for N-table semantic views.

    Rules:
    - Metrics can only be defined on the base table (fact/many-side)
    - Dimensions can be on any table
    - Facts can only be on the base table

    Raises:
        GranularityConstraintError: If any table violates granularity rules.
    """
    base_name = base_table.view.upper()

    for table in tables:
        table_name = table.view.upper()
        configs = table_configs.get(table.view, [])

        if table_name != base_name:
            # This is a dimension table - cannot have metrics or facts
            metrics_on_dim = [c.semantic_name for c in configs if c.kind == "METRIC"]
            facts_on_dim = [c.semantic_name for c in configs if c.kind == "FACT"]

            if metrics_on_dim:
                raise GranularityConstraintError(
                    f"Granularity constraint violation: Cannot have metrics on dimension table '{table.view}'.\n\n"
                    f"Problematic metrics: {metrics_on_dim}\n\n"
                    f"Metrics can only be defined on the base table '{base_table.view}' (fact table).\n\n"
                    f"Solution: Move these metrics to the '{base_table.view}' tab, or remove them."
                )

            if facts_on_dim:
                raise GranularityConstraintError(
                    f"Granularity constraint violation: Cannot have facts on dimension table '{table.view}'.\n\n"
                    f"Problematic facts: {facts_on_dim}\n\n"
                    f"Facts can only be defined on the base table '{base_table.view}' (fact table).\n\n"
                    f"Solution: Move these facts to the '{base_table.view}' tab, or remove them."
                )


def generate_n_table_semantic_view_ddl(
    tables: list[SemanticViewMetadata],
    relationships: list[RelationshipMetadata],
    table_configs: dict[str, list[SemanticColumnConfig]],
    base_table: SemanticViewMetadata,
    view_name: str,
    database: str,
    schema: str,
) -> DDLResult:
    """
    Generate CREATE SEMANTIC VIEW DDL for N-table semantic views (3+ tables).

    Creates a semantic view that joins multiple tables following Snowflake's granularity rules.

    IMPORTANT - Snowflake Granularity Constraints:
    - Dimensions must be at EQUAL or LOWER granularity than metrics
    - The base table (fact) has the HIGHEST granularity
    - Dimension tables have LOWER granularity
    - METRICS and FACTS can only be on the base table
    - DIMENSIONS can be on any table

    Args:
        tables: List of all tables to include in the semantic view
        relationships: List of relationships between the tables
        table_configs: Dict mapping table name to its column configurations
        base_table: The base/fact table (identified by identify_base_table())
        view_name: Name for the new semantic view
        database: Database name for the view
        schema: Schema name for the view

    Returns:
        DDLResult with the generated DDL

    Example output (3 tables: LINEITEM, ORDERS, CUSTOMER):
        CREATE OR REPLACE SEMANTIC VIEW DB.SCHEMA.LINEITEM_ORDERS_CUSTOMER_SV
        TABLES (
            LINEITEM_FACT as DB.SCHEMA.LINEITEM primary key (L_ORDERKEY, L_LINENUMBER),
            ORDERS_DIM as DB.SCHEMA.ORDERS primary key (O_ORDERKEY),
            CUSTOMER_DIM as DB.SCHEMA.CUSTOMER primary key (C_CUSTKEY)
        )
        RELATIONSHIPS (
            lineitem_to_orders as LINEITEM_FACT(L_ORDERKEY) references ORDERS_DIM(O_ORDERKEY),
            orders_to_customer as ORDERS_DIM(O_CUSTKEY) references CUSTOMER_DIM(C_CUSTKEY)
        )
        DIMENSIONS (
            LINEITEM_FACT.ship_mode as lineitem_fact.l_shipmode,
            ORDERS_DIM.order_date as orders_dim.o_orderdate,
            CUSTOMER_DIM.customer_name as customer_dim.c_name
        )
        METRICS (
            LINEITEM_FACT.quantity as SUM(lineitem_fact.l_quantity)
        );
    """
    # Validate granularity constraints
    _validate_n_table_granularity_constraints(tables, table_configs, base_table)

    # Check for multi-path relationship conflicts
    conflicts = detect_multi_path_conflicts(tables, relationships, base_table.view)
    if conflicts:
        # Build detailed error message
        conflict_details = []
        for conflict in conflicts:
            paths_str = "\n".join(
                f"      Path {i+1}: {' -> '.join(p)}"
                for i, p in enumerate(conflict["paths"])
            )
            conflict_details.append(
                f"  - {conflict['target_table']} is reachable via multiple paths:\n{paths_str}"
            )

        raise MultiPathConflictError(
            message=(
                f"Multi-path relationships detected!\n\n"
                f"Snowflake semantic views require unambiguous relationship paths.\n"
                f"The following tables have multiple paths from '{base_table.view}':\n\n"
                + "\n".join(conflict_details)
                + "\n\n"
                f"Solution: Remove one of the conflicting relationships to create an unambiguous path.\n"
                f"For example, if both direct (A->B) and indirect (A->C->B) paths exist, remove one."
            ),
            conflicts=conflicts,
        )

    fq_view_name = f"{database}.{schema}.{view_name}"

    # Generate aliases for each table
    # Base table gets _FACT suffix, others get _DIM suffix
    base_name_upper = base_table.view.upper()
    table_aliases: dict[str, str] = {}
    for table in tables:
        if table.view.upper() == base_name_upper:
            table_aliases[table.view] = f"{table.view}_FACT"
        else:
            table_aliases[table.view] = f"{table.view}_DIM"

    def escape_desc(desc: str | None) -> str:
        """Format description as comment clause."""
        if desc:
            escaped = desc.replace("'", "''")
            return f" comment='{escaped}'"
        return ""

    # Build TABLES clause
    lines = [
        f"CREATE OR REPLACE SEMANTIC VIEW {fq_view_name}",
        "TABLES (",
    ]

    table_defs = []
    for table in tables:
        alias = table_aliases[table.view]
        fq_table = f"{table.database}.{table.schema}.{table.view}"

        # Get primary key columns
        pk_cols = [c for c in table.columns if c.is_primary_key]
        pk_names = ",".join(c.name for c in pk_cols) if pk_cols else None

        if pk_names:
            table_defs.append(f"    {alias} as {fq_table} primary key ({pk_names})")
        else:
            table_defs.append(f"    {alias} as {fq_table}")

    lines.append(",\n".join(table_defs))
    lines.append(")")

    # Build RELATIONSHIPS clause
    # Supports composite keys: TABLE(col1, col2) references OTHER(col1, col2)
    if relationships:
        lines.append("RELATIONSHIPS (")
        rel_defs = []
        for rel in relationships:
            from_alias = table_aliases.get(rel.from_table, f"{rel.from_table}_FACT")
            to_alias = table_aliases.get(rel.to_table, f"{rel.to_table}_DIM")
            rel_name = f"{rel.from_table.lower()}_to_{rel.to_table.lower()}"
            from_cols = ", ".join(rel.from_columns)
            to_cols = ", ".join(rel.to_columns)
            rel_defs.append(
                f"    {rel_name} as {from_alias}({from_cols}) references {to_alias}({to_cols})"
            )
        lines.append(",\n".join(rel_defs))
        lines.append(")")

    # Collect all configs into a flat list and ensure each has a table_alias
    all_configs: list[SemanticColumnConfig] = []
    for table in tables:
        alias = table_aliases[table.view]
        configs = table_configs.get(table.view, [])

        for cfg in configs:
            # Ensure table_alias is set (use auto-generated if not specified)
            if not cfg.table_alias:
                cfg.table_alias = alias
            all_configs.append(cfg)

    # Resolve duplicate dimension names for self-referential tables
    # This auto-renames duplicates like EMP.EMP_NAME -> EMPLOYEE_NAME, MGR.EMP_NAME -> MANAGER_NAME
    all_configs, _duplicate_warnings = resolve_duplicate_dimension_names(all_configs, relationships)

    # Detect self-referential joins with nullable FKs and apply COALESCE
    self_ref_info = detect_self_referential_joins(tables, relationships, table_aliases)
    if self_ref_info:
        all_configs, _coalesce_messages = apply_coalesce_for_self_referential(
            all_configs, self_ref_info
        )

    # Collect dimensions, metrics, facts from resolved configs
    dim_defs = []
    metric_defs = []
    fact_defs = []

    for cfg in all_configs:
        alias = cfg.table_alias or ""
        semantic_name = cfg.semantic_name.lower()
        source_col = cfg.source_column
        desc_clause = escape_desc(cfg.description)

        if cfg.kind == "DIMENSION":
            # Build the source expression
            source_expr = f"{alias.lower()}.{source_col.lower()}"

            # Wrap in COALESCE if needed for nullable FK in self-referential join
            if cfg.requires_coalesce and cfg.coalesce_default:
                source_expr = f"COALESCE({source_expr}, {cfg.coalesce_default})"

            dim_defs.append(
                f"    {alias}.{semantic_name} as {source_expr}{desc_clause}"
            )
        elif cfg.kind == "METRIC":
            agg = cfg.aggregation or "SUM"
            agg_expr = format_metric_expression(agg, f"{alias.lower()}.{source_col.lower()}")
            metric_defs.append(
                f"    {alias}.{semantic_name} as {agg_expr}{desc_clause}"
            )
        elif cfg.kind == "FACT":
            fact_defs.append(
                f"    {alias}.{semantic_name} as {alias.lower()}.{source_col.lower()}{desc_clause}"
            )

    # Add clauses if they have content
    if fact_defs:
        lines.append("FACTS (")
        lines.append(",\n".join(fact_defs))
        lines.append(")")

    if dim_defs:
        lines.append("DIMENSIONS (")
        lines.append(",\n".join(dim_defs))
        lines.append(")")

    if metric_defs:
        lines.append("METRICS (")
        lines.append(",\n".join(metric_defs))
        lines.append(")")

    lines.append(";")
    ddl = "\n".join(lines)

    table_names = ", ".join(t.view for t in tables)
    return DDLResult(
        ddl=ddl,
        object_name=fq_view_name,
        object_type="SEMANTIC_VIEW",
        description=f"Multi-table semantic view joining {table_names}"
    )


def generate_dax_measure(
    measure_name: str,
    source_table: str,
    measure_column: str,
    pk_column: str,
    aggregation: str = "SUM"
) -> str:
    """
    Generate DAX measure that handles fan-out at query time.

    No Snowflake objects needed - copy this measure to Power BI Desktop.
    Uses SUMX/VALUES pattern to aggregate at the correct grain.

    Args:
        measure_name: Name for the new measure
        source_table: Table containing the measure column
        measure_column: Column to aggregate
        pk_column: Primary key column for deduplication
        aggregation: Aggregation function (SUM, AVG, COUNT, MIN, MAX)

    Returns:
        DAX measure code as string

    Example output:
        O_TOTALPRICE (Correct) =
        SUMX(
            VALUES(ORDERS[O_ORDERKEY]),
            CALCULATE(MAX(ORDERS[O_TOTALPRICE]))
        )
    """
    # Map aggregation to appropriate DAX pattern
    if aggregation.upper() == "SUM":
        inner_agg = "SUM"
        outer_func = "SUMX"
    elif aggregation.upper() == "AVG":
        inner_agg = "AVERAGE"
        outer_func = "AVERAGEX"
    elif aggregation.upper() == "COUNT":
        inner_agg = "COUNT"
        outer_func = "COUNTX"
    elif aggregation.upper() == "MIN":
        inner_agg = "MIN"
        outer_func = "MINX"
    elif aggregation.upper() == "MAX":
        inner_agg = "MAX"
        outer_func = "MAXX"
    else:
        inner_agg = "SUM"
        outer_func = "SUMX"

    # For SUM, we use MAX in the inner CALCULATE to get the single value per PK
    # Then SUMX aggregates across all unique PKs
    if aggregation.upper() == "SUM":
        dax = f"""{measure_name} (Correct) =
{outer_func}(
    VALUES({source_table}[{pk_column}]),
    CALCULATE(MAX({source_table}[{measure_column}]))
)"""
    elif aggregation.upper() == "AVG":
        dax = f"""{measure_name} (Correct) =
{outer_func}(
    VALUES({source_table}[{pk_column}]),
    CALCULATE(MAX({source_table}[{measure_column}]))
)"""
    elif aggregation.upper() == "COUNT":
        dax = f"""{measure_name} (Correct) =
COUNTROWS(
    VALUES({source_table}[{pk_column}])
)"""
    else:
        dax = f"""{measure_name} (Correct) =
{outer_func}(
    VALUES({source_table}[{pk_column}]),
    CALCULATE(MAX({source_table}[{measure_column}]))
)"""

    return dax


def execute_ddl(session, ddl: str) -> tuple[bool, str]:
    """
    Execute DDL statement(s) in Snowflake.

    Handles multiple statements separated by semicolons.
    Each statement is executed separately since Snowflake's
    session.sql() only supports single statements.

    Args:
        session: Snowflake session (can be Snowpark session or snowflake-connector cursor)
        ddl: The DDL statement(s) to execute (can contain multiple statements)

    Returns:
        Tuple of (success: bool, message: str)
    """
    import re

    # Split DDL into individual statements
    # Filter out empty statements and comments-only lines
    statements = []
    for stmt in ddl.split(';'):
        # Remove leading/trailing whitespace
        stmt = stmt.strip()
        if not stmt:
            continue

        # Check if it has any actual SQL (not just comments)
        non_comment_lines = [
            line.strip() for line in stmt.split('\n')
            if line.strip() and not line.strip().startswith('--')
        ]
        if non_comment_lines:
            # Keep the statement with SQL (may include comments)
            statements.append(stmt)

    if not statements:
        return False, "No valid SQL statements found"

    def extract_object_name(stmt: str) -> str | None:
        """Extract the object name from a CREATE statement."""
        # Match patterns like: CREATE ... SEMANTIC VIEW db.schema.name
        # or CREATE ... TABLE db.schema.name
        pattern = r'CREATE\s+(?:OR\s+REPLACE\s+)?(?:SEMANTIC\s+VIEW|TABLE|VIEW)\s+([^\s(]+)'
        match = re.search(pattern, stmt, re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    def verify_object_exists(obj_name: str, obj_type: str) -> bool:
        """Verify an object was created by checking if it exists."""
        try:
            # Try to describe the object
            if obj_type == "SEMANTIC VIEW":
                check_sql = f"DESC SEMANTIC VIEW {obj_name}"
            elif obj_type == "TABLE":
                check_sql = f"DESC TABLE {obj_name}"
            else:
                check_sql = f"DESC VIEW {obj_name}"

            result = session.sql(check_sql).collect()
            return len(result) > 0
        except Exception as e:
            logger.debug(f"Object verification failed for {obj_name}: {e}")
            return False

    try:
        results = []
        for stmt in statements:
            stmt_upper = stmt.upper()

            # Determine object type for verification
            if "SEMANTIC VIEW" in stmt_upper:
                obj_type = "SEMANTIC VIEW"
            elif "TABLE" in stmt_upper:
                obj_type = "TABLE"
            elif "VIEW" in stmt_upper:
                obj_type = "VIEW"
            else:
                obj_type = None

            obj_name = extract_object_name(stmt)

            # Execute the DDL using multiple methods
            # Snowpark can throw errors during result processing even if DDL succeeded
            execution_error = None
            snowflake_error = None

            # Method 1: Try using underlying cursor (bypasses Snowpark DataFrame issues)
            # This is more reliable for DDL statements
            try:
                cursor = session.connection.cursor()
                cursor.execute(stmt)
                result = cursor.fetchone()
                cursor.close()
                if result:
                    results.append(str(result[0]) if result[0] else "OK")
                else:
                    results.append("Statement executed successfully")
                continue  # Success - move to next statement
            except AttributeError:
                # session.connection might not exist (e.g., in tests)
                pass
            except Exception as cursor_err:
                err_str = str(cursor_err)
                # Check if this is a Snowflake SQL error
                if any(code in err_str for code in ['001', '002', '090', 'SQL compilation error']):
                    return False, f"Snowflake error: {err_str}"
                # Otherwise fall through to Method 2

            # Method 2: Try collect() (standard Snowpark method)
            try:
                result = session.sql(stmt).collect()
                if result:
                    results.append(str(result[0][0]) if result[0] else "OK")
                else:
                    results.append("Statement executed successfully")
                continue  # Success - move to next statement
            except Exception as collect_err:
                err_str = str(collect_err)
                # Check if this is a Snowflake SQL error (syntax, permissions, etc.)
                if any(code in err_str for code in ['001', '002', '090', 'SQL compilation error']):
                    snowflake_error = err_str
                else:
                    execution_error = collect_err

            # If we have a Snowflake SQL error, report it immediately
            if snowflake_error:
                return False, f"Snowflake error: {snowflake_error}"

            # Method 3: If collect() failed with non-SQL error (like alias error),
            # the DDL might have succeeded - verify the object exists
            if execution_error:
                err_str = str(execution_error)
                is_alias_error = "alias" in err_str.lower() or "1301" in err_str

                if obj_name and obj_type:
                    # Verify the object was actually created
                    if verify_object_exists(obj_name, obj_type):
                        results.append(f"{obj_type} created successfully")
                        continue
                    else:
                        # Object doesn't exist - DDL failed
                        # The alias error masked the real issue
                        return False, f"DDL failed - {obj_type} not created. Please run this SQL manually in Snowflake to see the actual error:\n\n{stmt}"
                elif is_alias_error:
                    # Can't verify but it's likely the alias error
                    results.append("Statement executed (unverified)")
                    continue
                else:
                    return False, err_str

        # Return summary
        if len(statements) == 1:
            return True, results[0]
        else:
            return True, f"Executed {len(statements)} statements successfully"
    except Exception as e:
        return False, str(e)


def get_default_semantic_view_name(table_name: str) -> str:
    """Generate default semantic view name."""
    return f"{table_name}_METRICS"
