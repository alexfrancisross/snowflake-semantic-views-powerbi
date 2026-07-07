"""
Relationship Management Module

Provides utilities for creating manual relationships between tables.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from .metadata_fetcher import RelationshipMetadata, CardinalityInfo


class SuggestionSource(Enum):
    """Source of a relationship."""
    FK_CONSTRAINT = "fk_constraint"      # From Snowflake SHOW IMPORTED KEYS
    MANUAL = "manual"                    # User-created manually


@dataclass
class SuggestedRelationship:
    """A relationship with source information.

    Supports both single-column and composite (multi-column) foreign keys.
    For composite keys, from_columns and to_columns contain multiple column names.

    Backwards compatible: accepts either string or list for column parameters.
    """
    from_table: str
    from_columns: str | list[str]  # Accepts string or list for backwards compat
    to_table: str
    to_columns: str | list[str]  # Accepts string or list for backwards compat
    confidence: float  # 0.0 to 1.0
    source: SuggestionSource
    match_reason: str = ""  # Human-readable explanation
    name: str | None = None
    # Full qualified names (optional)
    from_database: str | None = None
    from_schema: str | None = None
    to_database: str | None = None
    to_schema: str | None = None
    # Cardinality (optional - for manual relationships)
    from_cardinality: Literal["one", "many"] | None = None
    to_cardinality: Literal["one", "many"] | None = None

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

    def to_relationship_metadata(self) -> "RelationshipMetadata":
        """Convert to standard RelationshipMetadata."""
        from .metadata_fetcher import RelationshipMetadata, CardinalityInfo

        # Build cardinality if specified
        cardinality = None
        if self.from_cardinality and self.to_cardinality:
            cardinality = CardinalityInfo(
                from_cardinality=self.from_cardinality,
                to_cardinality=self.to_cardinality,
                detected_by="manual",
                confidence=1.0,
            )

        return RelationshipMetadata(
            name=self.name,
            from_table=self.from_table,
            from_columns=self.from_columns,
            to_table=self.to_table,
            to_columns=self.to_columns,
            from_database=self.from_database,
            from_schema=self.from_schema,
            to_database=self.to_database,
            to_schema=self.to_schema,
            cardinality=cardinality,
        )


def create_manual_relationship(
    from_table: str,
    from_columns: str | list[str],
    to_table: str,
    to_columns: str | list[str],
    from_database: str | None = None,
    from_schema: str | None = None,
    to_database: str | None = None,
    to_schema: str | None = None,
    from_cardinality: Literal["one", "many"] = "many",
    to_cardinality: Literal["one", "many"] = "one",
) -> SuggestedRelationship:
    """Create a manually specified relationship.

    Supports both single-column and composite (multi-column) foreign keys.

    Args:
        from_table: Source table name
        from_columns: Source column name(s) - string or list for composite keys
        to_table: Target table name
        to_columns: Target column name(s) - string or list for composite keys
        from_database: Source database (optional)
        from_schema: Source schema (optional)
        to_database: Target database (optional)
        to_schema: Target schema (optional)
        from_cardinality: Cardinality on source side ("one" or "many", default "many")
        to_cardinality: Cardinality on target side ("one" or "many", default "one")

    Returns:
        SuggestedRelationship with MANUAL source and confidence 1.0

    Examples:
        # Single column relationship
        create_manual_relationship("ORDERS", "O_CUSTKEY", "CUSTOMER", "C_CUSTKEY")

        # Composite key relationship
        create_manual_relationship(
            "LINEITEM", ["L_PARTKEY", "L_SUPPKEY"],
            "PARTSUPP", ["PS_PARTKEY", "PS_SUPPKEY"]
        )
    """
    # Normalize to lists
    from_cols = [from_columns] if isinstance(from_columns, str) else list(from_columns)
    to_cols = [to_columns] if isinstance(to_columns, str) else list(to_columns)

    return SuggestedRelationship(
        from_table=from_table,
        from_columns=from_cols,
        to_table=to_table,
        to_columns=to_cols,
        confidence=1.0,
        source=SuggestionSource.MANUAL,
        match_reason="Manually created by user",
        from_database=from_database,
        from_schema=from_schema,
        to_database=to_database,
        to_schema=to_schema,
        from_cardinality=from_cardinality,
        to_cardinality=to_cardinality,
    )
