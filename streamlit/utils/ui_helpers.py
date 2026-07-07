"""
Shared UI helper functions for the Power BI Semantic Model Generator.

This module consolidates duplicated UI utility functions from:
- streamlit_app.py
- pages/step_select.py
- pages/step_review.py
- pages/step_generate.py

Usage:
    from ui_helpers import (
        generate_project_name,
        get_object_icon_key,
        get_object_icon_html,
        get_connector_badge_html,
        display_column_metadata,
    )
"""

from datetime import datetime
from typing import TYPE_CHECKING

import pandas as pd
import streamlit as st

from .snowflake_theme import get_svg_icon

if TYPE_CHECKING:
    from .metadata_fetcher import SemanticViewMetadata


# =============================================================================
# ICON HELPERS
# =============================================================================

# Mapping of Snowflake object types to icon keys
OBJECT_TYPE_ICONS = {
    "SEMANTIC_VIEW": "cube",
    "VIEW": "view",
    "TABLE": "table",
}


def get_object_icon_key(object_type: str) -> str:
    """Get the icon key for a Snowflake object type.

    Maps Snowflake object types to icon keys:
        - SEMANTIC_VIEW -> cube (purple)
        - VIEW -> view (orange)
        - TABLE -> table (cyan)

    Args:
        object_type: Snowflake object type string (SEMANTIC_VIEW, VIEW, TABLE)

    Returns:
        Icon key string for use with get_svg_icon().
    """
    return OBJECT_TYPE_ICONS.get(object_type, "table")


def get_object_icon_html(object_type: str, size: int = 18) -> str:
    """Get HTML img tag with SVG icon for a Snowflake object type.

    Convenience function combining get_object_icon_key() and get_svg_icon().

    Args:
        object_type: Snowflake object type (SEMANTIC_VIEW, VIEW, TABLE)
        size: Icon size in pixels (default 18)

    Returns:
        HTML img tag string with the appropriate icon.
    """
    icon_key = get_object_icon_key(object_type)
    return get_svg_icon(icon_key, size)


# =============================================================================
# CONNECTOR BADGES
# =============================================================================

# Badge styles following Snowflake Design System colors
CONNECTOR_BADGE_STYLES = {
    "custom": {
        "bg_color": "#D4EDDA",
        "text_color": "#155724",
        "label": "Custom Connector",
    },
    "native": {
        "bg_color": "#D1ECF1",
        "text_color": "#0C5460",
        "label": "Native Connector",
    },
}


def get_connector_badge_html(object_type: str) -> str:
    """Get HTML badge indicating which connector will be used.

    v3.0: Semantic views use custom connector, standard tables use native.

    Args:
        object_type: Type of object (SEMANTIC_VIEW, VIEW, TABLE)

    Returns:
        HTML badge string with Snowflake Design System colors.
    """
    style = (
        CONNECTOR_BADGE_STYLES["custom"]
        if object_type == "SEMANTIC_VIEW"
        else CONNECTOR_BADGE_STYLES["native"]
    )

    return (
        f'<span style="background-color: {style["bg_color"]}; '
        f'color: {style["text_color"]}; padding: 2px 8px; border-radius: 8px; '
        f'font-size: 0.75em; font-weight: 600; margin-left: 8px;">'
        f'{style["label"]}</span>'
    )


def get_connector_badge(object_type: str) -> str:
    """Get a text connector badge with emoji indicator.

    Args:
        object_type: Type of object (SEMANTIC_VIEW, VIEW, TABLE)

    Returns:
        Badge string with colored emoji indicator.
    """
    if object_type == "SEMANTIC_VIEW":
        return "Custom Connector"
    return "Native Connector"


# =============================================================================
# PROJECT NAMING
# =============================================================================

def generate_project_name(views_metadata: list) -> str:
    """Generate a meaningful project name based on selected objects.

    Format (using dots as delimiters like Snowflake notation):
    - Single object: {DB}.{SCHEMA}.{OBJECT}_{YYYYMMDD}
    - Multiple objects: {DB}.{SCHEMA}.{N}_OBJECTS_{YYYYMMDD}
    - No objects: SnowflakePowerBI_{YYYYMMDD}

    Args:
        views_metadata: List of SemanticViewMetadata objects

    Returns:
        Generated project name string.
    """
    date_suffix = datetime.now().strftime("%Y%m%d")

    if not views_metadata:
        return f"SnowflakePowerBI_{date_suffix}"

    # Get first object's metadata
    first = views_metadata[0]
    db = first.database
    schema = first.schema
    obj_name = first.view

    if len(views_metadata) == 1:
        # Single object: DB.SCHEMA.OBJECT_DATE
        return f"{db}.{schema}.{obj_name}_{date_suffix}"
    else:
        # Multiple objects: DB.SCHEMA.N_OBJECTS_DATE
        count = len(views_metadata)
        return f"{db}.{schema}.{count}_OBJECTS_{date_suffix}"


# =============================================================================
# METADATA DISPLAY
# =============================================================================

def display_column_metadata(metadata: "SemanticViewMetadata") -> None:
    """Display column metadata in a dataframe.

    Shows column name, data type, and optionally kind (for semantic views)
    and description.

    Args:
        metadata: SemanticViewMetadata object containing column info.
    """
    columns_data = []
    for col in metadata.columns:
        row_data = {
            "Column": col.name,
            "Type": col.data_type,
        }
        # Only show Kind for semantic views
        if metadata.object_type == "SEMANTIC_VIEW":
            row_data["Kind"] = col.kind
        row_data["Description"] = col.description or "-"
        columns_data.append(row_data)

    if columns_data:
        df = pd.DataFrame(columns_data)
        st.dataframe(df, width='stretch', hide_index=True)
    else:
        object_name = (
            "semantic view"
            if metadata.object_type == "SEMANTIC_VIEW"
            else metadata.object_type.lower()
        )
        st.info(f"No columns found in this {object_name}.")
