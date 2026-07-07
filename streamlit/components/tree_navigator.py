"""
Tree Navigator Component for the Power BI Semantic Model Generator.

Provides a hierarchical tree view for navigating Snowflake databases,
schemas, and objects (tables, views, semantic views) with lazy loading.

Usage:
    from components.tree_navigator import TreeNavigator, TreeConfig

    config = TreeConfig(
        on_selection_change=handle_selection,
        show_search=True,
    )
    navigator = TreeNavigator(session, config)
    navigator.render()
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Optional
import streamlit as st
import streamlit_antd_components as sac

from config import CONFIG, OBJECT_TYPES, get_object_type_config
from logging_config import get_logger, log_user_action
from error_handling import error_boundary, MetadataFetchError

logger = get_logger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class TreeConfig:
    """Configuration for the tree navigator component.

    Attributes:
        on_selection_change: Callback when selection changes
        show_search: Whether to show the search filter
        show_selection_count: Whether to show selection count badge
        auto_load_metadata: Whether to auto-load metadata for selections
        checkbox_mode: Enable checkbox selection mode
        cascade_selection: Whether selecting parent selects children
    """
    on_selection_change: Optional[Callable[[list], None]] = None
    show_search: bool = True
    show_selection_count: bool = True
    auto_load_metadata: bool = True
    checkbox_mode: bool = True
    cascade_selection: bool = False
    tree_color: str = "#29B5E8"  # Snowflake blue


# =============================================================================
# TREE ITEM BUILDERS
# =============================================================================

def get_object_icon(object_type: str) -> sac.BsIcon:
    """Get Bootstrap icon for an object type with Snowflake colors.

    Args:
        object_type: SEMANTIC_VIEW, VIEW, or TABLE

    Returns:
        BsIcon instance with appropriate styling
    """
    config = get_object_type_config(object_type)

    icon_map = {
        "SEMANTIC_VIEW": ("box", config.color_primary),
        "VIEW": ("eye", config.color_primary),
        "TABLE": ("table", config.color_primary),
    }

    icon_name, color = icon_map.get(object_type, ("table", "#75CDD7"))
    return sac.BsIcon(name=icon_name, color=color)


def get_object_tag(object_type: str) -> sac.Tag:
    """Get a tag badge for an object type.

    Args:
        object_type: SEMANTIC_VIEW, VIEW, or TABLE

    Returns:
        Tag instance with appropriate styling
    """
    tag_map = {
        "SEMANTIC_VIEW": ("Semantic", "purple"),
        "VIEW": ("View", "orange"),
        "TABLE": ("Table", "cyan"),
    }

    label, color = tag_map.get(object_type, ("Table", "cyan"))
    return sac.Tag(label, color=color)


def matches_search(search_term: str, db: str, schema: str = None, name: str = None) -> bool:
    """Check if database/schema/object matches search term.

    Args:
        search_term: Search string (already uppercase)
        db: Database name
        schema: Schema name (optional)
        name: Object name (optional)

    Returns:
        True if any component matches the search
    """
    if not search_term:
        return True

    full_name = db.upper()
    if schema:
        full_name += "." + schema.upper()
    if name:
        full_name += "." + name.upper()

    return search_term in full_name


# =============================================================================
# TREE STATE MANAGEMENT
# =============================================================================

class TreeState:
    """Manages tree navigation state using Streamlit session state.

    Provides a cleaner interface for accessing and modifying tree state.
    """

    @staticmethod
    def get_loaded_schemas() -> dict[str, list[str]]:
        """Get cached schemas by database."""
        return st.session_state.get("loaded_schemas", {})

    @staticmethod
    def set_schemas(database: str, schemas: list[str]) -> None:
        """Cache schemas for a database."""
        if "loaded_schemas" not in st.session_state:
            st.session_state.loaded_schemas = {}
        st.session_state.loaded_schemas[database] = schemas

    @staticmethod
    def get_loaded_objects() -> dict[tuple[str, str], list[Any]]:
        """Get cached objects by (database, schema)."""
        return st.session_state.get("loaded_objects", {})

    @staticmethod
    def set_objects(database: str, schema: str, objects: list[Any]) -> None:
        """Cache objects for a schema."""
        if "loaded_objects" not in st.session_state:
            st.session_state.loaded_objects = {}
        st.session_state.loaded_objects[(database, schema)] = objects

    @staticmethod
    def get_expanded_nodes() -> list[str]:
        """Get list of expanded tree node labels."""
        return st.session_state.get("expanded_nodes", [])

    @staticmethod
    def set_expanded_nodes(nodes: list[str]) -> None:
        """Set expanded tree nodes."""
        st.session_state.expanded_nodes = [n for n in nodes if n is not None]

    @staticmethod
    def get_selected_objects() -> list[tuple[str, str, str, str]]:
        """Get list of selected objects as (db, schema, name, type) tuples."""
        return st.session_state.get("selected_objects", [])

    @staticmethod
    def set_selected_objects(objects: list[tuple[str, str, str, str]]) -> None:
        """Set selected objects."""
        st.session_state.selected_objects = objects

    @staticmethod
    def get_reset_counter() -> int:
        """Get tree reset counter (for forcing remount)."""
        return st.session_state.get("tree_reset_counter", 0)

    @staticmethod
    def increment_reset_counter() -> None:
        """Increment reset counter to force tree remount."""
        st.session_state.tree_reset_counter = TreeState.get_reset_counter() + 1

    @staticmethod
    def cleanup_state() -> None:
        """Clean up corrupted state values."""
        # Clean selected_objects
        if "selected_objects" in st.session_state:
            valid = []
            for item in st.session_state.selected_objects:
                if item is not None and isinstance(item, (list, tuple)) and len(item) >= 4:
                    if all(v is not None for v in item[:4]):
                        valid.append(tuple(item[:4]))
            st.session_state.selected_objects = valid

        # Clean expanded_nodes
        if "expanded_nodes" in st.session_state:
            st.session_state.expanded_nodes = [
                n for n in st.session_state.expanded_nodes
                if n is not None and isinstance(n, str)
            ]

        # Clean tree keys with None values
        keys_to_delete = []
        for key in list(st.session_state.keys()):
            if key.startswith("object_tree_"):
                val = st.session_state[key]
                if val is None or (isinstance(val, list) and any(v is None for v in val)):
                    keys_to_delete.append(key)
        for key in keys_to_delete:
            del st.session_state[key]


# =============================================================================
# TREE NAVIGATOR COMPONENT
# =============================================================================

class TreeNavigator:
    """Tree navigation component for Snowflake objects.

    Provides a hierarchical tree view with:
    - Lazy loading of schemas and objects
    - Search/filter functionality
    - Checkbox selection
    - State persistence across reruns

    Example:
        navigator = TreeNavigator(session, TreeConfig())
        navigator.render(databases=["DB1", "DB2"])
    """

    def __init__(self, session: Any, config: TreeConfig = None):
        """Initialize the tree navigator.

        Args:
            session: Snowflake session for data fetching
            config: Component configuration
        """
        self.session = session
        self.config = config or TreeConfig()
        self._label_map: dict[str, tuple] = {}

    def build_tree_items(
        self,
        databases: list[str],
        search_term: str = ""
    ) -> list[sac.TreeItem]:
        """Build tree items for the sac.tree component.

        Args:
            databases: List of database names
            search_term: Optional search filter

        Returns:
            List of TreeItem objects
        """
        items = []
        self._label_map = {}
        loaded_schemas = TreeState.get_loaded_schemas()
        loaded_objects = TreeState.get_loaded_objects()

        for db in databases:
            # Apply search filter
            if search_term:
                db_matches = search_term in db.upper()
                has_matching_children = self._has_matching_children(
                    db, search_term, loaded_schemas, loaded_objects
                )
                if not db_matches and not has_matching_children:
                    continue

            # Build database node
            self._label_map[db] = ("database", db, None, None, None)
            db_children = self._build_schema_items(
                db, search_term, loaded_schemas, loaded_objects
            )

            items.append(
                sac.TreeItem(db, icon="database", children=db_children)
            )

        return items

    def _has_matching_children(
        self,
        database: str,
        search_term: str,
        loaded_schemas: dict,
        loaded_objects: dict
    ) -> bool:
        """Check if database has any children matching search."""
        if database not in loaded_schemas:
            return False

        for schema in loaded_schemas[database]:
            if matches_search(search_term, database, schema):
                return True

            schema_key = (database, schema)
            if schema_key in loaded_objects:
                for obj in loaded_objects[schema_key]:
                    if matches_search(search_term, database, schema, obj.name):
                        return True

        return False

    def _build_schema_items(
        self,
        database: str,
        search_term: str,
        loaded_schemas: dict,
        loaded_objects: dict
    ) -> list[sac.TreeItem]:
        """Build schema tree items for a database."""
        if database not in loaded_schemas:
            return [sac.TreeItem("Loading schemas...", disabled=True)]

        items = []
        for schema in loaded_schemas[database]:
            # Apply search filter
            if search_term:
                schema_matches = matches_search(search_term, database, schema)
                schema_key = (database, schema)
                has_matching = False
                if schema_key in loaded_objects:
                    for obj in loaded_objects[schema_key]:
                        if matches_search(search_term, database, schema, obj.name):
                            has_matching = True
                            break
                if not schema_matches and not has_matching:
                    continue

            # Build schema node
            self._label_map[schema] = ("schema", database, schema, None, None)
            schema_children = self._build_object_items(
                database, schema, search_term, loaded_objects
            )

            items.append(
                sac.TreeItem(schema, icon="folder2-open", children=schema_children)
            )

        return items if items else [sac.TreeItem("No schemas found", disabled=True)]

    def _build_object_items(
        self,
        database: str,
        schema: str,
        search_term: str,
        loaded_objects: dict
    ) -> list[sac.TreeItem]:
        """Build object tree items for a schema."""
        schema_key = (database, schema)

        if schema_key not in loaded_objects:
            return [sac.TreeItem("Loading objects...", disabled=True)]

        items = []
        for obj in loaded_objects[schema_key]:
            # Apply search filter
            if search_term and not matches_search(search_term, database, schema, obj.name):
                continue

            # Build object node
            self._label_map[obj.name] = ("object", database, schema, obj.name, obj.object_type)

            items.append(
                sac.TreeItem(
                    obj.name,
                    icon=get_object_icon(obj.object_type),
                    tag=get_object_tag(obj.object_type)
                )
            )

        return items if items else [sac.TreeItem("No objects found", disabled=True)]

    def _handle_expansions(self, expanded: list[str]) -> bool:
        """Handle node expansions and trigger lazy loading.

        Args:
            expanded: List of expanded node labels

        Returns:
            True if a rerun is needed
        """
        from metadata_fetcher import get_schemas, get_all_objects
        from tooltips import snowflake_spinner

        needs_rerun = False

        for label in expanded:
            if label not in self._label_map:
                continue

            meta = self._label_map[label]
            node_type = meta[0]

            if node_type == "database":
                # Load schemas for expanded database
                db = meta[1]
                loaded_schemas = TreeState.get_loaded_schemas()
                if db not in loaded_schemas:
                    with snowflake_spinner(f"Loading schemas for {db}..."):
                        try:
                            schemas = get_schemas(self.session, db)
                            TreeState.set_schemas(db, schemas)
                            needs_rerun = True
                            log_user_action("load_schemas", {"database": db, "count": len(schemas)})
                        except Exception as e:
                            logger.error(f"Failed to load schemas for {db}: {e}")
                            st.error(f"Error loading schemas: {e}")

            elif node_type == "schema":
                # Load objects for expanded schema
                db, schema = meta[1], meta[2]
                loaded = TreeState.get_loaded_objects()
                if (db, schema) not in loaded:
                    with snowflake_spinner(f"Loading objects for {schema}..."):
                        try:
                            objects = get_all_objects(self.session, db, schema)
                            TreeState.set_objects(db, schema, objects)
                            needs_rerun = True
                            log_user_action("load_objects", {
                                "database": db,
                                "schema": schema,
                                "count": len(objects)
                            })
                        except Exception as e:
                            logger.error(f"Failed to load objects for {db}.{schema}: {e}")
                            st.error(f"Error loading objects: {e}")

        return needs_rerun

    def _ensure_parents_expanded(
        self,
        selections: list[tuple[str, str, str, str]],
        expanded: list[str]
    ) -> list[str]:
        """Ensure parent nodes (database, schema) are expanded for selected items.

        This keeps the tree open to show selected items after selection.

        Args:
            selections: List of (db, schema, name, type) tuples
            expanded: Current list of expanded node labels

        Returns:
            Updated list of expanded node labels
        """
        expanded_set = set(expanded) if expanded else set()

        for db, schema, name, obj_type in selections:
            # Add database to expanded
            if db and db not in expanded_set:
                expanded_set.add(db)
            # Add schema to expanded
            if schema and schema not in expanded_set:
                expanded_set.add(schema)

        return list(expanded_set)

    def _handle_selections(self, selected: list[str]) -> list[tuple[str, str, str, str]]:
        """Process tree selections and return object tuples.

        Preserves selections from items not currently visible in the tree
        (e.g., when filter changes). Only modifies selections for items
        that are currently visible in the tree.

        Args:
            selected: List of selected node labels

        Returns:
            List of (database, schema, name, object_type) tuples
        """
        # Get existing selections
        existing_selections = TreeState.get_selected_objects()

        # Build set of object labels currently visible in tree
        visible_object_labels = set()
        for label, meta in self._label_map.items():
            if meta[0] == "object":
                visible_object_labels.add(label)

        logger.debug(f"[_handle_selections] selected from tree: {selected}")
        logger.debug(f"[_handle_selections] existing_selections: {existing_selections}")
        logger.debug(f"[_handle_selections] visible_object_labels count: {len(visible_object_labels)}")

        # Build set of currently selected labels in tree
        selected_set = set(selected)

        # Start with existing selections that are NOT visible in current tree
        # (these should be preserved across filter changes)
        preserved_selections = []
        for db, schema, name, obj_type in existing_selections:
            if name not in visible_object_labels:
                preserved_selections.append((db, schema, name, obj_type))
                logger.debug(f"[_handle_selections] PRESERVING (not visible): {name}")

        # Add newly selected items from the current tree
        new_selections = []
        for label in selected:
            if label not in self._label_map:
                logger.debug(f"[_handle_selections] label not in _label_map: {label}")
                continue

            meta = self._label_map[label]
            if meta[0] == "object":
                _, db, schema, name, obj_type = meta
                new_selections.append((db, schema, name, obj_type))
                logger.debug(f"[_handle_selections] NEW selection: {db}.{schema}.{name}")

        # Combine preserved + new selections (deduplicated)
        all_selections = preserved_selections + new_selections
        # Deduplicate while preserving order
        seen = set()
        unique_selections = []
        for item in all_selections:
            if item not in seen:
                seen.add(item)
                unique_selections.append(item)

        logger.debug(f"[_handle_selections] FINAL: preserved={len(preserved_selections)}, new={len(new_selections)}, unique={len(unique_selections)}")
        return unique_selections

    def render(self, databases: list[str]) -> None:
        """Render the tree navigation component.

        Args:
            databases: List of available database names
        """
        from snowflake_theme import icon_header, get_svg_icon

        logger.info(f"[TREE] ========== RENDER START ==========")

        # Clean up corrupted state
        TreeState.cleanup_state()

        # Check if tree should be read-only (on Generate step)
        # Steps: 0=Review, 1=Data Model, 2=Generate Output
        # Lock selections on Generate step to prevent changes during file generation
        wizard_step = st.session_state.get("wizard_step", 0)
        is_read_only = wizard_step >= 2

        # Header
        st.markdown(
            f"### {icon_header('select', 'Select Objects', size=24)}",
            unsafe_allow_html=True
        )

        # Show read-only notice on later steps
        if is_read_only:
            st.info(f"{get_svg_icon('lock', 16)} Selection locked. Use **Reset App** to start over.")

        # Search filter (hidden when read-only)
        search_term = ""
        if self.config.show_search and not is_read_only:
            search_term = st.text_input(
                "Filter databases",
                placeholder="Type to filter...",
                key="search_filter"
            ).strip().upper()

        # Check for databases
        if not databases:
            st.warning("No databases found.")
            return

        # Build tree
        tree_items = self.build_tree_items(databases, search_term)

        if not tree_items:
            st.info("No matching databases found.")
            return

        # Get pre-selected labels
        pre_selected = [
            name for _, _, name, _ in TreeState.get_selected_objects()
            if name is not None
        ] or None

        logger.debug(f"[render] search_term: '{search_term}', pre_selected: {pre_selected}")

        # Get expanded nodes from state
        expanded_nodes = TreeState.get_expanded_nodes()
        open_index = [n for n in expanded_nodes if n] if expanded_nodes else None
        tree_key = f"object_tree_{TreeState.get_reset_counter()}"

        # Note: We keep checkbox=True even in read-only mode because sac.tree doesn't support
        # a disabled state (checkbox=False switches to single-select mode).
        # Instead, we skip processing selection changes when is_read_only below.
        tree_color = "#CCCCCC" if is_read_only else self.config.tree_color

        result = sac.tree(
            items=tree_items,
            index=pre_selected,
            open_index=open_index,
            label="Select objects:" if not is_read_only else "Selected objects (locked):",
            icon="diagram-3",
            color=tree_color,
            open_all=False,
            checkbox=self.config.checkbox_mode,  # Keep checkboxes visible (changes ignored in read-only)
            checkbox_strict=not self.config.cascade_selection,
            show_line=True,
            return_index=False,
            key=tree_key
        )

        # Parse result
        if hasattr(result, 'selected') and hasattr(result, 'expanded'):
            selected = result.selected if isinstance(result.selected, list) else [result.selected] if result.selected else []
            expanded = result.expanded or []
        else:
            selected = result if isinstance(result, list) else [result] if result else []
            expanded = []

        # Filter out placeholders
        selected = [s for s in selected if s and not str(s).startswith("Loading")]

        # Handle selections (skip if read-only to preserve existing)
        if is_read_only:
            new_selections = TreeState.get_selected_objects()
        else:
            new_selections = self._handle_selections(selected)
            TreeState.set_selected_objects(new_selections)

        # Auto-expand parents of selected items
        expanded = self._ensure_parents_expanded(new_selections, expanded)

        if self.config.on_selection_change:
            self.config.on_selection_change(new_selections)

        # Handle expanded nodes - preserve state across loading reruns
        current_expanded = set(expanded or [])
        saved_expanded = set(TreeState.get_expanded_nodes() or [])
        passed_to_tree = set(open_index or [])

        # Only update if tree returned something different (user interacted)
        if current_expanded and current_expanded != passed_to_tree:
            final_expanded = list(current_expanded)
        elif not current_expanded and saved_expanded:
            # Tree returned empty but we have saved state - preserve it
            final_expanded = list(saved_expanded)
        else:
            final_expanded = list(current_expanded) if current_expanded else []

        TreeState.set_expanded_nodes(final_expanded)

        # Handle lazy loading
        needs_rerun = self._handle_expansions(final_expanded)

        if needs_rerun:
            st.rerun()

        # Show selection count
        if self.config.show_selection_count:
            count = len(TreeState.get_selected_objects())
            if count > 0:
                st.success(f"**{count}** object(s) selected")


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

def render_tree_navigation(session: Any, databases: list[str], config: TreeConfig = None) -> None:
    """Render tree navigation with default configuration.

    This is a convenience function for simple usage.

    Args:
        session: Snowflake session
        databases: List of database names
        config: Optional configuration
    """
    navigator = TreeNavigator(session, config)
    navigator.render(databases)
