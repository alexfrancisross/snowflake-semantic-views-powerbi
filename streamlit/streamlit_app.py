"""
Streamlit App: Power BI Semantic Model Generator for Snowflake

This app allows users to:
1. Browse Snowflake objects in a tree view (Database -> Schema -> Objects)
2. Select multiple objects (Tables, Views, Semantic Views)
3. Generate a PBIT/PBIP project for Power BI Desktop
4. Download the project bundled with the custom connector

Supports running both locally (using ~/.snowflake/connections.toml)
and in Streamlit in Snowflake (using get_active_session()).
"""

import streamlit as st
import streamlit_antd_components as sac
import pandas as pd
import base64
from datetime import datetime
from pathlib import Path

# Import local modules
# Note: metadata_fetcher imports consolidated into single block
from utils.metadata_fetcher import (
    # Data access functions
    get_databases,
    get_schemas,
    get_all_objects,
    get_view_metadata,
    get_metadata_batch_parallel,
    get_semantic_views,  # For cache clearing after SV creation
    get_tables,  # For cache clearing after table creation
    # Data types
    SemanticViewMetadata,
    ObjectInfo,
    ObjectType,
    RelationshipMetadata,
    # Relationship utilities
    enrich_relationship_with_cardinality,
    assess_fan_out_risk,
    detect_all_relationships,
    detect_schema_type,
    identify_base_table,
    can_have_metrics,
    can_have_facts,
    detect_indirect_connections,
)
from utils.tmdl_generator import generate_multi_view_tmdl_project
from utils.zip_packager import (
    create_zip_with_connector,
    create_connector_only_zip,
    get_connector_bytes,
)
from utils.pbit_generator import (
    create_pbit_file,
    collect_all_relationships,
    detect_ambiguous_paths,
    detect_role_playing_dimensions,
)
from utils.fan_out_validator import (
    validate_measure_dimension_combinations,
    detect_relationship_issue_type,
    RelationshipIssue,
)
from utils.snowflake_ddl_generator import (
    detect_role_playing_dimensions,
    detect_circular_relationships,
    execute_ddl,
    DDLResult,
    # DAX measure generation - kept for fan-out solutions
    generate_dax_measure,
)
from utils.snowflake_session import (
    get_snowflake_session,
    get_session_info,
    is_running_in_snowflake,
    IN_SNOWFLAKE,
    render_connection_form,
    list_available_connections,
    reconnect_local_session,
)
from utils.tooltips import (
    inject_tooltip_css,
    term_with_tooltip,
    dimensions_label,
    metrics_label,
    facts_label,
    directquery_label,
    semantic_view_label,
    fan_out_label,
    granularity_label,
    inject_skeleton_css,
    show_skeleton_tree,
    show_skeleton_card,
    show_skeleton_progress,
    snowflake_spinner,
)
from utils.schema_visualizer import (
    render_schema_visualizer,
    show_graph_legend,
    FLOW_AVAILABLE,
)
from utils.snowflake_theme import get_full_theme_css, COLORS, DARK_COLORS, icon_header, get_svg_icon
from utils.ui_helpers import (
    generate_project_name,
    get_object_icon_key,
    get_object_icon_html,
    get_connector_badge_html,
    display_column_metadata,
)

# Import new Phase 2 modules
from utils.config import CONFIG, WIZARD_STEPS, OBJECT_TYPES, get_object_type_config
from utils.session_manager import (
    get_app_state,
    reset_app_state,
    migrate_legacy_state,
    init_session_state as init_app_state,
    sync_from_legacy,
    sync_to_legacy,
)
from utils.relationship_suggester import create_manual_relationship
from utils.validation import (
    validate_identifier,
    validate_semantic_view_name,
    validate_qualified_name,
    sanitize_for_display,
    escape_identifier,
    build_qualified_name,
    ValidationResult,
)
from utils.theme_loader import initialize_theme, inject_all_styles, inject_scripts

# Import Phase 3 modules - logging and error handling
from utils.logging_config import get_logger, log_user_action, log_performance
from utils.error_handling import (
    handle_error,
    safe_execute,
    error_boundary,
    SnowflakeConnectionError,
    MetadataFetchError,
)

# Import pages module for future incremental migration
from pages import render_current_step, is_page_implemented, PageContext

# Initialize module logger
logger = get_logger(__name__)


# === Snowflake Design System Theme ===
def inject_custom_css():
    """Inject Snowflake Design System compliant CSS theme.

    Uses the centralized theme_loader for organized CSS/JS injection.
    """
    # Get dark mode state from session
    dark_mode = st.session_state.get("dark_mode", False)

    # Use new centralized theme loader
    initialize_theme(dark_mode)

    # Legacy: keep the old injection for backward compatibility during transition
    # This can be removed once the theme_loader is fully tested
    theme_css = get_full_theme_css(dark_mode)

    st.markdown(f"""
    <style>
    {theme_css}

    /* Reduce top padding in main content area */
    .main .block-container {{
        padding-top: 0 !important;
        margin-top: 0 !important;
    }}

    /* Remove padding from app view container */
    [data-testid="stAppViewContainer"] {{
        padding-top: 0 !important;
    }}

    /* Remove top margin from main section */
    section[data-testid="stMain"] {{
        padding-top: 0 !important;
    }}


    /* Target the main block container */
    [data-testid="stMainBlockContainer"] {{
        padding-top: 0 !important;
        margin-top: 0 !important;
    }}

    /* Logo header alignment */
    .logo-header {{
        display: flex;
        align-items: center;
        gap: 1rem;
        margin-bottom: 1rem;
    }}

    /* Responsive steps/stepper component */
    .stCustomComponentV1 {{
        min-width: 0 !important;
    }}

    /* On smaller screens, allow horizontal scroll for steps */
    @media (max-width: 1200px) {{
        [data-testid="stCustomComponentV1"] {{
            overflow-x: auto !important;
            scrollbar-width: thin;
        }}
        [data-testid="stCustomComponentV1"]::-webkit-scrollbar {{
            height: 4px;
        }}
        [data-testid="stCustomComponentV1"]::-webkit-scrollbar-thumb {{
            background: #29B5E8;
            border-radius: 2px;
        }}
    }}

    /* Selection status card - sticky header above tree */
    .selection-status-card {{
        position: sticky;
        top: 0;
        z-index: 100;
        background: linear-gradient(135deg, #E8F6FA 0%, #F0FAFC 100%);
        border-left: 4px solid #29B5E8;
        border-radius: 6px;
        padding: 12px 16px;
        margin-bottom: 12px;
        font-size: 14px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }}
    </style>
    """, unsafe_allow_html=True)

    # Apply dark mode attribute via JavaScript if enabled
    if dark_mode:
        st.markdown("""
        <script>
        document.documentElement.setAttribute('data-theme', 'dark');
        </script>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <script>
        document.documentElement.removeAttribute('data-theme');
        </script>
        """, unsafe_allow_html=True)

    # Inject tooltip and skeleton CSS
    inject_tooltip_css()
    inject_skeleton_css()
    # Inject expander state persistence
    inject_expander_state_js()


def inject_expander_state_js():
    """Inject JavaScript to persist expander open/closed state across reruns."""
    st.markdown("""
    <script>
    (function() {
        const STORAGE_KEY = 'pbi_expander_states_v2';
        let isApplying = false;

        // Get stored states from localStorage
        function getStoredStates() {
            try {
                return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
            } catch (e) {
                return {};
            }
        }

        // Save state to localStorage
        function saveState(key, isOpen) {
            if (isApplying) return; // Don't save during apply phase
            const states = getStoredStates();
            states[key] = isOpen;
            localStorage.setItem(STORAGE_KEY, JSON.stringify(states));
        }

        // Get stable key from expander label (remove dynamic parts like counts)
        function getExpanderKey(details) {
            const summary = details.querySelector('summary');
            if (!summary) return null;

            let text = summary.textContent.trim();
            // Skip leading non-letter characters (emojis, icons, etc)
            text = text.replace(/^[^A-Za-z]+/, '');
            // Extract just the main label before parentheses or numbers
            // e.g., "Relationships (0/2 selected)" -> "Relationships"
            // e.g., "Selected Objects (5 objects, 73 columns)" -> "Selected Objects"
            // e.g., "Schema Diagram" -> "Schema Diagram"
            const match = text.match(/^([A-Za-z][A-Za-z\\s\\-]+?)(?:\\s*[\\(\\[0-9]|$)/);
            if (match) {
                return match[1].trim();
            }
            // Fallback: first 20 chars
            return text.substring(0, 20).trim();
        }

        // Apply stored states to expanders
        function applyStoredStates() {
            isApplying = true;
            const states = getStoredStates();
            const expanders = document.querySelectorAll('details[data-testid="stExpander"]');

            expanders.forEach(details => {
                const key = getExpanderKey(details);
                if (key && states.hasOwnProperty(key)) {
                    if (details.open !== states[key]) {
                        details.open = states[key];
                    }
                }
            });
            isApplying = false;
        }

        // Listen for expander toggles
        function setupListeners() {
            document.addEventListener('toggle', function(e) {
                if (e.target.matches('details[data-testid="stExpander"]')) {
                    const key = getExpanderKey(e.target);
                    if (key) {
                        saveState(key, e.target.open);
                    }
                }
            }, true);
        }

        // Debounce function
        let applyTimeout = null;
        function debouncedApply() {
            if (applyTimeout) clearTimeout(applyTimeout);
            applyTimeout = setTimeout(applyStoredStates, 100);
        }

        // Initialize
        function init() {
            setupListeners();
            // Apply states after DOM is ready
            debouncedApply();
            // Watch for Streamlit rerenders
            const observer = new MutationObserver((mutations) => {
                // Only apply if new expanders were added
                for (const mutation of mutations) {
                    if (mutation.addedNodes.length > 0) {
                        debouncedApply();
                        break;
                    }
                }
            });
            observer.observe(document.body, { childList: true, subtree: true });
        }

        // Run when DOM is ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', init);
        } else {
            init();
        }
    })();
    </script>
    """, unsafe_allow_html=True)


def get_wizard_step() -> int:
    """Get current wizard step, initializing to 0 if not set.

    The wizard has 3 steps (0-2):
        0: Review Selected Objects (home page - objects selected via sidebar)
        1: Design Data Model
        2: Download PBI Workbook

    Returns:
        Current wizard step index (0-2).
    """
    if "wizard_step" not in st.session_state:
        st.session_state.wizard_step = 0
    return st.session_state.wizard_step


