"""
Column Zone Selector Component for Power BI Semantic Model Generator.

This component provides a three-zone column selector (Dimensions, Metrics, Facts)
for assigning columns to semantic view zones. It uses smart defaults based on
column metadata and allows user customization of assignments.

Usage:
    from components.column_selector import ColumnSelector, render_column_zones

    # Using the class interface
    selector = ColumnSelector(columns, key_prefix="my_table")
    configs = selector.render()

    # Using the function interface
    configs = render_column_zones(columns, "my_table", is_base_table=True)
"""

from dataclasses import dataclass, field
from typing import Any
import streamlit as st

from tooltips import dimensions_label, metrics_label, facts_label
from snowflake_theme import get_svg_icon
from snowflake_ddl_generator import SemanticColumnConfig, SNOWFLAKE_AGGREGATIONS
from logging_config import get_logger

logger = get_logger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class ColumnZoneConfig:
    """Configuration for the column zone selector."""

    disable_metrics: bool = False
    """If True, disable the metrics zone (for dimension tables)."""

    disable_facts: bool = False
    """If True, disable the facts zone."""

    is_base_table: bool = True
    """If True, this is the base/fact table (metrics allowed)."""

    affected_measures: list[str] = field(default_factory=list)
    """Optional list of columns detected as affected by fan-out."""

    show_descriptions: bool = True
    """If True, show the column descriptions expander."""

    show_aggregations: bool = True
    """If True, show aggregation dropdowns for metrics."""


# =============================================================================
# COLUMN CLASSIFICATION HELPERS
# =============================================================================

def is_numeric_type(data_type: str | None) -> bool:
    """Check if a data type is numeric.

    Args:
        data_type: The Snowflake data type string

    Returns:
        True if the type is numeric
    """
    if not data_type:
        return False
    dtype = data_type.upper()
    return any(t in dtype for t in [
        "NUMBER", "DECIMAL", "FLOAT", "DOUBLE", "INT", "NUMERIC"
    ])


def is_date_type(data_type: str | None) -> bool:
    """Check if a data type is date/time.

    Args:
        data_type: The Snowflake data type string

    Returns:
        True if the type is date/time
    """
    if not data_type:
        return False
    dtype = data_type.upper()
    return "DATE" in dtype or "TIME" in dtype


def is_string_type(data_type: str | None) -> bool:
    """Check if a data type is string/text.

    Args:
        data_type: The Snowflake data type string

    Returns:
        True if the type is string/text
    """
    if not data_type:
        return False
    dtype = data_type.upper()
    return any(t in dtype for t in ["VARCHAR", "CHAR", "STRING", "TEXT"])


def is_key_column(column_name: str, is_primary_key: bool = False) -> bool:
    """Check if a column appears to be a key column.

    Args:
        column_name: The column name
        is_primary_key: Whether the column is a primary key

    Returns:
        True if the column appears to be a key
    """
    if is_primary_key:
        return True
    name_upper = column_name.upper()
    return "KEY" in name_upper or name_upper.endswith("_ID")


def classify_column(
    column: Any,
    is_base_table: bool = True,
    disable_metrics: bool = False
) -> str:
    """Classify a column into a semantic zone.

    Args:
        column: Column metadata object with name, data_type, is_primary_key
        is_base_table: Whether this is the base/fact table
        disable_metrics: Whether metrics are disabled

    Returns:
        Zone name: "DIMENSION", "METRIC", or "FACT"
    """
    # Primary keys and key columns are always dimensions
    is_pk = getattr(column, 'is_primary_key', False)
    if is_key_column(column.name, is_pk):
        return "DIMENSION"

    # Numeric columns: metrics on base table, dimensions otherwise
    data_type = getattr(column, 'data_type', None)
    if is_numeric_type(data_type):
        if is_base_table and not disable_metrics:
            return "METRIC"
        return "DIMENSION"

    # Date columns are dimensions
    if is_date_type(data_type):
        return "DIMENSION"

    # String columns are dimensions
    if is_string_type(data_type):
        return "DIMENSION"

    # Default: dimension (ensure all columns are assigned)
    return "DIMENSION"


# =============================================================================
# COLUMN SELECTOR STATE
# =============================================================================

