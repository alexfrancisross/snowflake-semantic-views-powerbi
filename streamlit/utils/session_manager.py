"""
Centralized session state management for the Power BI Semantic Model Generator.

This module provides a type-safe, centralized approach to managing Streamlit
session state, replacing the scattered init_session_state() pattern.

Usage:
    from session_manager import get_app_state, reset_app_state

    state = get_app_state()
    state.wizard_step = 1
    state.selected_objects.append(("DB", "SCHEMA", "TABLE", "TABLE"))
"""

from dataclasses import dataclass, field
from typing import Any, Optional
import streamlit as st

from .config import CONFIG


# =============================================================================
# STATE DATACLASSES
# =============================================================================

@dataclass
class SelectionState:
    """State for object selection (Step 0-1).

    Attributes:
        selected_objects: List of (database, schema, name, object_type) tuples
        views_metadata: List of loaded SemanticViewMetadata objects
    """
    selected_objects: list[tuple[str, str, str, str]] = field(default_factory=list)
    views_metadata: list[Any] = field(default_factory=list)  # SemanticViewMetadata

    def add_object(self, database: str, schema: str, name: str, object_type: str) -> bool:
        """Add an object to the selection if not already present.

        Args:
            database: Database name
            schema: Schema name
            name: Object name
            object_type: Object type (SEMANTIC_VIEW, TABLE, VIEW)

        Returns:
            True if added, False if already exists
        """
        obj_tuple = (database, schema, name, object_type)
        if obj_tuple not in self.selected_objects:
            self.selected_objects.append(obj_tuple)
            return True
        return False

    def remove_object(self, database: str, schema: str, name: str, object_type: str) -> bool:
        """Remove an object from the selection.

        Args:
            database: Database name
            schema: Schema name
            name: Object name
            object_type: Object type

        Returns:
            True if removed, False if not found
        """
        obj_tuple = (database, schema, name, object_type)
        if obj_tuple in self.selected_objects:
            self.selected_objects.remove(obj_tuple)
            return True
        return False

    def clear(self) -> None:
        """Clear all selections."""
        self.selected_objects.clear()
        self.views_metadata.clear()

    @property
    def count(self) -> int:
        """Number of selected objects."""
        return len(self.selected_objects)

    @property
    def has_selection(self) -> bool:
        """Whether any objects are selected."""
        return len(self.selected_objects) > 0


@dataclass
class TreeNavigationState:
    """State for tree navigation component.

    Attributes:
        loaded_schemas: Cache of schemas per database {db: [schemas]}
        loaded_objects: Cache of objects per location {(db, schema): [ObjectInfo]}
        expanded_nodes: List of expanded tree node IDs
        reset_counter: Counter to force tree component reset
    """
    loaded_schemas: dict[str, list[str]] = field(default_factory=dict)
    loaded_objects: dict[tuple[str, str], list[Any]] = field(default_factory=dict)
    expanded_nodes: list[str] = field(default_factory=list)
    reset_counter: int = 0

    def get_schemas(self, database: str) -> list[str] | None:
        """Get cached schemas for a database.

        Args:
            database: Database name

        Returns:
            List of schema names if cached, None otherwise
        """
        return self.loaded_schemas.get(database)

    def set_schemas(self, database: str, schemas: list[str]) -> None:
        """Cache schemas for a database.

        Args:
            database: Database name
            schemas: List of schema names
        """
        self.loaded_schemas[database] = schemas

    def get_objects(self, database: str, schema: str) -> list[Any] | None:
        """Get cached objects for a schema.

        Args:
            database: Database name
            schema: Schema name

        Returns:
            List of ObjectInfo if cached, None otherwise
        """
        return self.loaded_objects.get((database, schema))

    def set_objects(self, database: str, schema: str, objects: list[Any]) -> None:
        """Cache objects for a schema.

        Args:
            database: Database name
            schema: Schema name
            objects: List of ObjectInfo
        """
        self.loaded_objects[(database, schema)] = objects

    def is_expanded(self, node_id: str) -> bool:
        """Check if a tree node is expanded.

        Args:
            node_id: Tree node identifier

        Returns:
            True if expanded
        """
        return node_id in self.expanded_nodes

    def toggle_expanded(self, node_id: str) -> bool:
        """Toggle tree node expansion state.

        Args:
            node_id: Tree node identifier

        Returns:
            New expansion state (True if now expanded)
        """
        if node_id in self.expanded_nodes:
            self.expanded_nodes.remove(node_id)
            return False
        else:
            self.expanded_nodes.append(node_id)
            return True

    def force_reset(self) -> None:
        """Force tree component to remount by incrementing counter."""
        self.reset_counter += 1

    def clear_cache(self) -> None:
        """Clear all cached data."""
        self.loaded_schemas.clear()
        self.loaded_objects.clear()