def show_progress_indicator():
    """Display 3-step clickable progress indicator."""
    has_metadata = bool(st.session_state.get("views_metadata"))
    metadata_count = len(st.session_state.get("views_metadata", []))
    has_relationships = metadata_count <= 1 or st.session_state.get("selected_relationships") is not None

    current_step = get_wizard_step()

    # Create step items - disable steps that aren't accessible yet
    # Note: Object selection is now done via sidebar, not a separate step
    # Static progress indicator (non-interactive to avoid sac.tree interaction bug)
    steps = [
        ("1. Review Selected Objects", True),
        ("2. Design Data Model", has_metadata),
        ("3. Generate Output", has_relationships),
    ]

    # Build HTML for static step indicator
    step_html = '<div style="display: flex; justify-content: space-between; align-items: center; margin: 4px 0;">'
    for i, (title, enabled) in enumerate(steps):
        is_current = i == current_step
        is_completed = i < current_step
        is_disabled = not enabled

        # Colors
        if is_current:
            color = "#29B5E8"  # Snowflake blue
            bg_color = "#E6F7FC"
            font_weight = "600"
        elif is_completed:
            color = "#52c41a"  # Green
            bg_color = "#f6ffed"
            font_weight = "normal"
        elif is_disabled:
            color = "#d9d9d9"
            bg_color = "transparent"
            font_weight = "normal"
        else:
            color = "#666"
            bg_color = "transparent"
            font_weight = "normal"

        step_html += f'''
        <div style="flex: 1; text-align: center; padding: 8px 12px; border-radius: 4px; background: {bg_color};">
            <span style="color: {color}; font-weight: {font_weight}; font-size: 14px;">{title}</span>
        </div>
        '''
        # Add connector line between steps
        if i < len(steps) - 1:
            line_color = "#52c41a" if is_completed else "#d9d9d9"
            step_html += f'<div style="flex: 0.5; height: 2px; background: {line_color};"></div>'

    step_html += '</div>'
    st.markdown(step_html, unsafe_allow_html=True)


# Load SVG icons as base64 for inline display
def load_svg_icon(icon_name: str) -> str:
    """Load SVG icon and return as base64 data URI."""
    img_dir = Path(__file__).parent / "img"
    svg_path = img_dir / f"{icon_name}.svg"
    if svg_path.exists():
        svg_content = svg_path.read_text(encoding="utf-8")
        b64 = base64.b64encode(svg_content.encode()).decode()
        return f"data:image/svg+xml;base64,{b64}"
    return ""


# Preload icons at module level
ICON_DATA = {
    "table": load_svg_icon("table"),
    "view": load_svg_icon("view"),
    "cube": load_svg_icon("cube"),
    "database": load_svg_icon("database"),
    "schema": load_svg_icon("schema"),
}

# Map object types to icon keys
OBJECT_TYPE_ICONS = {
    "SEMANTIC_VIEW": "cube",
    "VIEW": "view",
    "TABLE": "table"
}


def get_icon_html(icon_key: str, size: int = 16) -> str:
    """Get HTML img tag for a preloaded SVG icon.

    Icons are preloaded at module level in ICON_DATA for performance.

    Args:
        icon_key: Key from ICON_DATA (e.g., 'table', 'view', 'cube')
        size: Icon size in pixels (default 16)

    Returns:
        HTML img tag string, or empty string if icon not found.
    """
    data_uri = ICON_DATA.get(icon_key, "")
    if data_uri:
        return f'<img src="{data_uri}" width="{size}" height="{size}" style="vertical-align: middle; margin-right: 4px;">'
    return ""


def init_session_state():
    """Initialize Streamlit session state variables for the wizard.

    This function now uses the centralized AppState from session_manager.py
    as the source of truth, with bidirectional sync to legacy session_state
    keys for backwards compatibility.

    The AppState provides:
        - Type-safe access to all state variables
        - Centralized state management
        - Gradual migration path from legacy session_state

    State Categories (managed via AppState):
        Selection State (AppState.selection):
            - selected_objects: List of (db, schema, name, obj_type) tuples
            - views_metadata: List of SemanticViewMetadata objects loaded

        Tree Navigation State (AppState.tree):
            - loaded_schemas: Cache of schemas per database
            - loaded_objects: Cache of objects per (db, schema) pair
            - expanded_nodes: List of expanded tree node IDs
            - reset_counter: Counter to force tree component reset

        Data Model State (AppState.model):
            - selected_relationships: Dict of relationship toggles
            - manual_relationships: User-created relationships
            - bridge_relationships: Bridge table relationships
            - active_relationship_choices: Conflict resolution choices

        Configuration State (AppState.config):
            - pbi_mode: Power BI mode ('DirectQuery' or 'Import')
            - dark_mode: Theme toggle (False=Light, True=Dark)

        UI State (AppState.ui):
            - show_add_rel_form: Add relationship form visibility
            - editing_rel_id: Currently editing relationship
            - search_filter: Current search text
    """
    # Use the new centralized state initialization
    # This handles migration and sync in one call
    init_app_state()

    # Ensure legacy keys exist for backwards compatibility
    # (init_app_state syncs AppState to these, but some may not be in the map)
    if "wizard_step" not in st.session_state:
        st.session_state.wizard_step = 0


def toggle_object_selection(database: str, schema: str, name: str, object_type: ObjectType):
    """Toggle an object in the selection list."""
    obj_tuple = (database, schema, name, object_type)
    if obj_tuple in st.session_state.selected_objects:
        st.session_state.selected_objects.remove(obj_tuple)
    else:
        st.session_state.selected_objects.append(obj_tuple)


def is_object_selected(database: str, schema: str, name: str, object_type: ObjectType) -> bool:
    """Check if an object is currently selected."""
    return (database, schema, name, object_type) in st.session_state.selected_objects


def matches_search(search_term: str, database: str, schema: str = "", obj_name: str = "") -> bool:
    """Check if any part of the fully qualified name matches the search term."""
    if not search_term:
        return True
    full_name = f"{database}.{schema}.{obj_name}".upper()
    return search_term in full_name


def build_tree_items(databases: list[str], search_term: str = "") -> tuple[list, dict]:
    """
    Build tree items for sac.tree component.
    Returns (items, label_map) where label_map maps labels to metadata.
    """
    items = []
    label_map = {}  # Maps label -> (type, db, schema, name, obj_type)

    for db in databases:
        # Skip databases that don't match search
        if search_term:
            db_matches = search_term in db.upper()
            has_matching_children = False
            if db in st.session_state.loaded_schemas:
                for schema in st.session_state.loaded_schemas[db]:
                    if matches_search(search_term, db, schema):
                        has_matching_children = True
                        break
                    schema_key = (db, schema)
                    if schema_key in st.session_state.loaded_objects:
                        for obj in st.session_state.loaded_objects[schema_key]:
                            if matches_search(search_term, db, schema, obj.name):
                                has_matching_children = True
                                break
            if not db_matches and not has_matching_children:
                continue

        db_label = db
        label_map[db_label] = ("database", db, None, None, None)
        db_children = []

        # Add schemas if loaded
        if db in st.session_state.loaded_schemas:
            for schema in st.session_state.loaded_schemas[db]:
                if search_term:
                    schema_matches = matches_search(search_term, db, schema)
                    schema_key = (db, schema)
                    has_matching_objects = False
                    if schema_key in st.session_state.loaded_objects:
                        for obj in st.session_state.loaded_objects[schema_key]:
                            if matches_search(search_term, db, schema, obj.name):
                                has_matching_objects = True
                                break
                    if not schema_matches and not has_matching_objects:
                        continue

                # Always use qualified schema label to prevent collisions
                # Schema names can collide with database names (e.g., "RAW" db vs "RAW" schema)
                schema_label = f"{db}.{schema}"
                label_map[schema_label] = ("schema", db, schema, None, None)
                schema_children = []

                schema_key = (db, schema)
                if schema_key in st.session_state.loaded_objects:
                    # Objects loaded - show them
                    for obj in st.session_state.loaded_objects[schema_key]:
                        if search_term and not matches_search(search_term, db, schema, obj.name):
                            continue

                        # Always use qualified object label to prevent collisions
                        # Object names can collide across schemas/databases (e.g., "CUSTOMERS")
                        obj_label = f"{db}.{schema}.{obj.name}"
                        label_map[obj_label] = ("object", db, schema, obj.name, obj.object_type)

                        # Icon and tag based on object type (Snowflake Design System colors)
                        if obj.object_type == "SEMANTIC_VIEW":
                            obj_icon = sac.BsIcon(name="box", color="#7254A3")  # Purple Moon
                            obj_tag = sac.Tag("Semantic", color="purple")
                        elif obj.object_type == "VIEW":
                            obj_icon = sac.BsIcon(name="eye", color="#FF9F36")  # Valencia Orange
                            obj_tag = sac.Tag("View", color="orange")
                        else:
                            obj_icon = sac.BsIcon(name="table", color="#75CDD7")  # Star Blue
                            obj_tag = sac.Tag("Table", color="cyan")

                        schema_children.append(
                            sac.TreeItem(obj_label, icon=obj_icon, tag=obj_tag)
                        )
                else:
                    # Objects not loaded - placeholder (will load on expand)
                    schema_children.append(
                        sac.TreeItem("⏳ Loading objects...", disabled=True)
                    )

                db_children.append(
                    sac.TreeItem(schema_label, icon="folder2-open", children=schema_children)
                )
        else:
            # Schemas not loaded - placeholder (will load on expand)
            db_children.append(
                sac.TreeItem("⏳ Loading schemas...", disabled=True)
            )

        items.append(
            sac.TreeItem(db_label, icon="database", children=db_children)
        )

    return items, label_map


# =============================================================================
# Tree Navigation Helper Functions
# =============================================================================

def _clean_tree_session_state() -> None:
    """Clean up corrupted session state that could cause tree errors.

    Filters out invalid entries from selected_objects, expanded_nodes,
    and removes tree keys with None values.
    """
    # Filter out invalid entries from selected_objects
    if "selected_objects" in st.session_state:
        valid_objects = []
        for item in st.session_state.selected_objects:
            if item is not None and isinstance(item, (list, tuple)) and len(item) >= 4:
                if all(v is not None for v in item[:4]):
                    valid_objects.append(item)
        st.session_state.selected_objects = valid_objects

    # Clean up expanded_nodes
    if "expanded_nodes" in st.session_state:
        st.session_state.expanded_nodes = [
            n for n in st.session_state.expanded_nodes
            if n is not None and isinstance(n, str)
        ]

    # Clean up ALL tree keys that have None values
    tree_keys_to_delete = []
    for key in list(st.session_state.keys()):
        if key.startswith("object_tree_"):
            val = st.session_state[key]
            if val is None:
                tree_keys_to_delete.append(key)
            elif isinstance(val, list) and any(v is None for v in val):
                tree_keys_to_delete.append(key)
    for key in tree_keys_to_delete:
        del st.session_state[key]


def _get_pending_metadata_count() -> int:
    """Calculate how many selected objects still need metadata loaded.

    Returns:
        Count of objects that haven't had metadata loaded yet
    """
    if not st.session_state.selected_objects:
        return 0

    loaded_keys = {(m.database, m.schema, m.view) for m in st.session_state.views_metadata}
    pending_count = sum(
        1 for db, schema, name, _ in st.session_state.selected_objects
        if (db, schema, name) not in loaded_keys
    )
    return pending_count


def _get_spinner_gif_base64() -> str:
    """Get the Snowflake spinner GIF as a base64 string.

    Returns:
        Base64 encoded GIF data, or empty string if file not found
    """
    import base64
    from pathlib import Path

    gif_path = Path(__file__).parent / "img" / "loading_spinner.gif"
    if gif_path.exists():
        return base64.b64encode(gif_path.read_bytes()).decode('utf-8')
    return ""


