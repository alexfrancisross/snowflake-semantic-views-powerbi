"""
Step 1: Design Data Model Page

This page allows users to configure relationships between
selected objects and set data model options.
"""

import streamlit as st

from pages import BasePage, PageContext, register_page
from utils.logging_config import get_logger, log_user_action
from utils.error_handling import show_error
from utils.snowflake_theme import icon_header, get_svg_icon
from utils.pbit_generator import (
    collect_all_relationships,
    detect_ambiguous_paths,
    detect_conflict_pairs,
    detect_role_playing_dimensions,
)
from utils.schema_visualizer import render_schema_visualizer, show_graph_legend, FLOW_AVAILABLE
from utils.relationship_suggester import create_manual_relationship

logger = get_logger(__name__)


def init_relationship_state(all_relationships: list) -> None:
    """Initialize selected relationships in session state.

    Args:
        all_relationships: List of detected relationships
    """
    if "selected_relationships" not in st.session_state:
        # Select all by default
        st.session_state.selected_relationships = {
            rel.relationship_id: True for rel in all_relationships
        }
    else:
        # Add any new relationships (from newly selected tables)
        for rel in all_relationships:
            if rel.relationship_id not in st.session_state.selected_relationships:
                st.session_state.selected_relationships[rel.relationship_id] = True
        # Remove relationships that no longer exist
        current_ids = {rel.relationship_id for rel in all_relationships}
        st.session_state.selected_relationships = {
            k: v for k, v in st.session_state.selected_relationships.items()
            if k in current_ids
        }

    # Initialize active relationship choices for conflict pairs
    # Maps conflict_pair_key (e.g., "conflict_0") to the chosen active relationship_id
    if "active_relationship_choices" not in st.session_state:
        st.session_state.active_relationship_choices = {}


def render_relationship_checkboxes(
    relationships: list,
    inactive_ids: set,
) -> None:
    """Render checkboxes for relationship selection.

    Args:
        relationships: List of relationships to render
        inactive_ids: Set of inactive relationship IDs
    """
    for rel in relationships:
        rel_id = rel.relationship_id
        is_inactive = rel_id in inactive_ids and st.session_state.selected_relationships.get(rel_id, True)

        # Build cardinality string (e.g., "*:1", "1:*")
        card_str = ""
        if hasattr(rel, 'cardinality') and rel.cardinality:
            from_sym = "1" if rel.cardinality.from_cardinality == "one" else "*"
            to_sym = "1" if rel.cardinality.to_cardinality == "one" else "*"
            card_str = f" ({from_sym}:{to_sym})"

        # Build label
        label = f"{rel.from_table}.{rel.from_column} -> {rel.to_table}.{rel.to_column}{card_str}"
        if rel.name:
            label += f" ({rel.name})"
        if is_inactive:
            label += " ⚠️"

        # Help text
        help_text = None
        if is_inactive:
            help_text = "Secondary path - won't filter automatically (use USERELATIONSHIP in DAX)"

        checked = st.checkbox(
            label,
            value=st.session_state.selected_relationships.get(rel_id, True),
            key=f"rel_{rel_id}",
            help=help_text,
        )
        st.session_state.selected_relationships[rel_id] = checked


def render_manual_relationship_checkboxes(
    manual_relationships: list,
    inactive_ids: set,
) -> None:
    """Render checkboxes for manual relationships with delete button.

    Args:
        manual_relationships: List of manually created relationships
        inactive_ids: Set of inactive relationship IDs
    """
    for rel in manual_relationships:
        rel_id = rel.relationship_id
        is_inactive = rel_id in inactive_ids and st.session_state.selected_relationships.get(rel_id, True)

        # Build cardinality string (e.g., "*:1", "1:*")
        card_str = ""
        if hasattr(rel, 'from_cardinality') and rel.from_cardinality and hasattr(rel, 'to_cardinality') and rel.to_cardinality:
            from_sym = "1" if rel.from_cardinality == "one" else "*"
            to_sym = "1" if rel.to_cardinality == "one" else "*"
            card_str = f" ({from_sym}:{to_sym})"

        # Build label with [Manual] badge
        label = f"{rel.from_table}.{rel.from_column} -> {rel.to_table}.{rel.to_column}{card_str} `[Manual]`"
        if is_inactive:
            label += " ⚠️"

        help_text = "User-created relationship"
        if is_inactive:
            help_text += " (secondary path - won't filter automatically)"

        # Use columns for checkbox + delete button
        col1, col2 = st.columns([0.9, 0.1])

        with col1:
            checked = st.checkbox(
                label,
                value=st.session_state.selected_relationships.get(rel_id, True),
                key=f"rel_{rel_id}",
                help=help_text,
            )
            st.session_state.selected_relationships[rel_id] = checked

        with col2:
            if st.button("🗑️", key=f"del_{rel_id}", help="Delete this relationship"):
                # Remove from manual relationships
                if "manual_relationships" in st.session_state:
                    st.session_state.manual_relationships = [
                        r for r in st.session_state.manual_relationships
                        if r.relationship_id != rel_id
                    ]
                st.session_state.selected_relationships.pop(rel_id, None)
                st.rerun()