@dataclass
class DataModelState:
    """State for data model configuration (Step 2).

    Attributes:
        selected_relationships: Dict of {relationship_id: enabled} for toggles
        column_zones: Dict of column zone assignments per table
        measure_config: Dict of measure configuration per column
        manual_relationships: List of user-created relationships
        bridge_relationships: List of bridge table relationships
        active_relationship_choices: User choices for active relationships in conflicts
        duplicate_role_playing_dims: Dict of duplicate dimension configuration
    """
    selected_relationships: dict[str, bool] = field(default_factory=dict)
    column_zones: dict[str, dict[str, str]] = field(default_factory=dict)
    measure_config: dict[str, dict[str, Any]] = field(default_factory=dict)
    # Manual relationship creation (v3.2+)
    manual_relationships: list[Any] = field(default_factory=list)  # SuggestedRelationship
    # Bridge relationships detected from data model
    bridge_relationships: list[Any] = field(default_factory=list)  # RelationshipMetadata
    # User choices for which relationship to make active in conflict pairs
    active_relationship_choices: dict[str, str] = field(default_factory=dict)
    # Role-playing dimension duplicate configuration
    duplicate_role_playing_dims: dict[str, Any] = field(default_factory=dict)

    def is_relationship_enabled(self, rel_id: str, default: bool = True) -> bool:
        """Check if a relationship is enabled.

        Args:
            rel_id: Relationship identifier
            default: Default value if not set

        Returns:
            Whether relationship is enabled
        """
        return self.selected_relationships.get(rel_id, default)

    def set_relationship_enabled(self, rel_id: str, enabled: bool) -> None:
        """Set relationship enabled state.

        Args:
            rel_id: Relationship identifier
            enabled: Whether enabled
        """
        self.selected_relationships[rel_id] = enabled

    def get_column_zone(self, table: str, column: str) -> str | None:
        """Get zone assignment for a column.

        Args:
            table: Table name
            column: Column name

        Returns:
            Zone name (DIMENSION, METRIC, FACT) or None
        """
        return self.column_zones.get(table, {}).get(column)

    def set_column_zone(self, table: str, column: str, zone: str) -> None:
        """Set zone assignment for a column.

        Args:
            table: Table name
            column: Column name
            zone: Zone name (DIMENSION, METRIC, FACT, EXCLUDE)
        """
        if table not in self.column_zones:
            self.column_zones[table] = {}
        self.column_zones[table][column] = zone

    def add_manual_relationship(self, relationship: Any) -> bool:
        """Add a manually created relationship.

        Args:
            relationship: SuggestedRelationship with source=MANUAL

        Returns:
            True if added, False if duplicate exists
        """
        rel_id = relationship.relationship_id
        existing_ids = {r.relationship_id for r in self.manual_relationships}
        if rel_id not in existing_ids:
            self.manual_relationships.append(relationship)
            self.selected_relationships[rel_id] = True
            return True
        return False

    def remove_manual_relationship(self, rel_id: str) -> bool:
        """Remove a manually created relationship.

        Args:
            rel_id: Relationship ID to remove

        Returns:
            True if removed, False if not found
        """
        for i, rel in enumerate(self.manual_relationships):
            if rel.relationship_id == rel_id:
                self.manual_relationships.pop(i)
                self.selected_relationships.pop(rel_id, None)
                return True
        return False

    def clear(self) -> None:
        """Clear all data model configuration."""
        self.selected_relationships.clear()
        self.column_zones.clear()
        self.measure_config.clear()
        self.manual_relationships.clear()
        self.bridge_relationships.clear()
        self.active_relationship_choices.clear()
        self.duplicate_role_playing_dims.clear()


