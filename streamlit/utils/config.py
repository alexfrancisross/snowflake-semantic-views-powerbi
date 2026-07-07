"""
Centralized configuration constants for the Power BI Semantic Model Generator.

This module consolidates all magic values, constants, and configuration
settings that were previously scattered throughout the codebase.

Usage:
    from config import CONFIG, WIZARD_STEPS, OBJECT_TYPES
"""

from dataclasses import dataclass, field
from typing import Literal


# =============================================================================
# APPLICATION CONFIGURATION
# =============================================================================

@dataclass(frozen=True)
class AppConfig:
    """Immutable application configuration.

    All configuration values are defined here for easy maintenance.
    Using frozen=True ensures values cannot be accidentally modified.
    """

    # App metadata
    APP_NAME: str = "Power BI Semantic Model Generator"
    APP_VERSION: str = "3.3.0"
    APP_ICON: str = "snowflake"

    # Cache settings (in seconds)
    CACHE_TTL_DATABASE: int = 300      # 5 minutes for database/schema lists
    CACHE_TTL_METADATA: int = 60       # 1 minute for object metadata
    CACHE_TTL_SESSION: int = 3600      # 1 hour for session info

    # PBIT generation
    PBIT_VERSION: str = "1.28"
    PBIT_THEME_NAME: str = "CY25SU11"

    # UI settings
    MAX_TREE_DEPTH: int = 3            # Database -> Schema -> Object
    DEFAULT_PAGE_SIZE: int = 1000
    SIDEBAR_WIDTH: int = 300

    # Wizard steps: Review (0) -> Model (1) -> Generate (2). "Select Objects"
    # lives in the sidebar rather than as a wizard step, and the standalone
    # "Semantic" step was retired (step_semantic.py is dead code / removed) -
    # these constants must match the 3-entry WIZARD_STEPS tuple below.
    WIZARD_STEP_REVIEW: int = 0
    WIZARD_STEP_MODEL: int = 1
    WIZARD_STEP_GENERATE: int = 2
    WIZARD_TOTAL_STEPS: int = 3

    # Snowflake identifier limits
    MAX_IDENTIFIER_LENGTH: int = 255

    # Data model settings
    DEFAULT_PBI_MODE: str = "DirectQuery"
    SUPPORTED_PBI_MODES: tuple = ("DirectQuery", "Import")

    # File size limits
    MAX_PBIT_SIZE_MB: int = 100


# Singleton instance
CONFIG = AppConfig()


# =============================================================================
# WIZARD STEP DEFINITIONS
# =============================================================================

@dataclass(frozen=True)
class WizardStep:
    """Definition of a wizard step."""
    index: int
    name: str
    short_name: str
    description: str
    icon: str


WIZARD_STEPS = (
    WizardStep(
        index=0,
        name="Review Selected Objects",
        short_name="Review",
        description="Review selected objects and their metadata",
        icon="verified"
    ),
    WizardStep(
        index=1,
        name="Design Data Model",
        short_name="Model",
        description="Configure relationships and data model settings",
        icon="data_engineering"
    ),
    WizardStep(
        index=2,
        name="Download PBI Workbook",
        short_name="Download",
        description="Generate and download your Power BI workbook",
        icon="download"
    ),
)


def get_wizard_step_by_index(index: int) -> WizardStep | None:
    """Get wizard step definition by index.

    Args:
        index: Step index (0-3)

    Returns:
        WizardStep if found, None otherwise
    """
    for step in WIZARD_STEPS:
        if step.index == index:
            return step
    return None


# =============================================================================
# OBJECT TYPE DEFINITIONS
# =============================================================================

# Type alias for object types
ObjectTypeLiteral = Literal["SEMANTIC_VIEW", "VIEW", "TABLE"]


@dataclass(frozen=True)
class ObjectTypeConfig:
    """Configuration for a Snowflake object type."""
    name: str
    display_name: str
    icon_key: str
    color_primary: str
    color_background: str
    connector_type: str  # "custom" or "native"