def render_add_relationship_form(views_metadata: list) -> None:
    """Render inline form for adding manual relationships.

    Args:
        views_metadata: List of selected table metadata
    """
    # Initialize form visibility state
    if "show_add_rel_form" not in st.session_state:
        st.session_state.show_add_rel_form = False

    # Toggle button
    if st.button("+ Add Relationship", key="toggle_add_rel"):
        st.session_state.show_add_rel_form = not st.session_state.show_add_rel_form
        st.rerun()

    if not st.session_state.show_add_rel_form:
        return

    # Build table/column options
    table_names = [m.view for m in views_metadata]
    table_columns = {m.view: [c.name for c in m.columns] for m in views_metadata}
    metadata_by_name = {m.view: m for m in views_metadata}

    with st.container(border=True):
        st.markdown("**Add New Relationship**")

        col1, col2 = st.columns(2)

        with col1:
            from_table = st.selectbox(
                "From Table",
                options=table_names,
                key="add_rel_from_table",
            )
            from_cols = table_columns.get(from_table, [])
            from_column = st.selectbox(
                "From Column",
                options=from_cols,
                key="add_rel_from_col",
            )

        with col2:
            # Filter out same table for "to" options
            to_options = [t for t in table_names if t != from_table]
            to_table = st.selectbox(
                "To Table",
                options=to_options if to_options else table_names,
                key="add_rel_to_table",
            )
            to_cols = table_columns.get(to_table, [])
            to_column = st.selectbox(
                "To Column",
                options=to_cols,
                key="add_rel_to_col",
            )

        # Cardinality selection
        st.markdown("**Cardinality**")
        cardinality_options = [
            "Many to One (*:1)",      # Most common - FK to PK
            "One to One (1:1)",
            "One to Many (1:*)",
            "Many to Many (*:*)",
        ]
        selected_cardinality = st.radio(
            "Relationship type",
            options=cardinality_options,
            index=0,  # Default to Many-to-One
            key="add_rel_cardinality",
            horizontal=True,
            label_visibility="collapsed",
            help="Many to One is most common (e.g., Orders -> Customers)",
        )

        # Parse cardinality selection
        if "Many to One" in selected_cardinality:
            from_card, to_card = "many", "one"
        elif "One to One" in selected_cardinality:
            from_card, to_card = "one", "one"
        elif "One to Many" in selected_cardinality:
            from_card, to_card = "one", "many"
        else:  # Many to Many
            from_card, to_card = "many", "many"

        # Action buttons
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            if st.button("Cancel", key="cancel_add_rel", width="stretch"):
                st.session_state.show_add_rel_form = False
                st.rerun()

        with btn_col2:
            if st.button("Add", key="confirm_add_rel", type="primary", width="stretch"):
                if from_table and from_column and to_table and to_column:
                    from_meta = metadata_by_name.get(from_table)
                    to_meta = metadata_by_name.get(to_table)

                    new_rel = create_manual_relationship(
                        from_table=from_table,
                        from_columns=from_column,
                        to_table=to_table,
                        to_columns=to_column,
                        from_database=from_meta.database if from_meta else None,
                        from_schema=from_meta.schema if from_meta else None,
                        to_database=to_meta.database if to_meta else None,
                        to_schema=to_meta.schema if to_meta else None,
                        from_cardinality=from_card,
                        to_cardinality=to_card,
                    )

                    # Initialize manual_relationships if needed
                    if "manual_relationships" not in st.session_state:
                        st.session_state.manual_relationships = []

                    # Check for duplicates
                    existing_ids = {r.relationship_id for r in st.session_state.manual_relationships}
                    if new_rel.relationship_id not in existing_ids:
                        st.session_state.manual_relationships.append(new_rel)
                        st.session_state.selected_relationships[new_rel.relationship_id] = True
                        log_user_action("add_manual_relationship", {
                            "from": f"{from_table}.{from_column}",
                            "to": f"{to_table}.{to_column}",
                        })
                        st.session_state.show_add_rel_form = False
                        st.rerun()
                    else:
                        st.warning("This relationship already exists.")


