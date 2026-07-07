"""
Step 3: Generate Model Page

This page generates the final output files (PBIT, PBIP)
and provides download options.
"""

import hashlib
import streamlit as st

from pages import BasePage, PageContext, register_page
from utils.logging_config import get_logger, log_user_action
from utils.error_handling import show_error
from utils.snowflake_theme import icon_header
from utils.pbit_generator import create_pbit_file, collect_all_relationships
from utils.tmdl_generator import generate_multi_view_tmdl_project
from utils.zip_packager import create_zip_with_connector
from utils.tooltips import snowflake_spinner
from utils.ui_helpers import generate_project_name

logger = get_logger(__name__)

# Constants for PBI connection modes (avoid fragile string parsing)
class PBIMode:
    DIRECT_QUERY = "directQuery"
    IMPORT = "import"


@register_page(2)
class GeneratePage(BasePage):
    """Page for generating and downloading output files.

    This page allows users to:
    - Choose output format (PBIT, PBIP)
    - Configure connection type (DirectQuery/Import)
    - Download the generated files
    """

    def __init__(self, step_index: int = 2):
        super().__init__(step_index)

    def render(self, context: PageContext) -> None:
        """Render the generation interface.

        Args:
            context: Page context with session and state
        """
        st.markdown(
            f"## {icon_header('rocket', 'Generate Output', size=28)}",
            unsafe_allow_html=True
        )

        views_metadata = st.session_state.get("views_metadata", [])
        selected_objects = st.session_state.get("selected_objects", [])

        # Debug: Log state mismatch
        logger.info(f"[GENERATE] selected_objects={len(selected_objects)}, views_metadata={len(views_metadata)}")

        if not views_metadata:
            st.warning(f"No metadata loaded. ({len(selected_objects)} objects selected but metadata not loaded)")
            st.caption("Go back to Step 1 to load object metadata.")
            if st.button("← Back to Review"):
                st.session_state.wizard_step = 0
                st.rerun()
            return

        # Get connection info from context or session state
        conn_info = self._get_connection_info(context)
        conn_info = self._apply_connection_overrides(conn_info)

        # Project name input
        default_name = generate_project_name(views_metadata)
        project_name = st.text_input(
            "Project Name",
            value=default_name,
            help="Name for the generated Power BI project"
        )

        # Connection type selection
        st.markdown("**How should Power BI connect to Snowflake?**")

        # Check if semantic views are in selection
        has_semantic_views = any(
            m.object_type == "SEMANTIC_VIEW" for m in views_metadata
        )

        if has_semantic_views:
            # Semantic views only support DirectQuery - show disabled radio
            st.radio(
                "Connection type:",
                options=["Live Connection (DirectQuery)"],
                horizontal=True,
                key="pbi_mode_radio_semantic",  # Unique key for semantic view mode
                label_visibility="collapsed",
                disabled=True,
            )
            pbi_mode = PBIMode.DIRECT_QUERY
            st.info("Semantic views require DirectQuery mode.")
        else:
            mode_index = st.radio(
                "Connection type:",
                options=["Live Connection (DirectQuery)", "Cached Data (Import)"],
                horizontal=True,
                key="pbi_mode_radio_standard",  # Unique key for standard mode
                label_visibility="collapsed",
                index=0,
            )
            pbi_mode = PBIMode.DIRECT_QUERY if mode_index == "Live Connection (DirectQuery)" else PBIMode.IMPORT

        # Store the actual mode value (not display string)
        st.session_state.pbi_mode = pbi_mode

        # Output format selection
        output_format = st.radio(
            "Output Format",
            ["PBIT (Recommended)", "PBIP (ZIP)"],
            index=0,
            horizontal=True,
            help="PBIT: Template file. PBIP: Project folder (requires Developer Mode).",
            key="output_format_radio",
        )

        # Generate file with caching to prevent regeneration on every rerun
        file_data, file_name, mime_type = self._get_cached_file(
            output_format, views_metadata, conn_info, project_name, pbi_mode
        )

        # Single download button
        if file_data:
            st.download_button(
                label="Download Power BI File",
                data=file_data,
                file_name=file_name,
                mime=mime_type,
                type="primary",
                width='stretch'
            )

        # Navigation (back only - final step)
        st.divider()
        if st.button("← Back to Design Data Model"):
            log_user_action("navigate_step", {"from": 2, "to": 1})
            st.session_state.wizard_step = 1
            st.rerun()

    def _apply_connection_overrides(self, conn_info: dict | None) -> dict | None:
        """Render warehouse/host override controls and apply them to conn_info.

        Surfaces UI warnings instead of silently baking a fake default
        warehouse or a naive host into the generated M code (issues #1/#2/#6).
        """
        if conn_info is None:
            return conn_info

        conn_info = dict(conn_info)

        if conn_info.get("warehouse_missing"):
            st.warning(
                "No warehouse is active for this Snowflake session, so the "
                "generated file would have no warehouse configured. Enter a "
                "warehouse to use below."
            )
            warehouse_override = st.text_input(
                "Snowflake warehouse to use",
                value=st.session_state.get("warehouse_override", ""),
                key="warehouse_override",
                help="Required because CURRENT_WAREHOUSE() returned no active warehouse for this session.",
            )
            if warehouse_override:
                conn_info["warehouse"] = warehouse_override
                conn_info["warehouse_missing"] = False

        with st.expander("Advanced: Server host override"):
            host_override = st.text_input(
                "Server host override",
                value=st.session_state.get("server_host_override", ""),
                key="server_host_override",
                help=(
                    "Leave blank to use the detected host "
                    f"({conn_info.get('server', 'unknown')}). Set this if you connect "
                    "via PrivateLink, or the detected host is wrong for your account."
                ),
            )
            if host_override:
                conn_info["server"] = host_override

        return conn_info

    def _get_connection_info(self, context: PageContext) -> dict | None:
        """Get connection info from session or defaults.

        Args:
            context: Page context

        Returns:
            Dict with server, warehouse info, or None if unavailable
        """
        # Try to get from session state (set by main app)
        if "conn_info" in st.session_state:
            return st.session_state.conn_info

        # Fallback - try to get from session
        try:
            from utils import get_session_info
            return get_session_info(context.session)
        except Exception as e:
            logger.error(f"Could not get connection info: {e}", exc_info=True)
            return None

    def _compute_cache_key(
        self,
        output_format: str,
        views_metadata: list,
        conn_info: dict,
        project_name: str,
        pbi_mode: str,
    ) -> str:
        """Compute a hash key for caching generated files.

        Args:
            output_format: Selected format string
            views_metadata: List of view metadata
            conn_info: Connection info dict
            project_name: Project name
            pbi_mode: PBI mode constant

        Returns:
            Hash string for cache lookup
        """
        # Build a string representation of all inputs
        metadata_repr = "|".join(
            f"{m.database}.{m.schema}.{m.view}" for m in sorted(views_metadata, key=lambda x: x.view)
        )
        selected_rels = st.session_state.get("selected_relationships", {})
        rels_repr = str(sorted(selected_rels.items()))
        active_choices = st.session_state.get("active_relationship_choices", {})
        choices_repr = str(sorted(active_choices.items()))
        dup_dims = st.session_state.get("duplicate_role_playing_dims")

        cache_input = f"{output_format}|{metadata_repr}|{conn_info}|{project_name}|{pbi_mode}|{rels_repr}|{choices_repr}|{dup_dims}"
        return hashlib.md5(cache_input.encode()).hexdigest()

    def _get_cached_file(
        self,
        output_format: str,
        views_metadata: list,
        conn_info: dict,
        project_name: str,
        pbi_mode: str,
    ) -> tuple:
        """Get file from cache or generate if needed.

        Args:
            output_format: Selected format string
            views_metadata: List of view metadata
            conn_info: Connection info dict
            project_name: Project name
            pbi_mode: PBI mode constant

        Returns:
            Tuple of (file_data, file_name, mime_type) or (None, None, None) on error
        """
        # Check for connection info error
        if conn_info is None:
            st.error("Unable to retrieve Snowflake connection information. Please check your connection and try again.")
            return None, None, None

        cache_key = self._compute_cache_key(output_format, views_metadata, conn_info, project_name, pbi_mode)

        # Check if we have a cached result with the same key
        cached = st.session_state.get("_generated_file_cache", {})
        if cached.get("key") == cache_key:
            return cached["data"], cached["name"], cached["mime"]

        # Generate new file with spinner
        with snowflake_spinner("Generating Power BI file..."):
            file_data, file_name, mime_type = self._generate_file(
                output_format, views_metadata, conn_info, project_name, pbi_mode
            )

        # Cache the result
        if file_data:
            st.session_state["_generated_file_cache"] = {
                "key": cache_key,
                "data": file_data,
                "name": file_name,
                "mime": mime_type,
            }

        return file_data, file_name, mime_type

    def _generate_file(
        self,
        output_format: str,
        views_metadata: list,
        conn_info: dict,
        project_name: str,
        pbi_mode: str,
    ) -> tuple:
        """Generate the Power BI file.

        Args:
            output_format: Selected format string
            views_metadata: List of view metadata
            conn_info: Connection info dict
            project_name: Project name
            pbi_mode: PBI mode constant (PBIMode.DIRECT_QUERY or PBIMode.IMPORT)

        Returns:
            Tuple of (file_data, file_name, mime_type) or (None, None, None) on error
        """
        selected_rels = self._get_selected_relationships(views_metadata)
        dup_dims = st.session_state.get("duplicate_role_playing_dims")
        user_active_choices = st.session_state.get("active_relationship_choices", {})

        try:
            if output_format.startswith("PBIT"):
                file_data = create_pbit_file(
                    views_metadata,
                    conn_info.get("server", ""),
                    conn_info.get("warehouse", ""),
                    project_name,
                    selected_relationships=selected_rels,
                    duplicate_role_playing_dims=dup_dims,
                    mode=pbi_mode,
                    user_active_choices=user_active_choices,
                )
                return file_data, f"{project_name}.pbit", "application/octet-stream"
            else:
                tmdl_files = generate_multi_view_tmdl_project(
                    views_metadata,
                    conn_info.get("server", ""),
                    conn_info.get("warehouse", ""),
                    project_name,
                    mode=pbi_mode
                )
                file_data = create_zip_with_connector(tmdl_files)
                return file_data, f"{project_name}_PowerBI.zip", "application/zip"
        except Exception as e:
            logger.error(f"Error generating file: {e}", exc_info=True)
            st.error(f"Error generating file: {e}")
            return None, None, None

    def _get_selected_relationships(self, views_metadata: list) -> list | None:
        """Get selected relationships including bridge and manual.

        Args:
            views_metadata: List of view metadata

        Returns:
            List of selected relationships or None
        """
        all_relationships = collect_all_relationships(views_metadata)
        bridge_relationships = st.session_state.get("bridge_relationships", [])
        manual_relationships = st.session_state.get("manual_relationships", [])

        # Combine all relationships
        all_rels = list(all_relationships) + bridge_relationships

        # Convert manual relationships to standard format
        for rel in manual_relationships:
            if hasattr(rel, 'to_relationship_metadata'):
                all_rels.append(rel.to_relationship_metadata())
            else:
                all_rels.append(rel)

        if all_rels and "selected_relationships" in st.session_state:
            return [
                rel for rel in all_rels
                if st.session_state.selected_relationships.get(rel.relationship_id, True)
            ]
        return None if not all_rels else all_rels

    def validate(self, context: PageContext) -> bool:
        """Validate before generation.

        Args:
            context: Page context

        Returns:
            True if ready to generate
        """
        views_metadata = st.session_state.get("views_metadata", [])
        return len(views_metadata) > 0