OBJECT_TYPES: dict[str, ObjectTypeConfig] = {
    "SEMANTIC_VIEW": ObjectTypeConfig(
        name="SEMANTIC_VIEW",
        display_name="Semantic View",
        icon_key="cube",
        color_primary="#7254A3",      # Purple Moon
        color_background="#F0EBF8",
        connector_type="custom"
    ),
    "TABLE": ObjectTypeConfig(
        name="TABLE",
        display_name="Table",
        icon_key="table",
        color_primary="#75CDD7",      # Star Blue
        color_background="#E8F6F7",
        connector_type="native"
    ),
    "VIEW": ObjectTypeConfig(
        name="VIEW",
        display_name="View",
        icon_key="view",
        color_primary="#FF9F36",      # Valencia Orange
        color_background="#FFF5E6",
        connector_type="native"
    ),
}


def get_object_type_config(object_type: str) -> ObjectTypeConfig:
    """Get configuration for an object type.

    Args:
        object_type: Snowflake object type string

    Returns:
        ObjectTypeConfig, defaults to TABLE if not found
    """
    return OBJECT_TYPES.get(object_type, OBJECT_TYPES["TABLE"])


# =============================================================================
# AGGREGATION DEFINITIONS
# =============================================================================

# Supported aggregations in Snowflake semantic views
SNOWFLAKE_AGGREGATIONS = (
    "SUM",
    "AVG",
    "COUNT",
    "MIN",
    "MAX",
    "COUNT_DISTINCT",
    "MEDIAN",
    "STDDEV",
    "VARIANCE",
)

# Default aggregation for new metrics
DEFAULT_AGGREGATION = "SUM"


# =============================================================================
# COLUMN KIND DEFINITIONS
# =============================================================================

@dataclass(frozen=True)
class ColumnKindConfig:
    """Configuration for a semantic column kind."""
    name: str
    display_name: str
    description: str
    color: str
    can_aggregate: bool


COLUMN_KINDS: dict[str, ColumnKindConfig] = {
    "DIMENSION": ColumnKindConfig(
        name="DIMENSION",
        display_name="Dimension",
        description="Categorical attribute for grouping/filtering",
        color="#29B5E8",  # Snowflake Blue
        can_aggregate=False
    ),
    "METRIC": ColumnKindConfig(
        name="METRIC",
        display_name="Metric",
        description="Pre-aggregated numeric measure",
        color="#34C759",  # Success Green
        can_aggregate=True
    ),
    "FACT": ColumnKindConfig(
        name="FACT",
        display_name="Fact",
        description="Raw numeric value at detail level",
        color="#FF9F36",  # Valencia Orange
        can_aggregate=True
    ),
    "COLUMN": ColumnKindConfig(
        name="COLUMN",
        display_name="Column",
        description="Regular table/view column",
        color="#8A8A8A",  # Gray
        can_aggregate=True
    ),
}


# =============================================================================
# RELATIONSHIP CARDINALITY
# =============================================================================

CARDINALITY_TYPES = {
    "one-to-one": {"from": "one", "to": "one", "symbol": "1:1"},
    "one-to-many": {"from": "one", "to": "many", "symbol": "1:N"},
    "many-to-one": {"from": "many", "to": "one", "symbol": "N:1"},
    "many-to-many": {"from": "many", "to": "many", "symbol": "M:N"},
}


# =============================================================================
# FAN-OUT RISK LEVELS
# =============================================================================

@dataclass(frozen=True)
class RiskLevelConfig:
    """Configuration for a fan-out risk level."""
    name: str
    display_name: str
    color: str
    description: str


RISK_LEVELS: dict[str, RiskLevelConfig] = {
    "none": RiskLevelConfig(
        name="none",
        display_name="None",
        color="#34C759",
        description="No fan-out risk detected"
    ),
    "low": RiskLevelConfig(
        name="low",
        display_name="Low",
        color="#34C759",
        description="Minimal risk of measure inflation"
    ),
    "medium": RiskLevelConfig(
        name="medium",
        display_name="Medium",
        color="#FF9F36",
        description="Moderate risk - review relationship direction"
    ),
    "high": RiskLevelConfig(
        name="high",
        display_name="High",
        color="#DC3545",
        description="High risk of incorrect aggregations"
    ),
    "critical": RiskLevelConfig(
        name="critical",
        display_name="Critical",
        color="#DC3545",
        description="Significant measure inflation expected"
    ),
}