def _render_status_card_html(
    selected_count: int,
    is_read_only: bool = False,
    pending_load_count: int = 0
) -> str:
    """Generate HTML for the selection status card.

    Args:
        selected_count: Number of selected objects
        is_read_only: If True, show locked state
        pending_load_count: Number of objects pending load

    Returns:
        HTML string for the status card
    """
    if selected_count == 0:
        return ""

    # Determine if loading
    is_loading = pending_load_count > 0 and not is_read_only

    # Build status content
    if is_read_only:
        icon_html = '<span style="font-size:18px;">🔒</span>'
        status_text = f"<strong>{selected_count}</strong> object(s) locked"
    elif is_loading:
        # Use Snowflake spinner GIF during loading
        gif_b64 = _get_spinner_gif_base64()
        if gif_b64:
            icon_html = f'<img src="data:image/gif;base64,{gif_b64}" width="20" height="20" style="vertical-align: middle;" />'
        else:
            icon_html = '<span style="font-size:18px;">⏳</span>'
        status_text = f"<strong>{selected_count}</strong> selected, <strong style=\"color:#29B5E8\">{pending_load_count}</strong> loading..."
    else:
        icon_html = '<span style="font-size:18px;">✓</span>'
        status_text = f"<strong>{selected_count}</strong> object(s) selected"

    # Add CSS for loading state
    loading_css = ""
    if is_loading:
        loading_css = """
        <style>
            .selection-status-card.loading {
                border-left-color: #29B5E8 !important;
                background: linear-gradient(135deg, #E8F6FA 0%, #F0FAFC 100%) !important;
            }
        </style>
        """

    card_class = "selection-status-card loading" if is_loading else "selection-status-card"

    return f"""
        {loading_css}
        <div class="{card_class}">
            <span style="margin-right:10px;">{icon_html}</span>
            {status_text}
        </div>
    """


def render_selection_status_header(is_read_only: bool = False, pending_load_count: int = 0):
    """Render sticky selection status card above the tree.

    Shows count of selected objects and loading status with Snowflake branding.

    Args:
        is_read_only: If True, show locked state for Step 3
        pending_load_count: Number of objects pending metadata load

    Returns:
        Placeholder that can be updated with loading state
    """
    selected_count = len(st.session_state.selected_objects)

    # Create a placeholder that can be updated later
    placeholder = st.empty()

    html = _render_status_card_html(selected_count, is_read_only, pending_load_count)
    if html:
        placeholder.markdown(html, unsafe_allow_html=True)

    return placeholder


def update_status_header_loading(placeholder, pending_count: int) -> None:
    """Update the status header to show loading state.

    Args:
        placeholder: The st.empty() placeholder from render_selection_status_header
        pending_count: Number of objects being loaded
    """
    selected_count = len(st.session_state.selected_objects)
    html = _render_status_card_html(selected_count, is_read_only=False, pending_load_count=pending_count)
    if html:
        placeholder.markdown(html, unsafe_allow_html=True)


def _get_pre_selected_labels() -> list[str] | None:
    """Get list of pre-selected object labels from session state.

    Returns fully-qualified object labels (db.schema.name) to match
    the label_map keys used in build_tree_items().

    Returns:
        List of qualified object labels to pre-select, or None if empty.
    """
    pre_selected = []
    exec_id = st.session_state.get("_exec_id", 0)

    logger.debug(f"[EXEC:{exec_id}][PRE_SELECT] selected_objects count: {len(st.session_state.selected_objects)}")

    for item in st.session_state.selected_objects:
        if item is None or not isinstance(item, (list, tuple)) or len(item) < 4:
            continue
        db, schema, name, obj_type = item
        if name is not None and isinstance(name, str):
            # Use fully-qualified label to match label_map keys
            qualified_label = f"{db}.{schema}.{name}"
            pre_selected.append(qualified_label)

    logger.debug(f"[EXEC:{exec_id}][PRE_SELECT] Qualified labels to pass to tree: {len(pre_selected)}, first 5: {pre_selected[:5]}")

    # Return None instead of empty list to avoid component issues
    return pre_selected if pre_selected else None


def _get_open_index() -> list[str] | None:
    """Get list of expanded node labels for the tree component.

    Returns:
        List of expanded node labels, or None if empty.
    """
    # First, ensure parent nodes of selected objects are expanded
    # This is critical for read-only mode (Step 3) to show checkmarks
    _ensure_selected_parents_expanded()

    if not st.session_state.expanded_nodes:
        return None

    open_index = [
        n for n in st.session_state.expanded_nodes
        if n is not None and isinstance(n, str)
    ]
    return open_index if open_index else None


def _ensure_selected_parents_expanded() -> None:
    """Ensure parent databases and schemas of selected objects are in expanded_nodes.

    This is critical for the tree to show checkmarks on selected objects.
    If parents aren't expanded, the object labels won't be in the tree,
    and pre_selected filtering will remove them.
    """
    if not st.session_state.selected_objects:
        return

    # Collect all unique databases and schemas from selected objects
    databases_to_expand = set()
    schemas_to_expand = set()

    for item in st.session_state.selected_objects:
        if item is None or not isinstance(item, (list, tuple)) or len(item) < 4:
            continue
        db, schema, name, obj_type = item
        if db:
            databases_to_expand.add(db)
        if db and schema:
            # Use qualified schema label to match TreeItem labels
            schemas_to_expand.add(f"{db}.{schema}")

    # Add to expanded_nodes if not already there
    for db in databases_to_expand:
        if db not in st.session_state.expanded_nodes:
            st.session_state.expanded_nodes.append(db)

    for schema_label in schemas_to_expand:
        if schema_label not in st.session_state.expanded_nodes:
            st.session_state.expanded_nodes.append(schema_label)


def _parse_tree_result(result) -> tuple[list[str], list[str]]:
    """Parse the result from sac.tree component.

    Handles both the new TreeResult namedtuple format (from forked component)
    and the old list format.

    Args:
        result: The result from sac.tree()

    Returns:
        Tuple of (selected_labels, expanded_labels)
    """
    if hasattr(result, 'selected') and hasattr(result, 'expanded'):
        # New forked component - TreeResult namedtuple
        selected = result.selected if isinstance(result.selected, list) else [result.selected] if result.selected else []
        expanded = result.expanded or []
    else:
        # Fallback for old component format
        selected = result if isinstance(result, list) else [result] if result else []
        expanded = []

    # Filter out None values and placeholder labels
    selected = [s for s in selected if s is not None and not str(s).startswith("⏳")]

    return selected, expanded


def _sync_expansion_state(expanded: list[str], open_index: list[str] | None) -> None:
    """Synchronize expansion state between tree result and session state.

    CRITICAL FIX: The forked sac.tree component only sends expanded keys back to Python
    when the user manually clicks expand/collapse. When we pass open_index to tell the
    tree which nodes to expand, it expands them visually but doesn't notify Python.

    Therefore, we must ALWAYS merge open_index (what we told tree to expand) with any
    tree result to ensure lazy loading processes all expanded nodes.

    Args:
        expanded: Expanded nodes from tree result (may be empty even if nodes are visually expanded)
        open_index: Open index passed to tree component (these nodes ARE visually expanded)
    """
    exec_id = st.session_state.get("_exec_id", 0)
    current_expanded = set(e for e in expanded if e is not None) if expanded else set()
    saved_expanded = set(st.session_state.expanded_nodes) if st.session_state.expanded_nodes else set()
    passed_to_tree = set(open_index) if open_index else set()

    # CRITICAL: Always include what we passed as open_index since those nodes ARE visually
    # expanded in the tree, even if the component didn't report them back
    merged_expanded = current_expanded | passed_to_tree | saved_expanded

    logger.debug(f"[EXEC:{exec_id}][SYNC_EXPAND] tree_returned={len(current_expanded)}, passed={len(passed_to_tree)}, saved={len(saved_expanded)}, merged={len(merged_expanded)}")

    if current_expanded and current_expanded != passed_to_tree:
        # User explicitly expanded/collapsed - use tree result merged with passed
        st.session_state.expanded_nodes = list(current_expanded | passed_to_tree)
    elif merged_expanded:
        # No tree result but we have passed or saved state - preserve all
        st.session_state.expanded_nodes = list(merged_expanded)
    else:
        # No state at all
        st.session_state.expanded_nodes = []


def _process_lazy_loading(session, label_map: dict) -> bool:
    """Process expanded nodes and load data lazily.

    Loads schemas when a database is expanded, and loads objects when
    a schema is expanded.

    CRITICAL FIX: When a database is expanded and its schemas are loaded,
    we also add those schemas to expanded_nodes. This ensures that if
    the schema is visually expanded in the tree, its objects will be
    loaded in the next cycle.

    Args:
        session: Snowflake session
        label_map: Mapping of labels to metadata

    Returns:
        True if any data was loaded (requires rerun), False otherwise
    """
    exec_id = st.session_state.get("_exec_id", 0)
    needs_rerun = False
    expanded_to_process = list(st.session_state.expanded_nodes or [])  # Copy to allow modification

    logger.debug(f"[EXEC:{exec_id}][LAZY_LOAD] Processing {len(expanded_to_process)} expanded nodes: {expanded_to_process[:5]}")

    for label in expanded_to_process:
        if label not in label_map:
            continue
        meta = label_map[label]

        if meta[0] == "database":
            # Database expanded - load schemas
            db = meta[1]
            if db not in st.session_state.loaded_schemas:
                with snowflake_spinner(f"Loading schemas for {db}..."):
                    try:
                        schemas = get_schemas(session, db)
                        st.session_state.loaded_schemas[db] = schemas
                        needs_rerun = True
                        logger.debug(f"[EXEC:{exec_id}][LAZY_LOAD] Loaded {len(schemas)} schemas for {db}")

                        # CRITICAL: Auto-add loaded schemas to expanded_nodes
                        # This ensures objects will be loaded if schemas are visually expanded
                        for schema_name in schemas:
                            # Use qualified schema label to match TreeItem labels
                            qualified_schema = f"{db}.{schema_name}"
                            if qualified_schema not in st.session_state.expanded_nodes:
                                st.session_state.expanded_nodes.append(qualified_schema)
                                logger.debug(f"[EXEC:{exec_id}][LAZY_LOAD] Auto-expanded schema: {qualified_schema}")
                    except Exception as e:
                        st.error(f"Error loading schemas: {e}")
            else:
                # Schemas already loaded - ensure they're in expanded_nodes
                for schema_name in st.session_state.loaded_schemas.get(db, []):
                    qualified_schema = f"{db}.{schema_name}"
                    if qualified_schema not in st.session_state.expanded_nodes:
                        st.session_state.expanded_nodes.append(qualified_schema)

        elif meta[0] == "schema":
            # Schema expanded - load objects
            db, schema = meta[1], meta[2]
            schema_key = (db, schema)
            if schema_key not in st.session_state.loaded_objects:
                with snowflake_spinner(f"Loading objects for {schema}..."):
                    try:
                        objects = get_all_objects(session, db, schema)
                        st.session_state.loaded_objects[schema_key] = objects
                        needs_rerun = True
                        logger.debug(f"[EXEC:{exec_id}][LAZY_LOAD] Loaded {len(objects)} objects for {db}.{schema}")
                    except Exception as e:
                        st.error(f"Error loading objects: {e}")

    return needs_rerun