@dataclass
class UIState:
    """State for transient UI elements.

    These are UI-specific states that don't persist across sessions
    but need to be tracked during the current session.

    Attributes:
        show_add_rel_form: Whether the add relationship form is visible
        editing_rel_id: ID of relationship being edited (None if not editing)
        just_reset: Flag indicating a reset just occurred

    Note: search_filter is NOT stored here - it's a Streamlit widget key
    that Streamlit manages directly via st.session_state.search_filter
    """
    show_add_rel_form: bool = False
    editing_rel_id: Optional[str] = None
    just_reset: bool = False


@dataclass
class ConfigurationState:
    """State for app configuration settings.

    Attributes:
        pbi_mode: Power BI connection mode (DirectQuery or Import)
        dark_mode: Theme toggle (False=Light, True=Dark)
        output_format: Output format (PBIT, PBIX, TMDL)
    """
    pbi_mode: str = field(default_factory=lambda: CONFIG.DEFAULT_PBI_MODE)
    dark_mode: bool = False
    output_format: str = "PBIT"

    def toggle_dark_mode(self) -> bool:
        """Toggle dark mode and return new state."""
        self.dark_mode = not self.dark_mode
        return self.dark_mode


# =============================================================================
# MAIN APP STATE
# =============================================================================

@dataclass
class AppState:
    """Complete application state.

    Combines all state categories into a single, type-safe object.
    Use get_app_state() to access the singleton instance.

    Attributes:
        wizard_step: Current wizard step index (0-4)
        selection: Object selection state
        tree: Tree navigation state
        model: Data model configuration state
        config: App configuration state
        ui: Transient UI state
    """
    wizard_step: int = 0
    selection: SelectionState = field(default_factory=SelectionState)
    tree: TreeNavigationState = field(default_factory=TreeNavigationState)
    model: DataModelState = field(default_factory=DataModelState)
    config: ConfigurationState = field(default_factory=ConfigurationState)
    ui: UIState = field(default_factory=UIState)

    def can_proceed_to_step(self, target_step: int) -> bool:
        """Check if user can proceed to a specific wizard step.

        Args:
            target_step: Target step index

        Returns:
            True if allowed to proceed
        """
        # Can always go back
        if target_step < self.wizard_step:
            return True

        # Step 0 -> 1: Need at least one selection
        if target_step >= 1 and not self.selection.has_selection:
            return False

        # Step 1 -> 2: Need loaded metadata
        if target_step >= 2 and len(self.selection.views_metadata) == 0:
            return False

        return True

    def go_to_step(self, step: int) -> bool:
        """Navigate to a wizard step if allowed.

        Args:
            step: Target step index (0-4)

        Returns:
            True if navigation succeeded
        """
        if 0 <= step < CONFIG.WIZARD_TOTAL_STEPS:
            if self.can_proceed_to_step(step):
                self.wizard_step = step
                return True
        return False

    def next_step(self) -> bool:
        """Go to next wizard step if allowed.

        Returns:
            True if navigation succeeded
        """
        return self.go_to_step(self.wizard_step + 1)

    def prev_step(self) -> bool:
        """Go to previous wizard step.

        Returns:
            True if navigation succeeded
        """
        return self.go_to_step(self.wizard_step - 1)

    def reset(self) -> None:
        """Reset all state to defaults."""
        self.wizard_step = 0
        self.selection = SelectionState()
        self.tree = TreeNavigationState()
        self.model = DataModelState()
        # Keep config (user preferences)