def render_conflict_pair_group(
    pair: tuple,
    pair_index: int,
) -> None:
    """Render a pair of conflicting relationships with toggle.

    Shows both relationships grouped together with a radio button
    to select which one should be the primary (active) path.

    Args:
        pair: Tuple of (rel1, rel2, center_table_name) where rel1 is default active
        pair_index: Index of this conflict pair (for session state key)
    """
    rel1, rel2, center_table = pair
    conflict_key = f"conflict_{pair_index}"

    # Get current choice (default to rel1 if not set)
    current_choice = st.session_state.active_relationship_choices.get(
        conflict_key, rel1.relationship_id
    )

    # Build labels for each option
    def build_rel_label(rel) -> str:
        card_str = ""
        if hasattr(rel, 'cardinality') and rel.cardinality:
            from_sym = "1" if rel.cardinality.from_cardinality == "one" else "*"
            to_sym = "1" if rel.cardinality.to_cardinality == "one" else "*"
            card_str = f" ({from_sym}:{to_sym})"
        from_col = rel.from_column if hasattr(rel, 'from_column') else rel.from_columns
        to_col = rel.to_column if hasattr(rel, 'to_column') else rel.to_columns
        return f"{rel.from_table}.{from_col} -> {rel.to_table}.{to_col}{card_str}"

    label1 = build_rel_label(rel1)
    label2 = build_rel_label(rel2)

    # Create options mapping
    options = {
        label1: rel1.relationship_id,
        label2: rel2.relationship_id,
    }

    # Find current label
    current_label = label1 if current_choice == rel1.relationship_id else label2

    with st.container(border=True):
        st.markdown(f"**Multiple paths to {center_table}** - choose primary:")

        selected_label = st.radio(
            "Select primary path",
            options=list(options.keys()),
            index=0 if current_label == label1 else 1,
            key=f"conflict_radio_{pair_index}",
            label_visibility="collapsed",
        )

        # Update session state
        selected_rel_id = options[selected_label]
        st.session_state.active_relationship_choices[conflict_key] = selected_rel_id

        st.caption("Secondary path won't filter automatically (use USERELATIONSHIP in DAX)")




