"""
Fan-out validator for relationship-based data models.

Validates measure-dimension combinations to detect and prevent fan-out issues
where aggregating measures from the "one" side of a relationship while grouping
by the "many" side causes inflated values.
"""

from dataclasses import dataclass
from typing import Literal

from .metadata_fetcher import (
    RelationshipMetadata,
    SemanticViewMetadata,
    CardinalityInfo,
    FanOutRisk,
)


@dataclass
class BlockedCombination:
    """Represents a blocked measure-dimension combination."""
    measure_table: str
    measure_column: str
    grouping_table: str
    reason: str
    inflation_factor: float | None = None


@dataclass
class RelationshipIssue:
    """
    Categorized relationship issue with appropriate solutions.

    Issue types:
    - "fan_out": Many:one relationship where measures on "one" side get inflated
      Solution: Snowflake Semantic Views (DirectQuery) or DAX SUMX/VALUES (Import only)
    - "many_to_many": Both sides have "many" cardinality
      Solution: Bridge table
    - "none": No issue detected
    """
    issue_type: Literal["fan_out", "many_to_many", "none"]
    relationship: RelationshipMetadata
    reason: str
    solutions: list[str]  # ["semantic_view", "dax_measure", "bridge_table"]
    affected_measures: list[str] | None = None
    inflation_factor: float | None = None


@dataclass
class ValidationResult:
    """Result of validating measure-dimension combinations."""
    is_valid: bool
    warnings: list[str]
    errors: list[str]
    blocked_combinations: list[BlockedCombination]
    fan_out_risks: list[FanOutRisk]

    @property
    def has_issues(self) -> bool:
        """Check if there are any warnings or errors."""
        return len(self.warnings) > 0 or len(self.errors) > 0


def validate_measure_dimension_combinations(
    relationships: list[RelationshipMetadata],
    tables_metadata: list[SemanticViewMetadata],
    strict_mode: bool = False
) -> ValidationResult:
    """
    Validate that selected measures and dimensions don't cause fan-out.

    Rules:
    - Measures from "one" side cannot be safely grouped by "many" side attributes
    - Warning if cardinality is uncertain
    - Error if high fan-out risk detected (in strict mode)

    Args:
        relationships: List of relationships between tables
        tables_metadata: Metadata for all selected tables
        strict_mode: If True, high-risk combinations generate errors instead of warnings

    Returns:
        ValidationResult with warnings, errors, and blocked combinations
    """
    warnings: list[str] = []
    errors: list[str] = []
    blocked: list[BlockedCombination] = []
    fan_out_risks: list[FanOutRisk] = []

    # Build a lookup for table metadata
    table_lookup = {m.view: m for m in tables_metadata}

    for rel in relationships:
        # Skip if no fan-out risk info
        if not rel.fan_out_risk:
            continue

        risk = rel.fan_out_risk
        fan_out_risks.append(risk)

        if risk.risk_level == "none":
            continue

        # Get table metadata
        from_table = table_lookup.get(rel.from_table)
        to_table = table_lookup.get(rel.to_table)

        if not from_table or not to_table:
            continue

        # Generate warning/error message
        msg = _format_risk_message(rel, risk, from_table, to_table)

        if risk.risk_level in ("critical", "high"):
            if strict_mode:
                errors.append(msg)
            else:
                warnings.append(msg)

            # Add blocked combinations for each affected measure
            for measure in risk.affected_measures:
                blocked.append(BlockedCombination(
                    measure_table=rel.to_table,
                    measure_column=measure,
                    grouping_table=rel.from_table,
                    reason=risk.reason,
                    inflation_factor=risk.inflation_factor
                ))
        elif risk.risk_level == "medium":
            warnings.append(msg)
        # Low risk: no warning needed

    is_valid = len(errors) == 0

    return ValidationResult(
        is_valid=is_valid,
        warnings=warnings,
        errors=errors,
        blocked_combinations=blocked,
        fan_out_risks=fan_out_risks
    )


def _format_risk_message(
    rel: RelationshipMetadata,
    risk: FanOutRisk,
    from_table: SemanticViewMetadata,
    to_table: SemanticViewMetadata
) -> str:
    """Format a human-readable risk message."""
    inflation_str = f" (~{risk.inflation_factor:.1f}x)" if risk.inflation_factor else ""

    if risk.risk_level == "critical":
        prefix = "CRITICAL"
    elif risk.risk_level == "high":
        prefix = "HIGH RISK"
    elif risk.risk_level == "medium":
        prefix = "WARNING"
    else:
        prefix = "INFO"

    measures_str = ", ".join(risk.affected_measures[:3])
    if len(risk.affected_measures) > 3:
        measures_str += f" (+{len(risk.affected_measures) - 3} more)"

    return (
        f"[{prefix}] {rel.from_table} -> {rel.to_table}: "
        f"Aggregating {measures_str}{inflation_str} may be inflated when grouped by "
        f"{from_table.view} columns. {risk.recommendation}"
    )