@dataclass
class ColumnZoneState:
    """State for column zone selections."""

    dimensions: list[str] = field(default_factory=list)
    metrics: list[str] = field(default_factory=list)
    facts: list[str] = field(default_factory=list)
    aggregations: dict[str, str] = field(default_factory=dict)
    descriptions: dict[str, str] = field(default_factory=dict)

    @property
    def all_selected(self) -> list[str]:
        """Get all selected column names."""
        return self.dimensions + self.metrics + self.facts

    @property
    def count(self) -> int:
        """Get total number of selected columns."""
        return len(self.all_selected)


# =============================================================================
# COLUMN SELECTOR COMPONENT
# =============================================================================

class ColumnSelector:
    """Three-zone column selector component.

    Renders a UI for assigning columns to Dimensions, Metrics, and Facts zones
    with smart defaults based on column metadata.

    Attributes:
        columns: List of column metadata objects
        key_prefix: Unique prefix for widget keys
        config: Configuration options
        state: Current selection state
    """

    def __init__(
        self,
        columns: list[Any],
        key_prefix: str,
        config: ColumnZoneConfig | None = None,
    ):
        """Initialize the column selector.

        Args:
            columns: List of column metadata objects (must have name, data_type)
            key_prefix: Unique prefix for Streamlit widget keys
            config: Optional configuration
        """
        self.columns = columns
        self.key_prefix = key_prefix
        self.config = config or ColumnZoneConfig()

        # Build column lookups
        self._column_names = [c.name for c in columns]
        self._column_info = {c.name: c for c in columns}

        # Initialize state from session
        self._init_state()

    def _init_state(self) -> None:
        """Initialize state from session state or compute defaults."""
        dims_key = f"{self.key_prefix}_dimensions"
        metrics_key = f"{self.key_prefix}_metrics"
        facts_key = f"{self.key_prefix}_facts"

        # Check if state already exists
        if dims_key in st.session_state:
            return

        # Compute smart defaults
        default_dims = []
        default_metrics = []
        default_facts = []

        for col in self.columns:
            kind = classify_column(
                col,
                is_base_table=self.config.is_base_table,
                disable_metrics=self.config.disable_metrics
            )
            if kind == "DIMENSION":
                default_dims.append(col.name)
            elif kind == "METRIC":
                default_metrics.append(col.name)
            elif kind == "FACT":
                default_facts.append(col.name)

        # Store defaults in session state
        st.session_state[dims_key] = default_dims
        st.session_state[metrics_key] = default_metrics
        st.session_state[facts_key] = default_facts

        logger.debug(
            f"Initialized column zones for {self.key_prefix}: "
            f"{len(default_dims)} dims, {len(default_metrics)} metrics, {len(default_facts)} facts"
        )

    def _get_column_label(self, col: Any) -> str:
        """Create display label for a column.

        Args:
            col: Column metadata object

        Returns:
            Display label string
        """
        label = col.name
        if getattr(col, 'is_primary_key', False):
            label += " 🔑"
        return label

    def _render_dimensions_zone(self) -> list[str]:
        """Render the dimensions zone.

        Returns:
            List of selected dimension column names
        """
        dims_key = f"{self.key_prefix}_dimensions"

        st.markdown(f"**{get_svg_icon('analytics', 16)} {dimensions_label()}**", unsafe_allow_html=True)
        st.caption("Attributes to group by")

        selected = st.multiselect(
            "Dimensions",
            options=self._column_names,
            default=st.session_state.get(dims_key, []),
            key=f"{self.key_prefix}_dim_select",
            label_visibility="collapsed",
        )

        st.session_state[dims_key] = selected
        return selected

    def _render_metrics_zone(self, selected_dims: list[str]) -> list[str]:
        """Render the metrics zone.

        Args:
            selected_dims: Currently selected dimensions (excluded from metrics)

        Returns:
            List of selected metric column names
        """
        metrics_key = f"{self.key_prefix}_metrics"

        st.markdown(f"**{get_svg_icon('analytics', 16)} {metrics_label()}**", unsafe_allow_html=True)
        st.caption("Measures to aggregate")

        if self.config.disable_metrics:
            st.warning("⊘ Metrics disabled (dimension table)")
            return []

        # Filter out columns already in dimensions
        available = [c for c in self._column_names if c not in selected_dims]
        current = [m for m in st.session_state.get(metrics_key, []) if m in available]

        selected = st.multiselect(
            "Metrics",
            options=available,
            default=current,
            key=f"{self.key_prefix}_metric_select",
            label_visibility="collapsed",
        )

        # Aggregation dropdowns for each selected metric
        if selected and self.config.show_aggregations:
            st.markdown("*Aggregations:*")
            for metric_name in selected:
                self._render_aggregation_dropdown(metric_name)

        st.session_state[metrics_key] = selected
        return selected

    def _render_aggregation_dropdown(self, metric_name: str) -> None:
        """Render aggregation dropdown for a metric.

        Args:
            metric_name: Name of the metric column
        """
        agg_key = f"{self.key_prefix}_agg_{metric_name}"

        if agg_key not in st.session_state:
            st.session_state[agg_key] = "SUM"

        current_agg = st.session_state[agg_key]
        agg_index = (
            SNOWFLAKE_AGGREGATIONS.index(current_agg)
            if current_agg in SNOWFLAKE_AGGREGATIONS
            else 0
        )

        selected_agg = st.selectbox(
            metric_name,
            options=SNOWFLAKE_AGGREGATIONS,
            index=agg_index,
            key=f"{self.key_prefix}_agg_select_{metric_name}",
        )

        st.session_state[agg_key] = selected_agg

    def _render_facts_zone(
        self,
        selected_dims: list[str],
        selected_metrics: list[str]
    ) -> list[str]:
        """Render the facts zone.

        Args:
            selected_dims: Currently selected dimensions
            selected_metrics: Currently selected metrics

        Returns:
            List of selected fact column names
        """
        facts_key = f"{self.key_prefix}_facts"

        st.markdown(f"**{get_svg_icon('docs', 16)} {facts_label()}**", unsafe_allow_html=True)
        st.caption("Detail-level data")

        if self.config.disable_facts:
            st.warning("⊘ Facts disabled (dimension table)")
            return []

        # Filter out columns already in dimensions or metrics
        available = [
            c for c in self._column_names
            if c not in selected_dims and c not in selected_metrics
        ]
        current = [f for f in st.session_state.get(facts_key, []) if f in available]

        selected = st.multiselect(
            "Facts",
            options=available,
            default=current,
            key=f"{self.key_prefix}_fact_select",
            label_visibility="collapsed",
        )

        st.session_state[facts_key] = selected
        return selected

    def _render_descriptions(
        self,
        selected_dims: list[str],
        selected_metrics: list[str],
        selected_facts: list[str],
    ) -> None:
        """Render the column descriptions expander.

        Args:
            selected_dims: Selected dimension columns
            selected_metrics: Selected metric columns
            selected_facts: Selected fact columns
        """
        all_selected = selected_dims + selected_metrics + selected_facts

        if not all_selected or not self.config.show_descriptions:
            return

        with st.expander("Column Descriptions", expanded=False):
            st.caption("Override descriptions from Snowflake metadata")

            for col_name in all_selected:
                col = self._column_info[col_name]

                # Get metadata description if available
                metadata_desc = ""
                if hasattr(col, 'description') and col.description:
                    metadata_desc = col.description

                # Session state key for overridden description
                desc_key = f"{self.key_prefix}_desc_{col_name}"
                if desc_key not in st.session_state:
                    st.session_state[desc_key] = metadata_desc

                # Determine icon based on zone
                if col_name in selected_dims:
                    icon = "📊"
                elif col_name in selected_metrics:
                    icon = "📈"
                else:
                    icon = "📝"

                desc_value = st.text_input(
                    f"{icon} {col_name}",
                    value=st.session_state[desc_key],
                    placeholder=f"Description for {col_name}",
                    key=f"{self.key_prefix}_desc_input_{col_name}",
                )
                st.session_state[desc_key] = desc_value

    def _get_description(self, col_name: str) -> str | None:
        """Get description for a column (overridden or from metadata).

        Args:
            col_name: Column name

        Returns:
            Description string or None
        """
        desc_key = f"{self.key_prefix}_desc_{col_name}"
        desc = st.session_state.get(desc_key, "")
        if desc:
            return desc

        col = self._column_info.get(col_name)
        if col and hasattr(col, 'description') and col.description:
            return col.description

        return None

    def _build_configs(
        self,
        selected_dims: list[str],
        selected_metrics: list[str],
        selected_facts: list[str],
    ) -> list[SemanticColumnConfig]:
        """Build SemanticColumnConfig list from selections.

        Args:
            selected_dims: Selected dimension columns
            selected_metrics: Selected metric columns
            selected_facts: Selected fact columns

        Returns:
            List of SemanticColumnConfig objects
        """
        configs = []

        # Dimensions
        for col_name in selected_dims:
            col = self._column_info[col_name]
            configs.append(SemanticColumnConfig(
                source_column=col_name,
                semantic_name=col_name.lower(),
                kind="DIMENSION",
                data_type=getattr(col, 'data_type', None) or "VARCHAR",
                description=self._get_description(col_name),
            ))

        # Metrics
        for col_name in selected_metrics:
            col = self._column_info[col_name]
            agg_key = f"{self.key_prefix}_agg_{col_name}"
            aggregation = st.session_state.get(agg_key, "SUM")

            # Include aggregation in semantic name
            semantic_name = f"{col_name.lower()}_{aggregation.lower()}"

            # Include aggregation in description
            base_desc = self._get_description(col_name)
            if base_desc:
                metric_desc = f"{aggregation} of {base_desc}"
            else:
                metric_desc = f"{aggregation} of {col_name}"

            configs.append(SemanticColumnConfig(
                source_column=col_name,
                semantic_name=semantic_name,
                kind="METRIC",
                data_type=getattr(col, 'data_type', None) or "NUMBER",
                aggregation=aggregation,
                description=metric_desc,
            ))

        # Facts
        for col_name in selected_facts:
            col = self._column_info[col_name]
            configs.append(SemanticColumnConfig(
                source_column=col_name,
                semantic_name=col_name.lower(),
                kind="FACT",
                data_type=getattr(col, 'data_type', None) or "VARCHAR",
                description=self._get_description(col_name),
            ))

        return configs

    def render(self) -> list[SemanticColumnConfig]:
        """Render the column zone selector UI.

        Returns:
            List of SemanticColumnConfig for assigned columns
        """
        # Render three columns for zones
        col1, col2, col3 = st.columns(3)

        with col1:
            selected_dims = self._render_dimensions_zone()

        with col2:
            selected_metrics = self._render_metrics_zone(selected_dims)

        with col3:
            selected_facts = self._render_facts_zone(selected_dims, selected_metrics)

        # Render descriptions section
        self._render_descriptions(selected_dims, selected_metrics, selected_facts)

        # Build and return configs
        return self._build_configs(selected_dims, selected_metrics, selected_facts)

    def get_state(self) -> ColumnZoneState:
        """Get the current selection state.

        Returns:
            ColumnZoneState with current selections
        """
        dims_key = f"{self.key_prefix}_dimensions"
        metrics_key = f"{self.key_prefix}_metrics"
        facts_key = f"{self.key_prefix}_facts"

        # Collect aggregations
        aggregations = {}
        for metric in st.session_state.get(metrics_key, []):
            agg_key = f"{self.key_prefix}_agg_{metric}"
            aggregations[metric] = st.session_state.get(agg_key, "SUM")

        # Collect descriptions
        descriptions = {}
        all_cols = (
            st.session_state.get(dims_key, []) +
            st.session_state.get(metrics_key, []) +
            st.session_state.get(facts_key, [])
        )
        for col_name in all_cols:
            desc_key = f"{self.key_prefix}_desc_{col_name}"
            if desc_key in st.session_state and st.session_state[desc_key]:
                descriptions[col_name] = st.session_state[desc_key]

        return ColumnZoneState(
            dimensions=st.session_state.get(dims_key, []),
            metrics=st.session_state.get(metrics_key, []),
            facts=st.session_state.get(facts_key, []),
            aggregations=aggregations,
            descriptions=descriptions,
        )


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

def render_column_zones(
    columns: list[Any],
    key_prefix: str,
    affected_measures: list[str] | None = None,
    disable_metrics: bool = False,
    disable_facts: bool = False,
    is_base_table: bool = True,
) -> list[SemanticColumnConfig]:
    """Render three-zone column selector.

    Convenience function that wraps ColumnSelector for backward compatibility.

    Args:
        columns: List of column metadata from the source table
        key_prefix: Unique prefix for widget keys
        affected_measures: Optional list of columns affected by fan-out
        disable_metrics: If True, disable the metrics zone
        disable_facts: If True, disable the facts zone
        is_base_table: If True, this is the base/fact table

    Returns:
        List of SemanticColumnConfig for assigned columns
    """
    config = ColumnZoneConfig(
        disable_metrics=disable_metrics,
        disable_facts=disable_facts,
        is_base_table=is_base_table,
        affected_measures=affected_measures or [],
    )

    selector = ColumnSelector(columns, key_prefix, config)
    return selector.render()