# =============================================================================
# SESSION STATE ACCESSORS
# =============================================================================

_STATE_KEY = "_app_state"
_STATE_VERSION = 2  # Increment when AppState structure changes


def _is_state_outdated(state: Any) -> bool:
    """Check if a cached AppState object is missing new fields.

    This handles the case where Streamlit has cached an old AppState
    object that was created before new fields were added.

    Args:
        state: Cached state object

    Returns:
        True if state is outdated and needs recreation
    """
    # Check for version marker
    if not hasattr(state, '_version'):
        return True

    # Check for required nested objects
    if not hasattr(state, 'ui'):
        return True

    # Check for required fields on nested objects
    if hasattr(state, 'model'):
        if not hasattr(state.model, 'bridge_relationships'):
            return True
        if not hasattr(state.model, 'active_relationship_choices'):
            return True

    return False


def get_app_state() -> AppState:
    """Get the application state singleton.

    Creates the state if it doesn't exist or if the cached state
    is outdated (missing new fields from schema changes).
    The state is stored in Streamlit's session_state for persistence.

    Returns:
        AppState instance
    """
    if _STATE_KEY in st.session_state:
        cached = st.session_state[_STATE_KEY]
        if not _is_state_outdated(cached):
            return cached
        # Cached state is outdated - migrate data to new structure
        new_state = _migrate_outdated_state(cached)
        st.session_state[_STATE_KEY] = new_state
        return new_state

    # No cached state - create fresh
    new_state = AppState()
    new_state._version = _STATE_VERSION
    st.session_state[_STATE_KEY] = new_state
    return new_state


def _migrate_outdated_state(old_state: Any) -> AppState:
    """Migrate data from an outdated AppState to a new one.

    Preserves user data while upgrading to new schema.

    Args:
        old_state: Outdated AppState object

    Returns:
        New AppState with migrated data
    """
    new_state = AppState()
    new_state._version = _STATE_VERSION

    # Migrate wizard_step
    if hasattr(old_state, 'wizard_step'):
        new_state.wizard_step = old_state.wizard_step

    # Migrate selection state
    if hasattr(old_state, 'selection'):
        old_sel = old_state.selection
        if hasattr(old_sel, 'selected_objects'):
            new_state.selection.selected_objects = list(old_sel.selected_objects)
        if hasattr(old_sel, 'views_metadata'):
            new_state.selection.views_metadata = list(old_sel.views_metadata)

    # Migrate tree state
    if hasattr(old_state, 'tree'):
        old_tree = old_state.tree
        if hasattr(old_tree, 'loaded_schemas'):
            new_state.tree.loaded_schemas = dict(old_tree.loaded_schemas)
        if hasattr(old_tree, 'loaded_objects'):
            new_state.tree.loaded_objects = dict(old_tree.loaded_objects)
        if hasattr(old_tree, 'expanded_nodes'):
            new_state.tree.expanded_nodes = list(old_tree.expanded_nodes)
        if hasattr(old_tree, 'reset_counter'):
            new_state.tree.reset_counter = old_tree.reset_counter

    # Migrate model state
    if hasattr(old_state, 'model'):
        old_model = old_state.model
        if hasattr(old_model, 'selected_relationships'):
            new_state.model.selected_relationships = dict(old_model.selected_relationships)
        if hasattr(old_model, 'manual_relationships'):
            new_state.model.manual_relationships = list(old_model.manual_relationships)
        if hasattr(old_model, 'column_zones'):
            new_state.model.column_zones = dict(old_model.column_zones)
        if hasattr(old_model, 'measure_config'):
            new_state.model.measure_config = dict(old_model.measure_config)
        # New fields - only migrate if they exist
        if hasattr(old_model, 'bridge_relationships'):
            new_state.model.bridge_relationships = list(old_model.bridge_relationships)
        if hasattr(old_model, 'active_relationship_choices'):
            new_state.model.active_relationship_choices = dict(old_model.active_relationship_choices)
        if hasattr(old_model, 'duplicate_role_playing_dims'):
            new_state.model.duplicate_role_playing_dims = dict(old_model.duplicate_role_playing_dims)

    # Migrate config state
    if hasattr(old_state, 'config'):
        old_config = old_state.config
        if hasattr(old_config, 'pbi_mode'):
            new_state.config.pbi_mode = old_config.pbi_mode
        if hasattr(old_config, 'dark_mode'):
            new_state.config.dark_mode = old_config.dark_mode
        if hasattr(old_config, 'output_format'):
            new_state.config.output_format = old_config.output_format

    # UI state is new - no migration needed (defaults are fine)

    return new_state


