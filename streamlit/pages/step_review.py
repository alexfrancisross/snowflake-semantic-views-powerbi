"""
Step 0: Review Selected Objects Page (Home)

This page shows a summary of selected objects with their metadata
and allows users to review before proceeding to model design.
Object selection is done via the sidebar tree navigator.
"""

import streamlit as st

from pages import BasePage, PageContext, register_page
from utils.logging_config import get_logger, log_user_action
from utils.snowflake_theme import icon_header
from utils.ui_helpers import (
    get_object_icon_key,
    get_object_icon_html,
    get_connector_badge_html,
    display_column_metadata,
)

logger = get_logger(__name__)


@register_page(0)
class ReviewPage(BasePage):
    """Page for reviewing selected objects (home page).

    This page displays:
    - Summary cards for each selected object
    - Column metadata with types
    - Suggested related tables
    - Connector type badges
    """

    def __init__(self, step_index: int = 0):
        super().__init__(step_index)

    def render(self, context: PageContext) -> None:
        """Render the review interface.

        Args:
            context: Page context with session and state
        """
        # Header with icon
        st.markdown(
            f"## {icon_header('verified', 'Review Selected Objects', size=28)}",
            unsafe_allow_html=True
        )

        views_metadata = st.session_state.get("views_metadata", [])

        if not views_metadata:
            st.info("👈 Use the **sidebar tree navigator** to select tables, views, and semantic views.")
            return

        # Summary stats
        total_columns = sum(len(m.columns) for m in views_metadata)
        has_semantic_views = any(
            m.object_type == "SEMANTIC_VIEW" for m in views_metadata
        )
        has_standard_tables = any(
            m.object_type in ("TABLE", "VIEW") for m in views_metadata
        )

        # Mixed selection warning
        if has_semantic_views and has_standard_tables:
            st.info(
                "**Mixed selection:** Semantic views use Custom Connector, "
                "standard tables use Native Snowflake Connector."
            )

        # Show each object
        for metadata in views_metadata:
            icon_html = get_object_icon_html(metadata.object_type, size=20)
            badge_html = get_connector_badge_html(metadata.object_type)

            st.markdown(
                f'{icon_html} **{metadata.full_name}** '
                f'({len(metadata.columns)} columns){badge_html}',
                unsafe_allow_html=True
            )

            # Show table comment if available
            if metadata.table_metadata and metadata.table_metadata.comment:
                st.caption(f"📝 {metadata.table_metadata.comment}")

            # Expandable column details
            with st.expander("Show columns", expanded=False):
                display_column_metadata(metadata)

        # Check for missing related tables
        selected_tables = {m.view for m in views_metadata}
        missing_tables = set()

        for metadata in views_metadata:
            if metadata.relationships:
                for rel in metadata.relationships:
                    if rel.to_table not in selected_tables:
                        missing_tables.add(rel.to_table)

        if missing_tables:
            st.warning(
                f"**Suggested tables:** {', '.join(sorted(missing_tables))}"
            )

        # Navigation (no back button - this is the home page)
        st.divider()
        if st.button(
            "Next: Design Data Model ->",
            type="primary",
            width="stretch"
        ):
            log_user_action("navigate_step", {
                "from": 0,
                "to": 1,
                "objects_count": len(views_metadata),
                "total_columns": total_columns
            })
            st.session_state.wizard_step = 1
            st.rerun()

    def validate(self, context: PageContext) -> bool:
        """Validate the review step.

        Args:
            context: Page context

        Returns:
            True if objects are selected
        """
        views_metadata = st.session_state.get("views_metadata", [])
        return len(views_metadata) > 0