@register_page(1)
class ModelPage(BasePage):
    """Page for configuring the data model.

    This page allows users to:
    - View auto-detected relationships
    - Add/remove relationships manually
    - Configure cardinality
    - Handle fan-out warnings
    - View schema visualization
    """

    def __init__(self, step_index: int = 1):
        super().__init__(step_index)

    def render(self, context: PageContext) -> None:
        """Render the model configuration interface.

        Args:
            context: Page context with session and state
        """
        st.markdown(
            f"## {icon_header('data_engineering', 'Design Data Model', size=28)}",
            unsafe_allow_html=True
        )

        views_metadata = st.session_state.get("views_metadata", [])
        logger.debug(f"ModelPage.render: views_metadata has {len(views_metadata)} items")
        logger.debug(f"ModelPage.render: table names = {[m.view for m in views_metadata]}")

        # No objects selected
        if not views_metadata:
            st.warning("No objects selected. Please go back and select objects.")
            if st.button("← Back to Review"):
                st.session_state.wizard_step = 0
                st.rerun()
            return

        # Single object - no relationships to configure but show visualizer
        if len(views_metadata) == 1:
            st.info("Single object selected - no relationships to configure.")

            # Show single-object visualizer
            if FLOW_AVAILABLE:
                render_schema_visualizer(
                    tables=views_metadata,
                    relationships=[],
                    key="single_object_graph"
                )

            st.divider()
            col1, col2 = st.columns(2)
            with col1:
                if st.button("← Back to Review"):
                    st.session_state.wizard_step = 0
                    st.rerun()
            with col2:
                if st.button("NEXT: DOWNLOAD PBI WORKBOOK ->", type="primary", width='stretch'):
                    log_user_action("navigate_step", {"from": 1, "to": 2, "skip_semantic": True})
                    st.session_state.wizard_step = 2
                    st.rerun()
            return

        # Multiple objects - show relationship configuration
        self._render_relationship_config(views_metadata)

        # Navigation
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            if st.button("← Back to Review"):
                log_user_action("navigate_step", {"from": 1, "to": 0})
                st.session_state.wizard_step = 0
                st.rerun()
        with col2:
            if st.button("Next: Generate Output ->", type="primary", width="stretch"):
                log_user_action("navigate_step", {"from": 1, "to": 2})
                st.session_state.wizard_step = 2
                st.rerun()

    def _render_relationship_config(self, views_metadata: list) -> None:
        """Render the relationship configuration section.

        Args:
            views_metadata: List of selected object metadata
        """
        logger.debug(f"_render_relationship_config called with {len(views_metadata)} objects")

        has_semantic_views = any(m.object_type == "SEMANTIC_VIEW" for m in views_metadata)
        has_standard_tables = any(m.object_type in ("TABLE", "VIEW") for m in views_metadata)
        # Pass session for cardinality enrichment
        session = st.session_state.get("snowpark_session")
        all_relationships = collect_all_relationships(views_metadata, session=session)
        logger.debug(f"Found {len(all_relationships)} FK relationships")

        # Cross-connector warning
        if has_semantic_views and has_standard_tables and all_relationships:
            self._render_cross_connector_warning(views_metadata, all_relationships)

        # Initialize relationship state (even if no FK relationships detected)
        init_relationship_state(all_relationships)

        # Detect conflict pairs on ALL relationships first (not just selected)
        # This ensures the "Path Choices" selector appears even when relationships
        # are deselected - user needs to see conflicts to make informed choices
        conflict_pairs = detect_conflict_pairs(all_relationships)

        # Get selected relationships for other analysis
        selected_rels = [
            rel for rel in all_relationships
            if st.session_state.selected_relationships.get(rel.relationship_id, True)
        ]

        # Detect ambiguous paths, respecting user's active/inactive choices
        user_choices = st.session_state.get("active_relationship_choices", {})
        _, inactive_rels = detect_ambiguous_paths(selected_rels, user_active_choices=user_choices)
        inactive_ids = {rel.relationship_id for rel in inactive_rels}

        # Combine detected and manual relationships
        manual_relationships = st.session_state.get("manual_relationships", [])
        all_rels = all_relationships + manual_relationships

        # Detect role-playing dimensions
        role_playing_dims = detect_role_playing_dimensions(selected_rels)
        if role_playing_dims:
            self._init_role_playing_state(role_playing_dims)

        # Two-column layout
        left_col, right_col = st.columns([1, 1])

        with left_col:
            try:
                self._render_left_column(
                    all_relationships,
                    all_rels,
                    inactive_ids,
                    role_playing_dims,
                    views_metadata,
                    conflict_pairs,
                )
            except Exception as e:
                logger.error(f"Error in _render_left_column: {e}", exc_info=True)
                show_error(
                    "Error rendering relationships",
                    details=str(e),
                    suggestion="Try refreshing the page or re-selecting your objects"
                )

        with right_col:
            try:
                self._render_schema_diagram(views_metadata, all_rels)
            except Exception as e:
                logger.error(f"Error in _render_schema_diagram: {e}", exc_info=True)
                show_error(
                    "Error rendering diagram",
                    details=str(e),
                    suggestion="Try refreshing the page or re-selecting your objects"
                )

    def _render_cross_connector_warning(self, views_metadata: list, all_relationships: list) -> None:
        """Render warning for cross-connector relationships."""
        object_types = {m.view: m.object_type for m in views_metadata}
        cross_connector_rels = []

        for rel in all_relationships:
            from_type = object_types.get(rel.from_table, "TABLE")
            to_type = object_types.get(rel.to_table, "TABLE")
            from_is_semantic = from_type == "SEMANTIC_VIEW"
            to_is_semantic = to_type == "SEMANTIC_VIEW"
            if from_is_semantic != to_is_semantic:
                cross_connector_rels.append(rel)

        if cross_connector_rels:
            st.warning(
                f"**Cross-connector relationships detected ({len(cross_connector_rels)})**\n\n"
                f"Relationships between tables using different connectors may need to be "
                f"created manually in Power BI Desktop.\n\n"
                f"Affected: {', '.join(f'{r.from_table}->{r.to_table}' for r in cross_connector_rels[:3])}"
                f"{'...' if len(cross_connector_rels) > 3 else ''}"
            )

    def _init_role_playing_state(self, role_playing_dims: dict) -> None:
        """Initialize role-playing dimension state."""
        if "duplicate_role_playing_dims" not in st.session_state:
            st.session_state.duplicate_role_playing_dims = {
                dim: True for dim in role_playing_dims
            }
        else:
            for dim in role_playing_dims:
                if dim not in st.session_state.duplicate_role_playing_dims:
                    st.session_state.duplicate_role_playing_dims[dim] = True
            st.session_state.duplicate_role_playing_dims = {
                k: v for k, v in st.session_state.duplicate_role_playing_dims.items()
                if k in role_playing_dims
            }

    def _render_left_column(
        self,
        all_relationships: list,
        all_rels: list,
        inactive_ids: set,
        role_playing_dims: dict,
        views_metadata: list | None = None,
        conflict_pairs: list | None = None,
    ) -> None:
        """Render the left column with relationship checkboxes and conflict pairs."""
        manual_relationships = st.session_state.get("manual_relationships", [])
        conflict_pairs = conflict_pairs or []

        # Add Relationship form at top
        if views_metadata:
            render_add_relationship_form(views_metadata)
            st.markdown("---")

        # Select/Deselect all buttons (only show if there are relationships)
        if all_rels:
            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                if st.button("Select All", key="select_all_rels", width="stretch"):
                    for rel in all_rels:
                        rel_id = rel.relationship_id
                        st.session_state.selected_relationships[rel_id] = True
                        st.session_state[f"rel_{rel_id}"] = True
                    st.rerun()
            with btn_col2:
                if st.button("Deselect All", key="deselect_all_rels", width="stretch"):
                    for rel in all_rels:
                        rel_id = rel.relationship_id
                        st.session_state.selected_relationships[rel_id] = False
                        st.session_state[f"rel_{rel_id}"] = False
                    st.rerun()

        # Manual relationships
        if manual_relationships:
            st.markdown("**✏️ Manual Relationships**")
            render_manual_relationship_checkboxes(manual_relationships, inactive_ids)

        # Conflict pairs - grouped with toggle
        if conflict_pairs:
            st.markdown("**Path Choices** (select one per group)")
            # Get IDs of relationships in conflict pairs
            conflicting_rel_ids = set()
            for i, pair in enumerate(conflict_pairs):
                rel1, rel2, center = pair
                conflicting_rel_ids.add(rel1.relationship_id)
                conflicting_rel_ids.add(rel2.relationship_id)
                render_conflict_pair_group(pair, i)

            # Non-conflicting relationships (simple checkboxes)
            non_conflicting = [r for r in all_relationships if r.relationship_id not in conflicting_rel_ids]
            if non_conflicting:
                st.markdown("**Other Relationships**")
                render_relationship_checkboxes(non_conflicting, set())  # No inactive for these
        elif all_relationships:
            # No conflict pairs - show all relationships normally
            if manual_relationships:
                st.markdown(f"**{get_svg_icon('copy', 16)} Detected Relationships**", unsafe_allow_html=True)
            render_relationship_checkboxes(all_relationships, inactive_ids)
        elif not manual_relationships:
            # No relationships at all - show helpful message
            st.info(
                "No FK constraints detected. Use **+ Add Relationship** above "
                "to define your data model."
            )


        # Role-playing dimensions
        if role_playing_dims:
            st.markdown("---")
            st.markdown("**Role-Playing Dimensions**")
            st.caption("Dimensions used by multiple tables - will be duplicated with role prefixes.")

            for dim_name, referencing_tables in role_playing_dims.items():
                new_tables = [f"{ref}_{dim_name}" for ref in referencing_tables]
                checked = st.checkbox(
                    f"{dim_name} -> {', '.join(new_tables)}",
                    value=st.session_state.duplicate_role_playing_dims.get(dim_name, True),
                    key=f"dup_{dim_name}",
                    help=f"Referenced by: {', '.join(referencing_tables)}",
                )
                st.session_state.duplicate_role_playing_dims[dim_name] = checked

    def _render_schema_diagram(self, views_metadata: list, all_rels: list) -> None:
        """Render the schema diagram visualization."""
        if len(views_metadata) > 1 and FLOW_AVAILABLE:
            st.caption("Drag to rearrange, scroll to zoom")

            selected_rels = [
                rel for rel in all_rels
                if st.session_state.selected_relationships.get(rel.relationship_id, True)
            ]
            render_schema_visualizer(
                tables=views_metadata,
                relationships=selected_rels,
                key="main_schema_graph"
            )
            show_graph_legend()
        else:
            st.info("Schema diagram available when 2+ tables selected")

    def validate(self, context: PageContext) -> bool:
        """Validate the model configuration.

        Args:
            context: Page context

        Returns:
            True if model is valid
        """
        views_metadata = st.session_state.get("views_metadata", [])
        return len(views_metadata) > 0