def reset_app_state() -> AppState:
    """Reset application state to defaults.

    Returns:
        Fresh AppState instance
    """
    new_state = AppState()
    new_state._version = _STATE_VERSION
    st.session_state[_STATE_KEY] = new_state
    return new_state


def has_app_state() -> bool:
    """Check if application state has been initialized.

    Returns:
        True if state exists
    """
    return _STATE_KEY in st.session_state


# =============================================================================
# MIGRATION HELPERS
# =============================================================================

def migrate_legacy_state() -> None:
    """Migrate legacy session state keys to new AppState structure.

    Call this during app initialization to handle existing sessions
    that used the old scattered session state pattern.
    """
    state = get_app_state()

    # Migrate selected_objects
    if "selected_objects" in st.session_state:
        legacy = st.session_state.selected_objects
        if legacy and not state.selection.selected_objects:
            state.selection.selected_objects = list(legacy)

    # Migrate views_metadata
    if "views_metadata" in st.session_state:
        legacy = st.session_state.views_metadata
        if legacy and not state.selection.views_metadata:
            state.selection.views_metadata = list(legacy)

    # Migrate wizard_step
    if "wizard_step" in st.session_state:
        legacy = st.session_state.wizard_step
        if isinstance(legacy, int) and state.wizard_step == 0:
            state.wizard_step = legacy

    # Migrate loaded_schemas
    if "loaded_schemas" in st.session_state:
        legacy = st.session_state.loaded_schemas
        if legacy and not state.tree.loaded_schemas:
            state.tree.loaded_schemas = dict(legacy)

    # Migrate loaded_objects
    if "loaded_objects" in st.session_state:
        legacy = st.session_state.loaded_objects
        if legacy and not state.tree.loaded_objects:
            state.tree.loaded_objects = dict(legacy)

    # Migrate expanded_nodes
    if "expanded_nodes" in st.session_state:
        legacy = st.session_state.expanded_nodes
        if legacy and not state.tree.expanded_nodes:
            state.tree.expanded_nodes = list(legacy)

    # Migrate pbi_mode
    if "pbi_mode" in st.session_state:
        legacy = st.session_state.pbi_mode
        if legacy and state.config.pbi_mode == CONFIG.DEFAULT_PBI_MODE:
            state.config.pbi_mode = legacy

    # Migrate dark_mode
    if "dark_mode" in st.session_state:
        legacy = st.session_state.dark_mode
        if isinstance(legacy, bool):
            state.config.dark_mode = legacy

    # Migrate manual_relationships
    if "manual_relationships" in st.session_state:
        legacy = st.session_state.manual_relationships
        if legacy and not state.model.manual_relationships:
            state.model.manual_relationships = list(legacy)

    # Migrate bridge_relationships
    if "bridge_relationships" in st.session_state:
        legacy = st.session_state.bridge_relationships
        if legacy and not state.model.bridge_relationships:
            state.model.bridge_relationships = list(legacy)

    # Migrate active_relationship_choices
    if "active_relationship_choices" in st.session_state:
        legacy = st.session_state.active_relationship_choices
        if legacy and not state.model.active_relationship_choices:
            state.model.active_relationship_choices = dict(legacy)

    # Migrate duplicate_role_playing_dims
    if "duplicate_role_playing_dims" in st.session_state:
        legacy = st.session_state.duplicate_role_playing_dims
        if legacy and not state.model.duplicate_role_playing_dims:
            state.model.duplicate_role_playing_dims = dict(legacy)

    # Migrate selected_relationships
    if "selected_relationships" in st.session_state:
        legacy = st.session_state.selected_relationships
        if legacy and not state.model.selected_relationships:
            state.model.selected_relationships = dict(legacy)