def _process_tree_selections(
    session,
    selected: list[str],
    label_map: dict
) -> bool:
    """Process tree selections and update session state.

    Handles object selections and schema-level cascade selections.
    Preserves selections for objects not visible in current tree (due to filter).

    Args:
        session: Snowflake session
        selected: List of selected labels from tree
        label_map: Mapping of labels to metadata

    Returns:
        True if schemas were loaded (requires rerun), False otherwise
    """
    needs_rerun = False

    logger.debug(f"[PROCESS_SEL] Input: {len(selected)} selected items from tree")
    logger.debug(f"[PROCESS_SEL] Current selected_objects: {len(st.session_state.selected_objects)}")

    # Build set of object labels currently visible in the tree
    visible_object_labels = set()
    for label, meta in label_map.items():
        if meta[0] == "object":
            visible_object_labels.add(meta[3])  # meta[3] is the object name

    logger.debug(f"[PROCESS_SEL] Visible objects in tree: {len(visible_object_labels)}")

    # Build set of selected databases from:
    # 1. Databases directly selected in the tree (database-level selection)
    # 2. Databases inferred from object-level selections
    # This ensures preservation works when user selects a new database via filter
    selected_databases = set()
    for label in selected:
        if label in label_map:
            meta = label_map[label]
            if meta[0] == "database":
                # Database directly selected - include it
                selected_databases.add(meta[1])
            elif meta[0] == "object":
                # Object selected - infer database from it
                selected_databases.add(meta[1])  # meta[1] is database name

    logger.debug(f"[PROCESS_SEL] Selected databases: {selected_databases}")

    # Preserve selections for objects NOT visible in current tree (due to filter)
    # Skip preservation if we just reset - start completely fresh
    #
    # IMPORTANT: When filter is active, preserve ALL hidden selections.
    # This enables multi-database selection: user selects ACME, filters on "tpch",
    # selects TPCH - both databases should be kept (51 total objects).
    # When filter is NOT active, only preserve if database is still selected.
    filter_active = bool(st.session_state.get("search_filter", "").strip())

    if st.session_state.get("_just_reset", False):
        preserved_selections = []
        st.session_state._just_reset = False
        logger.debug("[PROCESS_SEL] Just reset - not preserving any selections")
    else:
        preserved_selections = []
        for db, schema, name, obj_type in st.session_state.selected_objects:
            is_hidden = name not in visible_object_labels
            if filter_active:
                # Filter active: preserve ALL hidden selections (multi-database support)
                if is_hidden:
                    preserved_selections.append((db, schema, name, obj_type))
            else:
                # No filter: only preserve if database is still selected
                if is_hidden and db in selected_databases:
                    preserved_selections.append((db, schema, name, obj_type))
        logger.debug(f"[PROCESS_SEL] Preserved (hidden, filter_active={filter_active}): {len(preserved_selections)}")

    # Process new selections from the current tree
    new_object_selections = []

    for label in selected:
        if label not in label_map:
            continue
        meta = label_map[label]

        # Database selected - auto-load all schemas and objects
        if meta[0] == "database":
            db = meta[1]
            loaded_new_data = False

            # Auto-load schemas if not loaded
            if db not in st.session_state.loaded_schemas:
                with snowflake_spinner(f"Loading schemas for {db}..."):
                    try:
                        schemas = get_schemas(session, db)
                        st.session_state.loaded_schemas[db] = schemas
                        loaded_new_data = True
                    except Exception as e:
                        st.error(f"Error loading schemas for {db}: {e}")
                        continue

            # Add database to expanded nodes
            if db not in st.session_state.expanded_nodes:
                st.session_state.expanded_nodes.append(db)

            # Auto-load objects for each schema and select them
            schemas_to_load = st.session_state.loaded_schemas.get(db, [])
            for schema_name in schemas_to_load:
                schema_key = (db, schema_name)

                if schema_key not in st.session_state.loaded_objects:
                    with snowflake_spinner(f"Loading objects for {schema_name}..."):
                        try:
                            objects = get_all_objects(session, db, schema_name)
                            st.session_state.loaded_objects[schema_key] = objects
                            loaded_new_data = True
                        except Exception as e:
                            st.error(f"Error loading objects for {schema_name}: {e}")
                            continue

                # Add schema to expanded nodes (use qualified label)
                qualified_schema = f"{db}.{schema_name}"
                if qualified_schema not in st.session_state.expanded_nodes:
                    st.session_state.expanded_nodes.append(qualified_schema)

                # Select all objects in this schema
                for obj in st.session_state.loaded_objects.get(schema_key, []):
                    new_object_selections.append((db, schema_name, obj.name, obj.object_type))

            # Only trigger rerun if we actually loaded new data
            if loaded_new_data:
                needs_rerun = True
            continue

        if meta[0] == "object":
            _, db, schema, name, obj_type = meta
            new_object_selections.append((db, schema, name, obj_type))

        elif meta[0] == "schema":
            # Schema selected - auto-load and select all objects
            db = meta[1]
            schema_name = meta[2]
            schema_key = (db, schema_name)

            # Auto-load if not loaded
            if schema_key not in st.session_state.loaded_objects:
                with snowflake_spinner(f"Loading objects for {schema_name}..."):
                    try:
                        objects = get_all_objects(session, db, schema_name)
                        st.session_state.loaded_objects[schema_key] = objects
                        needs_rerun = True  # Only rerun if we loaded new data
                    except Exception as e:
                        st.error(f"Error loading objects for {schema_name}: {e}")
                        continue

                # Add schema to expanded nodes (use qualified label)
                qualified_schema = f"{db}.{schema_name}"
                if qualified_schema not in st.session_state.expanded_nodes:
                    st.session_state.expanded_nodes.append(qualified_schema)

            # Select all objects
            for obj in st.session_state.loaded_objects.get(schema_key, []):
                new_object_selections.append((db, schema_name, obj.name, obj.object_type))

    # Combine preserved + new selections (deduplicated)
    all_selections = preserved_selections + new_object_selections
    seen = set()
    unique_selections = []
    for item in all_selections:
        if item not in seen:
            seen.add(item)
            unique_selections.append(item)

    exec_id = st.session_state.get("_exec_id", 0)
    logger.debug(f"[EXEC:{exec_id}][PROCESS_SEL] new_object_selections={len(new_object_selections)}, unique_selections={len(unique_selections)}")

    # Check if selections actually changed (to trigger rerun for deselections)
    old_selections = set(st.session_state.selected_objects)
    new_selections = set(unique_selections)
    selections_changed = old_selections != new_selections

    added = new_selections - old_selections
    removed = old_selections - new_selections
    logger.debug(f"[EXEC:{exec_id}][PROCESS_SEL] Changes: added={len(added)}, removed={len(removed)}, changed={selections_changed}")
    if removed:
        logger.debug(f"[EXEC:{exec_id}][PROCESS_SEL] Removed items: {list(removed)[:5]}")

    st.session_state.selected_objects = unique_selections
    logger.debug(f"[EXEC:{exec_id}][STATE_UPDATE] selected_objects now has {len(st.session_state.selected_objects)} items")

    # Trigger rerun if selections changed (including deselections)
    # NOTE: Do NOT increment tree_reset_counter here - that causes the tree to re-mount
    # and ignore the index prop, creating a deselection loop. Only reset on explicit user action.
    if selections_changed:
        logger.debug(f"[EXEC:{exec_id}][PROCESS_SEL] Selections changed - setting needs_rerun=True")
        needs_rerun = True

    return needs_rerun


def _sync_metadata_with_selections(session) -> bool:
    """Synchronize views_metadata with selected_objects.

    Removes metadata for deselected objects and loads metadata for newly
    selected objects.

    Args:
        session: Snowflake session for loading metadata

    Returns:
        True if metadata changed (added or removed), False otherwise.
        Caller should trigger full rerun if True (main content needs update).
    """
    exec_id = st.session_state.get("_exec_id", 0)

    # Track original count to detect removals
    original_count = len(st.session_state.views_metadata)

    # Build key sets for comparison
    selected_keys = {(db, schema, name) for db, schema, name, _ in st.session_state.selected_objects}
    loaded_keys = {(m.database, m.schema, m.view) for m in st.session_state.views_metadata}

    logger.debug(f"[EXEC:{exec_id}][METADATA_SYNC] selected_keys={len(selected_keys)}, loaded_keys={len(loaded_keys)}")
    if selected_keys:
        logger.debug(f"[EXEC:{exec_id}][METADATA_SYNC] First 3 selected: {list(selected_keys)[:3]}")
    if loaded_keys:
        logger.debug(f"[EXEC:{exec_id}][METADATA_SYNC] First 3 loaded: {list(loaded_keys)[:3]}")

    # Remove metadata for deselected objects
    st.session_state.views_metadata = [
        m for m in st.session_state.views_metadata
        if (m.database, m.schema, m.view) in selected_keys
    ]
    metadata_removed = len(st.session_state.views_metadata) < original_count

    # Clean up orphaned relationships after deselecting objects
    current_objects = {m.view for m in st.session_state.views_metadata}

    # Remove manual relationships involving deselected objects
    if "manual_relationships" in st.session_state:
        st.session_state.manual_relationships = [
            rel for rel in st.session_state.manual_relationships
            if rel.from_table in current_objects and rel.to_table in current_objects
        ]

    # Remove bridge relationships involving deselected objects
    if "bridge_relationships" in st.session_state:
        st.session_state.bridge_relationships = [
            rel for rel in st.session_state.bridge_relationships
            if rel.from_table in current_objects and rel.to_table in current_objects
        ]

    # Clear selected_relationships state to force regeneration
    # (relationships will be re-detected on next render)
    if "selected_relationships" in st.session_state and current_objects:
        # Filter to only keep relationship IDs for current objects
        rel_ids_to_keep = {
            rid for rid, selected in st.session_state.selected_relationships.items()
            if any(obj in rid for obj in current_objects)
        }
        st.session_state.selected_relationships = {
            rid: selected for rid, selected in st.session_state.selected_relationships.items()
            if rid in rel_ids_to_keep
        }

    # Clean up active_relationship_choices for conflict pairs
    if "active_relationship_choices" in st.session_state and current_objects:
        st.session_state.active_relationship_choices = {
            key: val for key, val in st.session_state.active_relationship_choices.items()
            if any(obj in key for obj in current_objects)
        }

    # Load metadata for newly selected objects
    objects_to_load = [
        (db, schema, name, obj_type)
        for db, schema, name, obj_type in st.session_state.selected_objects
        if (db, schema, name) not in loaded_keys
    ]

    metadata_added = False
    if objects_to_load:
        logger.debug(f"[EXEC:{exec_id}][METADATA_SYNC] Loading {len(objects_to_load)} objects: {objects_to_load[:3]}")

        # Update status header to show loading state
        placeholder = st.session_state.get("_status_header_placeholder")
        if placeholder:
            update_status_header_loading(placeholder, len(objects_to_load))

        try:
            with snowflake_spinner(f"Loading metadata for {len(objects_to_load)} object(s)..."):
                new_metadata = get_metadata_batch_parallel(session, objects_to_load, max_workers=8)
                st.session_state.views_metadata.extend(new_metadata)
            metadata_added = True
            logger.debug(f"[EXEC:{exec_id}][METADATA_SYNC] Loaded {len(objects_to_load)} objects, total metadata: {len(st.session_state.views_metadata)}")
        except Exception as e:
            logger.error(f"[EXEC:{exec_id}][METADATA_SYNC] Failed to load metadata: {e}", exc_info=True)
            st.error(f"Failed to load metadata for selected objects: {e}")

    # Return True if main content needs update (metadata changed)
    return metadata_added or metadata_removed