def get_safe_aggregations(
    table_name: str,
    column_name: str,
    relationships: list[RelationshipMetadata],
    tables_metadata: list[SemanticViewMetadata]
) -> dict[str, bool]:
    """
    Return which aggregation functions are safe for a column given relationships.

    Args:
        table_name: Table containing the column
        column_name: Column to check
        relationships: List of relationships
        tables_metadata: Metadata for all tables

    Returns:
        Dictionary mapping aggregation function to safety (True = safe)
    """
    # Find relationships where this table is on the "one" side (to_table)
    risky_relationships = [
        rel for rel in relationships
        if rel.to_table == table_name
        and rel.cardinality
        and rel.cardinality.to_cardinality == "one"
        and rel.cardinality.from_cardinality == "many"
    ]

    if not risky_relationships:
        # No risky relationships, all aggregations are safe
        return {
            "SUM": True,
            "AVG": True,
            "COUNT": True,
            "MIN": True,
            "MAX": True,
            "DISTINCTCOUNT": True
        }

    # Check if column is in affected measures
    is_affected = any(
        rel.fan_out_risk and column_name in rel.fan_out_risk.affected_measures
        for rel in risky_relationships
    )

    if not is_affected:
        return {
            "SUM": True,
            "AVG": True,
            "COUNT": True,
            "MIN": True,
            "MAX": True,
            "DISTINCTCOUNT": True
        }

    # Column is affected by fan-out
    return {
        "SUM": False,      # Will be inflated
        "AVG": False,      # Will be wrong due to duplicated rows
        "COUNT": False,    # Will be inflated
        "MIN": True,       # Safe - returns same value regardless of duplicates
        "MAX": True,       # Safe - returns same value regardless of duplicates
        "DISTINCTCOUNT": True  # Safe - counts distinct values
    }


def suggest_fix_for_fan_out(
    relationship: RelationshipMetadata,
    from_table_metadata: SemanticViewMetadata,
    to_table_metadata: SemanticViewMetadata
) -> list[str]:
    """
    Suggest fixes for a fan-out issue.

    Args:
        relationship: The problematic relationship
        from_table_metadata: Metadata for the from (many) table
        to_table_metadata: Metadata for the to (one) table

    Returns:
        List of suggested fixes
    """
    suggestions = []

    if not relationship.fan_out_risk:
        return suggestions

    risk = relationship.fan_out_risk
    if risk.risk_level == "none":
        return suggestions

    # Suggestion 1: Use DISTINCTCOUNT for counting
    suggestions.append(
        f"Use DISTINCTCOUNT({to_table_metadata.view}_KEY) instead of COUNT(*) "
        f"when counting {to_table_metadata.view} records"
    )

    # Suggestion 2: Create a bridge table
    if risk.affected_measures:
        measures_str = ", ".join(risk.affected_measures[:2])
        suggestions.append(
            f"Create a bridge table that pre-aggregates {measures_str} "
            f"at the {to_table_metadata.view} level before joining"
        )

    # Suggestion 3: Change relationship direction
    suggestions.append(
        f"Configure the relationship to filter from {to_table_metadata.view} "
        f"to {from_table_metadata.view} (single direction)"
    )

    # Suggestion 4: Use a different grouping strategy
    suggestions.append(
        f"Group by {to_table_metadata.view} attributes first, then join "
        f"to {from_table_metadata.view} for additional details"
    )

    return suggestions


def calculate_expected_inflation(
    relationships: list[RelationshipMetadata],
    grouping_columns: list[tuple[str, str]],  # (table_name, column_name)
    measure_columns: list[tuple[str, str]]    # (table_name, column_name)
) -> dict[str, float]:
    """
    Calculate expected inflation for each measure based on grouping columns.

    Args:
        relationships: List of relationships
        grouping_columns: List of (table_name, column_name) tuples for grouping
        measure_columns: List of (table_name, column_name) tuples for measures

    Returns:
        Dictionary mapping "table.column" to expected inflation factor
    """
    inflation_factors: dict[str, float] = {}

    grouping_tables = {table for table, _ in grouping_columns}
    measure_tables = {table for table, _ in measure_columns}

    for measure_table, measure_col in measure_columns:
        key = f"{measure_table}.{measure_col}"

        # Find relationships where measure table is on "one" side
        # and grouping table is on "many" side
        for rel in relationships:
            if rel.to_table == measure_table and rel.from_table in grouping_tables:
                if rel.cardinality and rel.cardinality.avg_rows_per_key:
                    # Accumulate inflation from all such relationships
                    current = inflation_factors.get(key, 1.0)
                    inflation_factors[key] = current * rel.cardinality.avg_rows_per_key

        # Default to 1.0 if no inflation detected
        if key not in inflation_factors:
            inflation_factors[key] = 1.0

    return inflation_factors