# =============================================================================
# BIDIRECTIONAL SYNC (for gradual migration)
# =============================================================================

# Map of legacy session_state keys to AppState paths
_LEGACY_KEY_MAP = {
    # Core state
    "wizard_step": ("wizard_step", None),
    "selected_objects": ("selection", "selected_objects"),
    "views_metadata": ("selection", "views_metadata"),

    # Tree navigation
    "loaded_schemas": ("tree", "loaded_schemas"),
    "loaded_objects": ("tree", "loaded_objects"),
    "expanded_nodes": ("tree", "expanded_nodes"),
    "tree_reset_counter": ("tree", "reset_counter"),

    # Data model
    "selected_relationships": ("model", "selected_relationships"),
    "manual_relationships": ("model", "manual_relationships"),
    "bridge_relationships": ("model", "bridge_relationships"),
    "active_relationship_choices": ("model", "active_relationship_choices"),
    "duplicate_role_playing_dims": ("model", "duplicate_role_playing_dims"),

    # Configuration
    "pbi_mode": ("config", "pbi_mode"),
    "dark_mode": ("config", "dark_mode"),

    # UI state (excluding widget keys - Streamlit manages those directly)
    "show_add_rel_form": ("ui", "show_add_rel_form"),
    "editing_rel_id": ("ui", "editing_rel_id"),
    # NOTE: search_filter is NOT included here - it's a widget key that Streamlit manages
    "_just_reset": ("ui", "just_reset"),
}


def sync_to_legacy() -> None:
    """Sync AppState values to legacy session_state keys.

    Call this after modifying AppState to ensure legacy code
    that reads from st.session_state sees updated values.

    This enables gradual migration - new code uses AppState,
    legacy code continues to work via session_state.
    """
    state = get_app_state()

    for legacy_key, (attr1, attr2) in _LEGACY_KEY_MAP.items():
        try:
            if attr2 is None:
                # Direct attribute on AppState
                value = getattr(state, attr1, None)
            else:
                # Nested attribute (e.g., state.selection.selected_objects)
                sub_state = getattr(state, attr1, None)
                if sub_state is None:
                    continue
                # Use getattr with default to handle old cached objects
                value = getattr(sub_state, attr2, None)
                if value is None:
                    # Attribute doesn't exist on old cached object - skip
                    continue

            # Copy to session_state
            st.session_state[legacy_key] = value
        except AttributeError:
            # Old cached AppState object missing new fields - skip
            pass


def sync_from_legacy() -> None:
    """Sync legacy session_state values back to AppState.

    Call this at the start of each render cycle to capture any
    changes made by legacy code or widget callbacks.

    This enables gradual migration - widgets can still use
    session_state keys while AppState becomes source of truth.
    """
    state = get_app_state()

    for legacy_key, (attr1, attr2) in _LEGACY_KEY_MAP.items():
        if legacy_key not in st.session_state:
            continue

        value = st.session_state[legacy_key]

        if attr2 is None:
            # Direct attribute on AppState
            setattr(state, attr1, value)
        else:
            # Nested attribute
            sub_state = getattr(state, attr1)
            setattr(sub_state, attr2, value)