def render_tree_navigation(session, databases: list[str]):
    """Render the database/schema/object tree navigation using sac.tree with lazy loading on expand.

    Uses @st.fragment to isolate tree interactions from main content reruns,
    improving performance and eliminating header flicker.
    """
    # Header rendered OUTSIDE fragment - won't re-render on tree interactions
    st.markdown(f"### {icon_header('select', 'Select Objects', size=24)}", unsafe_allow_html=True)

    @st.fragment
    def _tree_fragment():
        """Fragment for tree interactions - only this reruns on selection/expansion."""
        # Check if tree should be read-only (on Generate step)
        # Steps: 0=Review, 1=Data Model, 2=Generate Output
        # Lock selections on Generate step to prevent changes during file generation
        wizard_step = st.session_state.get("wizard_step", 0)
        is_read_only = wizard_step >= 2

        # Calculate pending metadata load count BEFORE rendering header
        pending_load_count = _get_pending_metadata_count()

        # Selection status header (sticky, above tree)
        # Returns a placeholder that can be updated during metadata loading
        status_placeholder = render_selection_status_header(is_read_only, pending_load_count)

        # Store placeholder in session state so _sync_metadata_with_selections can update it
        st.session_state._status_header_placeholder = status_placeholder

        # Clean up any corrupted session state
        _clean_tree_session_state()

        # Search filter
        search_term = st.text_input(
            "🔍 Filter databases",
            placeholder="Type to filter by database name...",
            key="search_filter"
        ).strip().upper()

        # Track filter changes to handle different scenarios:
        # - Filter ACTIVATED (empty -> text or text -> different text): show unchecked
        # - Filter CLEARED (text -> empty): show checkmarks for selected databases
        prev_filter = st.session_state.get("_prev_search_filter", "")
        filter_just_changed = (search_term != prev_filter)
        filter_was_cleared = filter_just_changed and not search_term and prev_filter
        filter_was_activated = filter_just_changed and search_term
        st.session_state._prev_search_filter = search_term
        if filter_just_changed:
            logger.debug(f"[TREE_NAV] Filter changed: '{prev_filter}' -> '{search_term}' (cleared={filter_was_cleared}, activated={filter_was_activated})")

        if not databases:
            st.warning("No databases found.")
            return

        # Build tree items
        tree_items, label_map = build_tree_items(databases, search_term)

        if not tree_items:
            st.info("No matching databases found.")
            return

        # Get pre-selection and expansion state
        pre_selected = _get_pre_selected_labels()
        open_index = _get_open_index()

        # Check if pre_selected labels actually exist in tree items
        # Only pass labels that exist in tree to avoid sac.tree confusion
        all_tree_labels = set()
        def collect_labels(items):
            for item in items:
                all_tree_labels.add(item.label)
                if item.children:
                    collect_labels(item.children)
        collect_labels(tree_items)

        # Track if we expect selections but tree can't show them (collapsed state or filtered)
        expected_selections_missing = False
        logger.debug(f"[TREE_NAV] all_tree_labels count: {len(all_tree_labels)}")

        # Handle filter scenarios differently:
        # - Filter ACTIVATED: show databases unchecked (user starts fresh in filtered view)
        # - Filter CLEARED: show checkmarks for databases with selections
        # - No filter change: normal logic
        if filter_was_activated:
            # User typed a filter - show filtered items UNCHECKED
            # User must explicitly click to select in filtered view
            pre_selected = []
            logger.debug(f"[TREE_NAV] Filter activated - forcing empty pre_selected (unchecked)")
        elif pre_selected:
            # Normal case or filter cleared - compute proper pre_selected with parent labels
            # Filter to only labels that exist in tree
            valid_pre_selected = [l for l in pre_selected if l in all_tree_labels]
            missing_count = len(pre_selected) - len(valid_pre_selected)
            logger.debug(f"[TREE_NAV] pre_selected={len(pre_selected)}, valid={len(valid_pre_selected)}, missing={missing_count}")

            # If object labels aren't visible (collapsed), add their parent labels instead
            # This ensures checkmarks show on database/schema when children are selected but collapsed
            if missing_count > 0:
                # Group missing labels by database and schema
                parent_labels_to_add = set()
                for label in pre_selected:
                    if label not in all_tree_labels:
                        # Parse "DB.SCHEMA.OBJECT" format
                        parts = label.split(".")
                        if len(parts) >= 2:
                            db_label = parts[0]  # Database label
                            schema_label = f"{parts[0]}.{parts[1]}"  # Schema label
                            # Add whichever parent exists in tree
                            if schema_label in all_tree_labels:
                                parent_labels_to_add.add(schema_label)
                            elif db_label in all_tree_labels:
                                parent_labels_to_add.add(db_label)

                # Combine valid object labels with parent labels
                valid_pre_selected = list(set(valid_pre_selected) | parent_labels_to_add)
                logger.debug(f"[TREE_NAV] Added parent labels: {parent_labels_to_add}, total valid: {len(valid_pre_selected)}")

            # If most labels are missing, tree is in collapsed state
            if missing_count > len(pre_selected) // 2:
                expected_selections_missing = True
            # IMPORTANT: Pass empty list [] instead of None when no valid selections
            # This explicitly tells sac.tree "nothing is selected" rather than relying
            # on default/cached behavior which may auto-select items
            pre_selected = valid_pre_selected if valid_pre_selected else []
        else:
            # Ensure we pass empty list, not None
            pre_selected = []

        # Dynamic key for tree reset (e.g., after creating semantic view or explicit reset)
        # NOTE: We removed filter_hash from key because it caused tree to remount and ignore
        # the index parameter, resulting in lost checkmarks. Instead, we use filter_just_changed
        # guard to prevent processing stale selections when filter changes.
        tree_key = f"object_tree_{st.session_state.get('tree_reset_counter', 0)}"
        exec_id = st.session_state.get("_exec_id", 0)
        logger.debug(f"[EXEC:{exec_id}][TREE_INPUT] tree_key={tree_key}, index={len(pre_selected) if pre_selected else 0} items, tree_items={len(tree_items)}")

        # Show info message when selections are locked on Generate step
        if is_read_only:
            st.info("⚠️ Object selection is locked on the Generate step. Go back to modify selections.")

        # Render tree component
        # Note: We keep checkbox=True even in read-only mode because sac.tree doesn't support
        # a disabled state. Instead, we skip processing selection changes in read-only mode below.
        result = sac.tree(
            items=tree_items,
            index=pre_selected,
            open_index=open_index,
            label="Select objects:" if not is_read_only else "Selected objects (locked):",
            icon="diagram-3",
            color="#29B5E8" if not is_read_only else "#8A8A8A",  # Gray when locked
            open_all=False,
            checkbox=True,  # Keep checkboxes visible (changes ignored in read-only mode)
            checkbox_strict=False,  # Enable cascading: selecting parent selects all children
            show_line=True,
            return_index=False,
            key=tree_key
        )

        # Parse tree result and sync expansion state
        selected, expanded = _parse_tree_result(result)
        _sync_expansion_state(expanded, open_index)

        logger.debug(f"[EXEC:{exec_id}][TREE_OUTPUT] selected={len(selected)} items, first 5: {selected[:5]}")
        logger.debug(f"[EXEC:{exec_id}][TREE_EXPANDED] expanded_from_tree={len(expanded)}, expanded_nodes={len(st.session_state.expanded_nodes)}, first 3: {st.session_state.expanded_nodes[:3] if st.session_state.expanded_nodes else []}")
        logger.debug(f"[EXEC:{exec_id}][TREE_STATE] pre_selected was: {len(pre_selected) if pre_selected else 0} items")

        # Process lazy loading for expanded nodes
        needs_lazy_rerun = _process_lazy_loading(session, label_map)

        # CRITICAL FIX: Expand parent labels to child objects before comparison
        # With checkbox_strict=False (cascade mode), sac.tree returns parent labels when all children
        # are selected (e.g., returns 'TPCH_RICH_DB' instead of all 26 child objects).
        # We must expand these parent labels to get accurate add/remove detection.
        def expand_parent_labels(labels: set, lmap: dict) -> set:
            """Expand database/schema labels to their child object labels.

            IMPORTANT: Also includes the parent label itself if no children found.
            This ensures database selections are detected even before objects are loaded.
            """
            expanded_labels = set()
            for label in labels:
                meta = lmap.get(label)
                if not meta:
                    expanded_labels.add(label)
                    continue
                label_type = meta[0]
                if label_type == "object":
                    expanded_labels.add(label)
                elif label_type == "database":
                    # Find all objects under this database
                    db_name = meta[1]  # meta is (type, db, schema, name, obj_type) or similar
                    found_children = False
                    for other_label, other_meta in lmap.items():
                        if other_meta[0] == "object" and other_meta[1] == db_name:
                            expanded_labels.add(other_label)
                            found_children = True
                    # Keep database label if no children found (objects not loaded yet)
                    # This ensures new database selections are detected for auto-loading
                    if not found_children:
                        expanded_labels.add(label)
                elif label_type == "schema":
                    # Find all objects under this schema
                    db_name, schema_name = meta[1], meta[2]
                    found_children = False
                    for other_label, other_meta in lmap.items():
                        if other_meta[0] == "object" and other_meta[1] == db_name and other_meta[2] == schema_name:
                            expanded_labels.add(other_label)
                            found_children = True
                    # Keep schema label if no children found
                    if not found_children:
                        expanded_labels.add(label)
            return expanded_labels

        # Process tree selections (skip if lazy loading occurred or tree state is inconsistent)
        pre_set = set(pre_selected) if pre_selected else set()
        selected_set = set(selected)

        # Expand parent labels to children for accurate comparison
        expanded_selected = expand_parent_labels(selected_set, label_map)
        logger.debug(f"[EXEC:{exec_id}][TREE_EXPAND] raw={len(selected_set)}, expanded={len(expanded_selected)}")

        new_selections = expanded_selected - pre_set
        removed_selections = pre_set - expanded_selected

        logger.debug(f"[TREE_NAV] New selections (added): {len(new_selections)}: {list(new_selections)[:5]}")
        logger.debug(f"[TREE_NAV] Removed selections: {len(removed_selections)}: {list(removed_selections)[:5]}")

        # NOTE: We removed tree_state_mismatch check because it was blocking legitimate deselection.
        # The _process_tree_selections function already preserves items from collapsed nodes
        # via the visible_object_labels check, so this guard was redundant and harmful.

        # Detect spurious database/schema selections: tree component with cascade mode
        # reports parent labels as "selected" when all children are selected.
        # BUT: Only mark as spurious if the database already has objects selected.
        # A genuinely NEW database (no objects from it in selected_objects) is legitimate!
        spurious_db_schema = False
        has_legitimate_removals = len(removed_selections) > 0

        # Build set of databases that already have objects selected
        already_selected_dbs = {obj[0] for obj in st.session_state.selected_objects}

        if len(pre_set) > 0 and new_selections and not has_legitimate_removals:
            all_new_are_spurious = True  # Assume spurious until we find a genuine new db
            for label in new_selections:
                meta = label_map.get(label)
                if meta and meta[0] == "database":
                    db_name = meta[1]
                    if db_name not in already_selected_dbs:
                        # This is a genuinely NEW database - not spurious!
                        all_new_are_spurious = False
                        logger.debug(f"[TREE_NAV] Genuine new database selection: {label}")
                        break
                    else:
                        logger.debug(f"[TREE_NAV] Spurious db selection (already has objects): {label}")
                elif meta and meta[0] == "schema":
                    # Schema selections could be spurious too, check if db already selected
                    db_name = meta[1]
                    if db_name not in already_selected_dbs:
                        all_new_are_spurious = False
                        break
                else:
                    # Object selections are never spurious
                    all_new_are_spurious = False
                    break

            # Only block if ALL new selections are spurious parent labels
            spurious_db_schema = all_new_are_spurious and any(
                label_map.get(l, (None,))[0] in ("database", "schema") for l in new_selections
            )

        # Check if filter is active - if so, allow processing even with expected_selections_missing
        # This fixes the bug where filtering to a new database didn't update selections
        filter_active = bool(st.session_state.get("search_filter", "").strip())
        # Only count new selections that exist in label_map (visible in current tree)
        # This filters out stale selections from tree component that don't match filtered view
        valid_new_selections = {s for s in new_selections if s in label_map}
        has_new_selections = bool(valid_new_selections)

        logger.debug(f"[EXEC:{exec_id}][GUARDS] is_read_only={is_read_only}, spurious={spurious_db_schema}, expected_missing={expected_selections_missing}, needs_lazy_rerun={needs_lazy_rerun}, removals={len(removed_selections)}, filter_active={filter_active}, has_new={has_new_selections}, valid_new={list(valid_new_selections)[:3]}, filter_just_changed={filter_just_changed}")

        # Process selections and sync metadata
        selection_needs_rerun = False
        metadata_changed = False

        # Skip processing if tree state is inconsistent or in read-only mode
        if is_read_only:
            logger.debug("[TREE_NAV] SKIPPING: read-only mode")
            pass  # Read-only mode - don't process any selection changes
        elif filter_just_changed and not has_new_selections:
            # Filter just changed - tree remounted with fresh state
            # Don't process empty/stale selection as "user deselected everything"
            # BUT: If user made new selections (clicked something), process those
            logger.debug("[TREE_NAV] SKIPPING: filter_just_changed (tree re-rendering)")
            pass  # Wait for user to make explicit selections in new filtered view
        elif spurious_db_schema:
            logger.debug("[TREE_NAV] SKIPPING: spurious_db_schema")
            pass  # Don't process spurious database/schema selections
        elif expected_selections_missing and not (filter_active and has_new_selections):
            # Only skip if expected_selections_missing AND (no filter OR no new selections)
            # When filter is active and user made new selections, process them
            logger.debug("[TREE_NAV] SKIPPING: expected_selections_missing (no filter or new selections)")
            pass  # Don't process when tree can't show selections
        else:
            # Process selections even during lazy loading
            # This ensures objects are added to selected_objects immediately when a database is selected
            logger.debug("[TREE_NAV] PROCESSING selections via _process_tree_selections")
            selection_needs_rerun = _process_tree_selections(session, selected, label_map)

        # Sync metadata with selections (returns True if metadata changed)
        metadata_changed = _sync_metadata_with_selections(session)

        # State consistency check: selected_objects vs views_metadata
        selection_count = len(st.session_state.selected_objects)
        metadata_count = len(st.session_state.views_metadata)

        # Debug: Show state in sidebar for troubleshooting
        if selection_count != metadata_count:
            st.warning(f"⚠️ State mismatch: {selection_count} selected, {metadata_count} loaded")
            logger.warning(f"[EXEC:{exec_id}][STATE_DESYNC] selected_objects={selection_count}, views_metadata={metadata_count}")
        else:
            logger.debug(f"[EXEC:{exec_id}][STATE_OK] selected_objects={selection_count}, views_metadata={metadata_count}")

        # Selective rerun logic:
        # - Metadata changed (add/remove objects)? Full rerun - main content needs update
        # - Just lazy loading (expand/collapse)? Try fragment rerun, fall back to full rerun
        if metadata_changed:
            logger.debug(f"[EXEC:{exec_id}][RERUN] Full rerun - metadata changed")
            st.rerun()  # Full app rerun - main content needs to show changes
        elif needs_lazy_rerun or selection_needs_rerun:
            logger.debug(f"[EXEC:{exec_id}][RERUN] Rerun for lazy loading or selection state")
            # scope="fragment" only works during fragment reruns, not initial render
            # Use full rerun to ensure consistency
            st.rerun()

    # Execute the fragment
    _tree_fragment()