def detect_relationship_issue_type(
    relationship: RelationshipMetadata,
    from_table_metadata: SemanticViewMetadata,
    to_table_metadata: SemanticViewMetadata
) -> RelationshipIssue:
    """
    Detect whether a relationship has fan-out risk or is a true M:M relationship.

    This is critical for recommending the correct solution:
    - Fan-Out (many:one): Solved by Snowflake Semantic Views or DAX (Import only)
    - M:M (many:many): Solved by Bridge Tables

    Args:
        relationship: The relationship to analyze
        from_table_metadata: Metadata for the "from" (source) table
        to_table_metadata: Metadata for the "to" (target) table

    Returns:
        RelationshipIssue with categorized issue type and appropriate solutions.
    """
    cardinality = relationship.cardinality

    if not cardinality:
        # Unknown cardinality - check if there's already computed fan_out_risk
        if relationship.fan_out_risk and relationship.fan_out_risk.risk_level != "none":
            # Fan-out risk was detected by other means
            return RelationshipIssue(
                issue_type="fan_out",
                relationship=relationship,
                reason="Potential fan-out risk detected (cardinality unknown)",
                solutions=["semantic_view"],  # Safe default for DirectQuery
                affected_measures=relationship.fan_out_risk.affected_measures,
                inflation_factor=relationship.fan_out_risk.inflation_factor
            )
        # No cardinality info and no known risk
        return RelationshipIssue(
            issue_type="none",
            relationship=relationship,
            reason="Cardinality unknown - no issue detected",
            solutions=[]
        )

    # M:M: Both sides are "many" - this is where bridge tables help
    if cardinality.from_cardinality == "many" and cardinality.to_cardinality == "many":
        return RelationshipIssue(
            issue_type="many_to_many",
            relationship=relationship,
            reason=f"Many-to-many relationship: {from_table_metadata.view} (*) ↔ (*) {to_table_metadata.view}",
            solutions=["bridge_table"]
        )

    # Fan-Out: many:one relationship (from has many, to has one)
    if cardinality.from_cardinality == "many" and cardinality.to_cardinality == "one":
        # Find affected measures on the "one" side (to_table)
        affected = _find_potential_measures(to_table_metadata)

        if not affected:
            return RelationshipIssue(
                issue_type="none",
                relationship=relationship,
                reason="No numeric measures found on 'one' side - no fan-out risk",
                solutions=[]
            )

        # Use existing fan_out_risk if available for inflation factor
        inflation = None
        if relationship.fan_out_risk:
            inflation = relationship.fan_out_risk.inflation_factor

        return RelationshipIssue(
            issue_type="fan_out",
            relationship=relationship,
            reason=f"Fan-out risk: Aggregating from {to_table_metadata.view} while grouping by {from_table_metadata.view}",
            solutions=["semantic_view"],  # DAX added conditionally in UI based on mode
            affected_measures=affected,
            inflation_factor=inflation or cardinality.avg_rows_per_key
        )

    # One:Many (reverse direction) - the "from" side has measures that could be affected
    if cardinality.from_cardinality == "one" and cardinality.to_cardinality == "many":
        # This is actually safe direction - aggregating from "one" and grouping by itself
        # But check if there's a computed fan_out_risk
        if relationship.fan_out_risk and relationship.fan_out_risk.risk_level != "none":
            return RelationshipIssue(
                issue_type="fan_out",
                relationship=relationship,
                reason=relationship.fan_out_risk.reason,
                solutions=["semantic_view"],
                affected_measures=relationship.fan_out_risk.affected_measures,
                inflation_factor=relationship.fan_out_risk.inflation_factor
            )

    # One:One or no risk detected
    return RelationshipIssue(
        issue_type="none",
        relationship=relationship,
        reason="No fan-out risk for this cardinality",
        solutions=[]
    )


def _find_potential_measures(table_metadata: SemanticViewMetadata) -> list[str]:
    """
    Find numeric columns that could be affected by fan-out.

    Excludes key columns (IDs, foreign keys) as they're not typically aggregated.
    """
    numeric_types = {
        "NUMBER", "DECIMAL", "NUMERIC", "INT", "INTEGER", "BIGINT",
        "SMALLINT", "FLOAT", "DOUBLE", "REAL", "FLOAT4", "FLOAT8",
        "DOUBLE PRECISION"
    }
    affected = []

    for col in table_metadata.columns:
        # Extract base type (before parentheses for precision/scale)
        col_type_upper = col.data_type.upper().split("(")[0].strip()

        if col_type_upper not in numeric_types:
            continue

        # Exclude key columns - they're not typically aggregated
        col_upper = col.name.upper()
        is_key = (
            col.is_primary_key or
            getattr(col, 'is_foreign_key', False) or
            col_upper.endswith("_ID") or
            col_upper.endswith("_KEY") or
            col_upper.endswith("KEY") or
            col_upper.startswith("FK_") or
            col_upper.startswith("PK_") or
            ("KEY" in col_upper and len(col_upper) < 20)  # Avoid matching "MONKEY" etc.
        )

        if not is_key:
            affected.append(col.name)

    return affected