def _init_legacy_keys_if_missing() -> None:
    """Initialize legacy session_state keys if they don't exist.

    This ensures legacy code that accesses st.session_state.key directly
    doesn't fail with AttributeError. Only sets defaults for missing keys,
    does NOT overwrite existing values (preserves user changes).
    """
    state = get_app_state()

    for legacy_key, (attr1, attr2) in _LEGACY_KEY_MAP.items():
        # Only initialize if key doesn't exist
        if legacy_key in st.session_state:
            continue

        try:
            if attr2 is None:
                value = getattr(state, attr1, None)
            else:
                sub_state = getattr(state, attr1, None)
                if sub_state is None:
                    continue
                value = getattr(sub_state, attr2, None)

            # Set default value in session_state
            if value is not None:
                st.session_state[legacy_key] = value
            else:
                # Provide sensible defaults for common types
                if legacy_key in ("selected_objects", "views_metadata", "expanded_nodes"):
                    st.session_state[legacy_key] = []
                elif legacy_key in ("loaded_schemas", "loaded_objects", "selected_relationships",
                                    "manual_relationships", "bridge_relationships",
                                    "active_relationship_choices", "duplicate_role_playing_dims"):
                    st.session_state[legacy_key] = {}
                elif legacy_key == "wizard_step":
                    st.session_state[legacy_key] = 0
                elif legacy_key == "tree_reset_counter":
                    st.session_state[legacy_key] = 0
        except AttributeError:
            pass


def init_session_state() -> AppState:
    """Initialize session state with AppState as source of truth.

    This replaces the legacy init_session_state() pattern.
    Call this once at app startup.

    1. Creates or retrieves AppState
    2. Migrates any legacy session_state values
    3. Initializes missing legacy keys with defaults (for backward compatibility)

    Note: We do NOT call sync_to_legacy() here because it would overwrite
    any widget/callback changes to session_state before sync_from_legacy()
    can capture them. The correct order is:
      1. sync_from_legacy() - capture widget changes
      2. app logic
      3. sync_to_legacy() - only if AppState was explicitly modified

    Returns:
        Initialized AppState instance
    """
    # Get or create AppState
    state = get_app_state()

    # Migrate any existing legacy state (one-time)
    migrate_legacy_state()

    # Initialize missing legacy keys with defaults (doesn't overwrite existing)
    _init_legacy_keys_if_missing()

    return state


def get_state_value(key: str, default: Any = None) -> Any:
    """Get a state value using the new unified approach.

    Prefer using get_app_state() directly, but this helper
    provides a drop-in replacement for st.session_state.get().

    Args:
        key: Legacy key name (e.g., "wizard_step", "views_metadata")
        default: Default value if not found

    Returns:
        State value
    """
    if key not in _LEGACY_KEY_MAP:
        # Unknown key - fall back to session_state
        return st.session_state.get(key, default)

    state = get_app_state()
    attr1, attr2 = _LEGACY_KEY_MAP[key]

    if attr2 is None:
        return getattr(state, attr1, default)
    else:
        sub_state = getattr(state, attr1, None)
        if sub_state is None:
            return default
        return getattr(sub_state, attr2, default)


def set_state_value(key: str, value: Any) -> None:
    """Set a state value using the new unified approach.

    Prefer using get_app_state() directly, but this helper
    provides a drop-in replacement for st.session_state[key] = value.

    Args:
        key: Legacy key name
        value: Value to set
    """
    if key not in _LEGACY_KEY_MAP:
        # Unknown key - fall back to session_state
        st.session_state[key] = value
        return

    state = get_app_state()
    attr1, attr2 = _LEGACY_KEY_MAP[key]

    if attr2 is None:
        setattr(state, attr1, value)
    else:
        sub_state = getattr(state, attr1)
        setattr(sub_state, attr2, value)

    # Also update legacy key for backwards compatibility
    st.session_state[key] = value