def main():
    """Main application entry point."""
    # Execution ID tracking for debugging reruns
    if "_exec_id" not in st.session_state:
        st.session_state._exec_id = 0
    st.session_state._exec_id += 1
    exec_id = st.session_state._exec_id
    logger.debug(f"[EXEC:{exec_id}] === NEW RENDER CYCLE ===")

    # Initialize session state with centralized AppState
    # This handles creation, migration, and legacy key sync in one call
    init_session_state()

    # Sync any changes from legacy session_state back to AppState
    # This captures widget changes that directly modify session_state
    sync_from_legacy()

    # Page configuration - use Snowflake logo as favicon
    favicon_path = Path(__file__).parent / "img" / "snowflake.svg"
    st.set_page_config(
        page_title="Power BI Semantic Model Generator",
        page_icon=str(favicon_path) if favicon_path.exists() else "❄️",
        layout="wide"
    )

    # Inject custom Snowflake-style CSS
    inject_custom_css()

    # Header with Snowflake logo and connector download
    snowflake_icon = get_svg_icon("snowflake", size=48)

    # Check if MSI exists for header download button
    msi_path = Path(__file__).parent / "assets" / "SnowflakeSemanticViewsConnector.msi"
    msi_exists = msi_path.exists()

    # Header row with title and download button on same line
    header_col, button_col = st.columns([6, 1])

    with header_col:
        st.markdown(f"""
            <div style="display: flex; align-items: center; gap: 16px; margin-bottom: 4px;">
                {snowflake_icon}
                <div style="flex: 1;">
                    <h1 style="margin: 0; padding: 0;">Power BI Semantic Model Generator</h1>
                    <p style="margin: 0; color: #6c757d; font-size: 0.875rem;">
                        Create Power BI semantic models from Snowflake tables and semantic views
                    </p>
                </div>
            </div>
        """, unsafe_allow_html=True)

    with button_col:
        # Vertical alignment spacer + download button
        st.markdown('<div style="height: 8px;"></div>', unsafe_allow_html=True)
        if msi_exists:
            msi_bytes = msi_path.read_bytes()
            st.download_button(
                label="Get Connector",
                data=msi_bytes,
                file_name="SnowflakeSemanticViewsConnector.msi",
                mime="application/x-msi",
                help="Download the Power BI connector (.msi) - required to query Snowflake Semantic Views",
                key="header_msi_download"
            )

    # Progress indicator
    show_progress_indicator()

    # Initialize Snowflake session with structured error handling
    try:
        if "_snowpark_session::manual" in st.session_state:
            session = st.session_state["_snowpark_session::manual"]
        else:
            session = get_snowflake_session()
        # Store session in session_state for cardinality enrichment
        st.session_state.snowpark_session = session
        logger.info("Snowflake session established successfully")
    except (FileNotFoundError, KeyError) as e:
        # No usable connections.toml connection - render an interactive
        # connection form instead of dead-ending (issue #3).
        available = list_available_connections()
        if available:
            st.info(f"Connections found in connections.toml: {', '.join(available)}")
        session = render_connection_form()
        if session is None:
            return
        st.session_state.snowpark_session = session
        st.rerun()
    except ImportError as e:
        handle_error(
            e,
            operation="Loading Dependencies",
            show_in_ui=True,
            details="pip install snowflake-snowpark-python cryptography",
            suggestion="Install the required packages using pip",
        )
        return
    except Exception as e:
        handle_error(e, operation="Snowflake Connection", show_in_ui=True)
        return

    if is_running_in_snowflake() is False:
        with st.sidebar:
            if st.button("Reconnect to Snowflake", help="Drop the cached session and create a new one"):
                st.session_state.pop("_snowpark_session::manual", None)
                try:
                    reconnect_local_session()
                except Exception:
                    pass
                st.rerun()

    # Get session info for display and model generation
    try:
        conn_info = get_session_info(session)
    except Exception as e:
        st.warning(f"Could not get connection info: {e}")
        conn_info = {"server": "unknown", "warehouse": "XSMALL", "warehouse_missing": False, "is_local": True}

    # Store conn_info in session state for page modules to access
    st.session_state.conn_info = conn_info

    # Load databases with error handling
    try:
        databases = get_databases(session)
        logger.debug(f"Loaded {len(databases)} databases")
    except Exception as e:
        logger.error(f"Error fetching databases: {e}", exc_info=True)
        handle_error(e, operation="Loading Databases", show_in_ui=True)
        return

    # Sidebar - Objects, Connection Info
    with st.sidebar:
        # Snowflake logo and Reset button in horizontal layout
        logo_col, btn_col = st.columns([0.55, 0.45], gap="small", vertical_alignment="center")

        with logo_col:
            logo_path = Path(__file__).parent / "assets" / "logo_snowflake_blue.png"
            if logo_path.exists():
                st.image(str(logo_path), width=140)

        with btn_col:
            reset_clicked = st.button("Reset", key="reset_app", type="secondary", icon=":material/refresh:", use_container_width=True)

        # Reset App - immediate reset without confirmation
        if reset_clicked:
            # Get current reset counter BEFORE clearing state
            current_counter = st.session_state.get("tree_reset_counter", 0)
            # Clear ALL session state except connection info
            keys_to_keep = {"conn_info"}
            keys_to_delete = [k for k in st.session_state.keys() if k not in keys_to_keep]
            for key in keys_to_delete:
                del st.session_state[key]
            # Reset wizard to step 0
            st.session_state.wizard_step = 0
            st.session_state.views_metadata = []
            st.session_state.selected_objects = []
            # Explicitly clear the database filter text box
            st.session_state.search_filter = ""
            # Increment reset counter so tree gets a fresh key and doesn't restore old state
            st.session_state.tree_reset_counter = current_counter + 1
            # Flag to skip preserved selections on next tree render
            st.session_state._just_reset = True
            log_user_action("reset_app")
            st.rerun()

        st.divider()

        # Object Selection (tree navigation - always visible in sidebar)
        render_tree_navigation(session, databases)

        st.divider()

        # Connection Info
        st.markdown(f"### {icon_header('connected', 'Connection Info', size=24)}", unsafe_allow_html=True)
        env_badge = "🏠 Local" if conn_info.get("is_local", True) else f"{get_svg_icon('cloud', 16)} Snowflake"
        st.markdown(f"**Environment:** {env_badge}", unsafe_allow_html=True)
        st.text(f"Server: {conn_info.get('server', 'unknown')}")
        st.text(f"Warehouse: {conn_info.get('warehouse', 'unknown')}")
        st.text(f"User: {conn_info.get('user', 'unknown')}")

        # Show error if present
        if "error" in conn_info:
            st.error(f"Connection error: {conn_info['error']}")

    # Main content area - multi-page wizard (one step at a time)
    current_step = get_wizard_step()
    logger.debug(f"Rendering wizard step {current_step}")

    # Get app state for page system integration
    app_state = get_app_state()

    # Page modules are auto-imported in pages/__init__.py
    # This ensures @register_page decorators run even on Streamlit reload

    # Use the new page system for all steps
    if is_page_implemented(current_step):
        logger.debug(f"Using page system for step {current_step}")
        if render_current_step(session, app_state):
            return  # Page handled rendering
        # If render_current_step returns False, fall through to legacy rendering

    # === LEGACY RENDERING (fallback) ===
    # This code is kept for backward compatibility during migration
    # Once all pages are verified working, this can be removed

    # === STEP 0: REVIEW SELECTED OBJECTS (HOME) ===
    if current_step == 0:
        st.markdown(f"## {icon_header('verified', 'Review Selected Objects', size=28)}", unsafe_allow_html=True)

        if not st.session_state.views_metadata:
            st.info("👈 Use the **sidebar tree navigator** to select tables, views, and semantic views.")
        else:
            total_columns = sum(len(m.columns) for m in st.session_state.views_metadata)
            has_semantic_views = any(m.object_type == "SEMANTIC_VIEW" for m in st.session_state.views_metadata)
            has_standard_tables = any(m.object_type in ("TABLE", "VIEW") for m in st.session_state.views_metadata)

            if has_semantic_views and has_standard_tables:
                st.info(
                    "**Mixed selection:** Semantic views use Custom Connector, "
                    "standard tables use Native Snowflake Connector."
                )

            # Show each object
            for metadata in st.session_state.views_metadata:
                icon_html = get_object_icon_html(metadata.object_type, size=20)
                badge_html = get_connector_badge_html(metadata.object_type)
                st.markdown(f'{icon_html} **{metadata.full_name}** ({len(metadata.columns)} columns){badge_html}', unsafe_allow_html=True)

                if metadata.table_metadata and metadata.table_metadata.comment:
                    st.caption(f"📝 {metadata.table_metadata.comment}")

                with st.expander("Show columns", expanded=False):
                    display_column_metadata(metadata)

            # Check for missing related tables
            selected_tables = {m.view for m in st.session_state.views_metadata}
            missing_tables = set()
            for metadata in st.session_state.views_metadata:
                if metadata.relationships:
                    for rel in metadata.relationships:
                        if rel.to_table not in selected_tables:
                            missing_tables.add(rel.to_table)

            if missing_tables:
                st.warning(f"**💡 Suggested tables:** {', '.join(sorted(missing_tables))}")

            # Navigation (no back button - this is the home page)
            st.divider()
            if st.button("Next: Design Data Model ->", type="primary", width="stretch", key="review_next_btn"):
                logger.debug("Button clicked - navigating to step 1")
                st.session_state.wizard_step = 1
                st.rerun()

    # === STEP 1: DESIGN DATA MODEL ===
    elif current_step == 1:
        logger.debug(f"Rendering step 1, views_metadata count: {len(st.session_state.get('views_metadata', []))}")
        st.markdown(f"## {icon_header('data_engineering', 'Design Data Model', size=28)}", unsafe_allow_html=True)

        if not st.session_state.views_metadata:
            st.warning("No objects selected.")
            if st.button("← Back to Review"):
                st.session_state.wizard_step = 0
                st.rerun()
        elif len(st.session_state.views_metadata) == 1:
            st.info("Single object selected - no relationships to configure.")

            # Show single-object visualizer
            if FLOW_AVAILABLE:
                render_schema_visualizer(
                    tables=st.session_state.views_metadata,
                    relationships=[],
                    key="single_object_graph_main"
                )

            st.divider()
            col1, col2 = st.columns(2)
            with col1:
                if st.button("← Back to Review"):
                    st.session_state.wizard_step = 0
                    st.rerun()
            with col2:
                if st.button("NEXT: DOWNLOAD PBI WORKBOOK ->", type="primary", width='stretch'):
                    st.session_state.wizard_step = 2
                    st.rerun()
        else:
            has_semantic_views = any(m.object_type == "SEMANTIC_VIEW" for m in st.session_state.views_metadata)
            has_standard_tables = any(m.object_type in ("TABLE", "VIEW") for m in st.session_state.views_metadata)
            all_relationships = collect_all_relationships(
                st.session_state.views_metadata,
                session=st.session_state.get("snowpark_session")
            )

            # Enrich relationships with cardinality and fan-out risk
            if all_relationships:
                session = st.session_state.get("snowpark_session")
                metadata_by_name = {m.view: m for m in st.session_state.views_metadata}
                for rel in all_relationships:
                    from_meta = metadata_by_name.get(rel.from_table)
                    to_meta = metadata_by_name.get(rel.to_table)
                    if from_meta and to_meta and session:
                        enrich_relationship_with_cardinality(session, rel, from_meta, to_meta)

            # v3.0: Check for cross-connector relationships and warn
            if has_semantic_views and has_standard_tables and all_relationships:
                # Create lookup for object types by name
                object_types = {m.view: m.object_type for m in st.session_state.views_metadata}

                # Find relationships that span connector types
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
                        f"**⚠️ Cross-connector relationships detected ({len(cross_connector_rels)})**\n\n"
                        f"Relationships between tables using different connectors may need to be "
                        f"created manually in Power BI Desktop.\n\n"
                        f"Affected: {', '.join(f'{r.from_table}->{r.to_table}' for r in cross_connector_rels[:3])}"
                        f"{'...' if len(cross_connector_rels) > 3 else ''}"
                    )

            # Initialize selected relationships in session state (even if empty)
            if "selected_relationships" not in st.session_state:
                st.session_state.selected_relationships = {}

            if all_relationships:
                # Initialize selected relationships for detected FK relationships
                for rel in all_relationships:
                    if rel.relationship_id not in st.session_state.selected_relationships:
                        st.session_state.selected_relationships[rel.relationship_id] = True
                # Remove relationships that no longer exist
                current_ids = {rel.relationship_id for rel in all_relationships}
                # Keep manual relationships (those not in current_ids are manual)
                manual_rel_ids = {r.relationship_id for r in st.session_state.get("manual_relationships", [])}
                st.session_state.selected_relationships = {
                    k: v for k, v in st.session_state.selected_relationships.items()
                    if k in current_ids or k in manual_rel_ids
                }

                # Detect ambiguous paths
                selected_rels = [rel for rel in all_relationships
                                 if st.session_state.selected_relationships.get(rel.relationship_id, True)]
                _, inactive_rels = detect_ambiguous_paths(selected_rels)
                inactive_ids = {rel.relationship_id for rel in inactive_rels}

                # Count selected (including manual relationships)
                manual_relationships = st.session_state.get("manual_relationships", [])
                all_rels = all_relationships + manual_relationships
                selected_count = sum(
                    1 for rel in all_rels
                    if st.session_state.selected_relationships.get(rel.relationship_id, True)
                )

                # Detect role-playing dimensions (needed for left column)
                role_playing_dims = detect_role_playing_dimensions(selected_rels)
                if role_playing_dims:
                    # Initialize session state for role-playing dimension duplication
                    if "duplicate_role_playing_dims" not in st.session_state:
                        st.session_state.duplicate_role_playing_dims = {
                            dim: True for dim in role_playing_dims
                        }
                    else:
                        # Add any new role-playing dimensions
                        for dim in role_playing_dims:
                            if dim not in st.session_state.duplicate_role_playing_dims:
                                st.session_state.duplicate_role_playing_dims[dim] = True
                        # Remove dimensions that no longer exist
                        st.session_state.duplicate_role_playing_dims = {
                            k: v for k, v in st.session_state.duplicate_role_playing_dims.items()
                            if k in role_playing_dims
                        }

            else:
                # No FK relationships detected - initialize defaults for UI
                inactive_ids = set()
                role_playing_dims = {}

            # === Data Model Configuration (always shown when 2+ objects) ===
            # Get manual relationships (available even without FK relationships)
            manual_relationships = st.session_state.get("manual_relationships", [])
            all_rels = all_relationships + manual_relationships

            # Two-column layout: options on left, diagram on right
            left_col, right_col = st.columns([1, 1])

            with left_col:
                # === Add Relationship Form ===
                # Initialize form visibility state
                if "show_add_rel_form" not in st.session_state:
                    st.session_state.show_add_rel_form = False

                # Toggle button
                if st.button("+ Add Relationship", key="toggle_add_rel"):
                    st.session_state.show_add_rel_form = not st.session_state.show_add_rel_form
                    st.rerun()

                if st.session_state.show_add_rel_form:
                    # Build table/column options
                    table_names = [m.view for m in st.session_state.views_metadata]
                    table_columns = {m.view: [c.name for c in m.columns] for m in st.session_state.views_metadata}

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
                            "Many to One (*:1)",
                            "One to One (1:1)",
                            "One to Many (1:*)",
                            "Many to Many (*:*)",
                        ]
                        selected_cardinality = st.radio(
                            "Relationship type",
                            options=cardinality_options,
                            index=0,
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
                        else:
                            from_card, to_card = "many", "many"

                        # Action buttons
                        btn_col1, btn_col2 = st.columns(2)
                        with btn_col1:
                            if st.button("Cancel", key="cancel_add_rel", width='stretch'):
                                st.session_state.show_add_rel_form = False
                                st.rerun()

                        with btn_col2:
                            if st.button("Add", key="confirm_add_rel", type="primary", width='stretch'):
                                if from_table and from_column and to_table and to_column:
                                    metadata_by_name = {m.view: m for m in st.session_state.views_metadata}
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

                # Info message when no FK relationships detected
                if not all_relationships and not manual_relationships:
                    st.info(
                        "No foreign key constraints detected in Snowflake. "
                        "Use 'Add Relationship' above to manually define relationships between tables."
                    )

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

                # Show manual relationships (if any)
                if manual_relationships:
                    st.markdown("**✏️ Manual Relationships**")
                    for rel in manual_relationships:
                        rel_id = rel.relationship_id
                        is_inactive = rel_id in inactive_ids and st.session_state.selected_relationships.get(rel_id, True)

                        # Get cardinality display
                        from_card = getattr(rel, 'from_cardinality', 'many')
                        to_card = getattr(rel, 'to_cardinality', 'one')
                        card_str = f"({'*' if from_card == 'many' else '1'}:{'*' if to_card == 'many' else '1'})"

                        label = f"{rel.from_table}.{rel.from_column} -> {rel.to_table}.{rel.to_column} {card_str} `[Manual]`"
                        if is_inactive:
                            label += " ⚠️"

                        help_text = "User-created relationship"
                        if is_inactive:
                            help_text += " (inactive - resolves ambiguous paths)"

                        # Check if we're currently editing this relationship
                        is_editing = st.session_state.get("editing_rel_id") == rel_id

                        if is_editing:
                            # Show edit form
                            with st.container(border=True):
                                st.markdown("**Edit Relationship**")

                                table_names = [m.view for m in st.session_state.views_metadata]
                                table_columns = {m.view: [c.name for c in m.columns] for m in st.session_state.views_metadata}
                                metadata_by_name = {m.view: m for m in st.session_state.views_metadata}

                                edit_col1, edit_col2 = st.columns(2)

                                with edit_col1:
                                    from_idx = table_names.index(rel.from_table) if rel.from_table in table_names else 0
                                    edit_from_table = st.selectbox(
                                        "From Table",
                                        options=table_names,
                                        index=from_idx,
                                        key=f"edit_from_table_{rel_id}",
                                    )
                                    from_cols = table_columns.get(edit_from_table, [])
                                    from_col_idx = from_cols.index(rel.from_column) if rel.from_column in from_cols else 0
                                    edit_from_column = st.selectbox(
                                        "From Column",
                                        options=from_cols,
                                        index=from_col_idx,
                                        key=f"edit_from_col_{rel_id}",
                                    )

                                with edit_col2:
                                    to_idx = table_names.index(rel.to_table) if rel.to_table in table_names else 0
                                    edit_to_table = st.selectbox(
                                        "To Table",
                                        options=table_names,
                                        index=to_idx,
                                        key=f"edit_to_table_{rel_id}",
                                    )
                                    to_cols = table_columns.get(edit_to_table, [])
                                    to_col_idx = to_cols.index(rel.to_column) if rel.to_column in to_cols else 0
                                    edit_to_column = st.selectbox(
                                        "To Column",
                                        options=to_cols,
                                        index=to_col_idx,
                                        key=f"edit_to_col_{rel_id}",
                                    )

                                # Cardinality selection
                                cardinality_options = ["Many to One (*:1)", "One to One (1:1)", "One to Many (1:*)", "Many to Many (*:*)"]
                                if from_card == "many" and to_card == "one":
                                    card_idx = 0
                                elif from_card == "one" and to_card == "one":
                                    card_idx = 1
                                elif from_card == "one" and to_card == "many":
                                    card_idx = 2
                                else:
                                    card_idx = 3

                                edit_cardinality = st.radio(
                                    "Cardinality",
                                    options=cardinality_options,
                                    index=card_idx,
                                    key=f"edit_card_{rel_id}",
                                    horizontal=True,
                                )

                                # Parse cardinality
                                if "Many to One" in edit_cardinality:
                                    new_from_card, new_to_card = "many", "one"
                                elif "One to One" in edit_cardinality:
                                    new_from_card, new_to_card = "one", "one"
                                elif "One to Many" in edit_cardinality:
                                    new_from_card, new_to_card = "one", "many"
                                else:
                                    new_from_card, new_to_card = "many", "many"

                                # Action buttons
                                btn_col1, btn_col2 = st.columns(2)
                                with btn_col1:
                                    if st.button("Cancel", key=f"cancel_edit_{rel_id}"):
                                        del st.session_state["editing_rel_id"]
                                        st.rerun()

                                with btn_col2:
                                    if st.button("Save", key=f"save_edit_{rel_id}", type="primary"):
                                        # Remove old relationship
                                        st.session_state.manual_relationships = [
                                            r for r in st.session_state.manual_relationships
                                            if r.relationship_id != rel_id
                                        ]
                                        st.session_state.selected_relationships.pop(rel_id, None)

                                        # Create updated relationship
                                        from_meta = metadata_by_name.get(edit_from_table)
                                        to_meta = metadata_by_name.get(edit_to_table)

                                        new_rel = create_manual_relationship(
                                            from_table=edit_from_table,
                                            from_columns=edit_from_column,
                                            to_table=edit_to_table,
                                            to_columns=edit_to_column,
                                            from_database=from_meta.database if from_meta else None,
                                            from_schema=from_meta.schema if from_meta else None,
                                            to_database=to_meta.database if to_meta else None,
                                            to_schema=to_meta.schema if to_meta else None,
                                            from_cardinality=new_from_card,
                                            to_cardinality=new_to_card,
                                        )

                                        st.session_state.manual_relationships.append(new_rel)
                                        st.session_state.selected_relationships[new_rel.relationship_id] = True
                                        del st.session_state["editing_rel_id"]
                                        st.rerun()
                        else:
                            # Normal display with checkbox + edit + delete buttons
                            chk_col, edit_col, del_col = st.columns([0.8, 0.1, 0.1])

                            with chk_col:
                                checked = st.checkbox(
                                    label,
                                    value=st.session_state.selected_relationships.get(rel_id, True),
                                    key=f"rel_{rel_id}",
                                    help=help_text,
                                )
                                st.session_state.selected_relationships[rel_id] = checked

                            with edit_col:
                                if st.button("✏️", key=f"edit_{rel_id}", help="Edit this relationship"):
                                    st.session_state.editing_rel_id = rel_id
                                    st.rerun()

                            with del_col:
                                if st.button("🗑️", key=f"del_{rel_id}", help="Delete this relationship"):
                                    st.session_state.manual_relationships = [
                                        r for r in st.session_state.manual_relationships
                                        if r.relationship_id != rel_id
                                    ]
                                    st.session_state.selected_relationships.pop(rel_id, None)
                                    st.rerun()

                # Show detected (FK) relationships
                if all_relationships:
                    st.markdown(f"**{get_svg_icon('copy', 16)} Detected Relationships**", unsafe_allow_html=True)

                    # Show each original relationship with checkbox
                    for rel in all_relationships:
                        rel_id = rel.relationship_id
                        is_inactive = rel_id in inactive_ids and st.session_state.selected_relationships.get(rel_id, True)
                        is_self_ref = rel.from_table == rel.to_table

                        # Build cardinality string
                        card_str = ""
                        if hasattr(rel, 'cardinality') and rel.cardinality:
                            from_sym = "1" if rel.cardinality.from_cardinality == "one" else "*"
                            to_sym = "1" if rel.cardinality.to_cardinality == "one" else "*"
                            card_str = f" ({from_sym}:{to_sym})"

                        # Build label with cardinality and inactive/self-ref indicator
                        label = f"{rel.from_table}.{rel.from_column} -> {rel.to_table}.{rel.to_column}{card_str}"
                        if rel.name:
                            label += f" ({rel.name})"
                        if is_self_ref:
                            label += " 🔄 `[Self-ref]`"
                        elif is_inactive:
                            label += " ⚠️"

                        # Checkbox for this relationship
                        help_text = None
                        disabled = False
                        if is_self_ref:
                            help_text = "Self-referential relationship - Power BI does not support this. Will NOT be exported."
                            disabled = True
                        elif is_inactive:
                            help_text = "Inactive - resolves ambiguous paths"

                        checked = st.checkbox(
                            label,
                            value=False if is_self_ref else st.session_state.selected_relationships.get(rel_id, True),
                            key=f"rel_{rel_id}",
                            help=help_text,
                            disabled=disabled,
                        )
                        if not is_self_ref:
                            st.session_state.selected_relationships[rel_id] = checked

                    if inactive_ids:
                        st.caption("⚠️ = inactive relationship")
                    # Note about self-referential
                    if any(rel.from_table == rel.to_table for rel in all_relationships):
                        st.caption("🔄 = self-referential (not exported to Power BI)")

                    # Role-playing dimensions section
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

            with right_col:
                # Schema diagram
                if len(st.session_state.views_metadata) > 1 and FLOW_AVAILABLE:
                    st.caption("Drag to rearrange, scroll to zoom")
                    selected_rels_for_diagram = [
                        rel for rel in all_rels
                        if st.session_state.selected_relationships.get(rel.relationship_id, True)
                    ]
                    render_schema_visualizer(
                        tables=st.session_state.views_metadata,
                        relationships=selected_rels_for_diagram,
                        key="main_schema_graph"
                    )
                    show_graph_legend()
                else:
                    st.info("Schema diagram available when 2+ tables selected")

            # Navigation buttons for Step 1 (Data Model)
            st.divider()
            col1, col2 = st.columns(2)
            with col1:
                if st.button("← Back to Review"):
                    st.session_state.wizard_step = 0
                    st.rerun()
            with col2:
                if st.button("Next: Generate Output ->", type="primary", width="stretch"):
                    st.session_state.wizard_step = 2
                    st.rerun()

    # === STEP 2: GENERATE OUTPUT (FALLBACK) ===
    # NOTE: Step 2 is normally handled by pages/step_generate.py via the page system.
    # This fallback only executes if the page system fails to render.
    elif current_step == 2:
        st.markdown(f"## {icon_header('rocket', 'Generate Output', size=28)}", unsafe_allow_html=True)

        # Debug info
        selection_count = len(st.session_state.get("selected_objects", []))
        metadata_count = len(st.session_state.get("views_metadata", []))
        logger.warning(f"[FALLBACK] Step 2 fallback rendering: selected_objects={selection_count}, views_metadata={metadata_count}")

        if not st.session_state.get("views_metadata"):
            st.warning(f"No metadata loaded. ({selection_count} objects selected but metadata not loaded)")
            st.caption("This is a fallback page. The normal page system may have failed.")

            if selection_count > 0:
                st.info("Selected objects exist but metadata wasn't loaded. Try going back and reselecting.")

            if st.button("← Back to Review"):
                st.session_state.wizard_step = 0
                st.rerun()
        else:
            st.info(f"Fallback mode: {metadata_count} objects ready for generation.")
            st.caption("The normal page system may have failed. Please try refreshing.")

            # Show the actual error if available
            if "_page_render_error" in st.session_state:
                st.error(f"Page error: {st.session_state._page_render_error}")

            if st.button("← Back to Design Data Model"):
                st.session_state.wizard_step = 1
                st.rerun()

    # Footer
    st.divider()
    st.markdown(
        "*Written By Alex Ross, Principal Solution Engineer at Snowflake | "
        f"© {datetime.now().year}*"
    )
    st.caption(
        "ℹ️ Provided as-is under [MIT License](https://opensource.org/licenses/MIT). "
        "Not officially supported by Snowflake."
    )


# === Helper functions for rendering fix solutions ===


def _render_dax_solution(rel, to_meta, risk):
    """Render DAX measure solution UI (Import mode only)."""
    st.caption("ℹ️ Query-time calculation in Power BI - no Snowflake objects needed")

    # Warning about DirectQuery limitation
    st.warning(
        "⚠️ **DAX SUMX/VALUES pattern only works in Import mode.** "
        "In DirectQuery, this pattern fails when tables exceed 1 million rows "
        "due to Power BI's row limit for the `VALUES()` function."
    )

    if not to_meta or not risk or not risk.affected_measures:
        st.warning("Table metadata not available")
        return

    # Get PK column for DAX measure
    pk_cols = [c for c in to_meta.columns if c.is_primary_key]
    pk_col = pk_cols[0].name if pk_cols else None

    if pk_col:
        st.markdown("**DAX measures to copy to Power BI:**")
        for i, measure in enumerate(risk.affected_measures[:3]):
            dax_code = generate_dax_measure(
                measure_name=measure,
                source_table=rel.to_table,
                measure_column=measure,
                pk_column=pk_col,
                aggregation="SUM"
            )
            st.code(dax_code, language="dax")

        if len(risk.affected_measures) > 3:
            st.caption(f"*...and {len(risk.affected_measures) - 3} more measures*")

        st.info("""
**📖 How to use DAX measures:**

1. Open your Power BI report
2. Select the table in the Data pane
3. Click "New Measure" in the ribbon
4. Paste the DAX code above

**Why this works:**
- `VALUES()` gets distinct primary keys
- `SUMX()` iterates and aggregates at correct grain
""")
    else:
        st.warning("Cannot generate DAX - no primary key found in table")


if __name__ == "__main__":
    main()
