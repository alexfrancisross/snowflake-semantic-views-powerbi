"""
PBIT (Power BI Template) file generator.
Creates .pbit files that can be opened directly in Power BI Desktop.

PBIT files are ZIP archives containing:
- Version: Version string (UTF-16-LE)
- [Content_Types].xml: MIME type manifest (UTF-8)
- DataModelSchema: Model definition JSON (UTF-16-LE)
- Report/Layout: Report layout JSON (UTF-16-LE)
- Settings: Settings JSON (UTF-16-LE)
- Metadata: Metadata JSON (UTF-16-LE)
- Connections: Connections JSON (UTF-8) - optional
- DiagramLayout: Diagram layout JSON (UTF-16-LE) - optional
- SecurityBindings: Binary security data - optional
"""

import io
import json
import logging
import uuid
import zipfile
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

from .metadata_fetcher import (
    SemanticViewMetadata,
    ColumnMetadata,
    RelationshipMetadata,
    TableMetadata,
    CardinalityInfo,
    has_composite_primary_key,
)
from .type_mappings import snowflake_to_pbi_type


# Current PBIT version (matches Power BI Desktop)
PBIT_VERSION = "1.28"


def generate_lineage_tag() -> str:
    """Generate a unique lineage tag (UUID format)."""
    return str(uuid.uuid4())


def generate_page_id() -> str:
    """Generate a random page ID (20 hex characters)."""
    return uuid.uuid4().hex[:20]


def escape_m_string(value: str | None) -> str:
    """Escape a string for use in M (Power Query) expressions."""
    return (value or "").replace('"', '""')


def escape_m_identifier(name: str) -> str:
    """
    Escape an identifier for use as a variable name in M (Power Query).

    M identifiers with spaces, special characters, or starting with numbers
    must be wrapped in #"...".

    Examples:
        "MyTable" -> "MyTable"
        "Table With Spaces" -> '#"Table With Spaces"'
        "123_starts_with_number" -> '#"123_starts_with_number"'
    """
    import re
    # Check if identifier needs escaping:
    # - Contains spaces or special chars (not alphanumeric or underscore)
    # - Starts with a number
    # - Is empty
    if not name or re.search(r'[^a-zA-Z0-9_]', name) or name[0].isdigit():
        # Escape inner quotes and wrap in #"..."
        escaped = name.replace('"', '""')
        return f'#"{escaped}"'
    return name


def generate_version() -> str:
    """Generate Version file content."""
    return PBIT_VERSION


def generate_content_types_xml() -> str:
    """
    Generate [Content_Types].xml manifest.

    Returns:
        XML string declaring content types for all parts.
    """
    return '''<?xml version="1.0" encoding="utf-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="json" ContentType=""/><Override PartName="/Version" ContentType=""/><Override PartName="/DataModelSchema" ContentType=""/><Override PartName="/DiagramLayout" ContentType=""/><Override PartName="/Report/Layout" ContentType=""/><Override PartName="/Settings" ContentType="application/json"/><Override PartName="/Metadata" ContentType="application/json"/><Override PartName="/SecurityBindings" ContentType=""/></Types>'''


def generate_settings() -> str:
    """
    Generate Settings JSON.

    Returns:
        JSON string with settings configuration.
    """
    settings = {
        "Version": 4,
        "ReportSettings": {},
        "QueriesSettings": {
            "TypeDetectionEnabled": True,
            "RelationshipImportEnabled": True,
            "Version": "2.149.178.0"
        }
    }
    return json.dumps(settings)


def generate_metadata(description: str = "") -> str:
    """
    Generate Metadata JSON.

    Args:
        description: Optional file description.

    Returns:
        JSON string with metadata.
    """
    metadata = {
        "Version": 5,
        "AutoCreatedRelationships": [],
        "CreatedFrom": "Cloud",
        "CreatedFromRelease": "2025.01"
    }
    if description:
        metadata["FileDescription"] = description
    return json.dumps(metadata)


def generate_connections() -> str:
    """
    Generate Connections JSON.
    Empty for DirectQuery templates.

    Returns:
        JSON string with connections.
    """
    connections = {
        "Version": 3,
        "RemoteArtifacts": []
    }
    return json.dumps(connections)


def _remove_overlaps(
    positions: dict[str, tuple[float, float]],
    node_width: float,
    node_height: float,
    padding: float = 20.0,
) -> dict[str, tuple[float, float]]:
    """
    Greedy overlap removal - shift overlapping nodes apart.

    Similar to Power BI's GreedyOverlapRemover algorithm.
    Iteratively detects overlapping node pairs and shifts them apart.

    Args:
        positions: Dict mapping node name to (x, y) position.
        node_width: Width of each node.
        node_height: Height of each node.
        padding: Minimum gap between nodes.

    Returns:
        Updated positions dict with overlaps resolved.
    """
    if len(positions) < 2:
        return positions

    # Work with a mutable copy
    pos = dict(positions)
    names = list(pos.keys())
    changed = True
    max_iterations = 100

    while changed and max_iterations > 0:
        changed = False
        max_iterations -= 1

        for i in range(len(names)):
            name1 = names[i]
            x1, y1 = pos[name1]

            for j in range(i + 1, len(names)):
                name2 = names[j]
                x2, y2 = pos[name2]

                # Check if nodes overlap (including padding)
                overlap_x = (node_width + padding) - abs(x1 - x2)
                overlap_y = (node_height + padding) - abs(y1 - y2)

                if overlap_x > 0 and overlap_y > 0:
                    # Nodes overlap - shift node2 away from node1
                    # Choose direction with smaller overlap to minimize movement
                    if overlap_x < overlap_y:
                        # Shift horizontally
                        shift = overlap_x + 1  # +1 to ensure separation
                        if x2 >= x1:
                            pos[name2] = (x2 + shift, y2)
                        else:
                            pos[name2] = (x2 - shift, y2)
                    else:
                        # Shift vertically
                        shift = overlap_y + 1
                        if y2 >= y1:
                            pos[name2] = (x2, y2 + shift)
                        else:
                            pos[name2] = (x2, y2 - shift)

                    changed = True

    return pos


def generate_diagram_layout(
    table_names: list[str],
    relationships: list[RelationshipMetadata] | None = None,
    role_playing_dims: dict[str, list[str]] | None = None,
) -> str:
    """
    Generate DiagramLayout JSON with relationship-based clustering.

    Tables are positioned based on their relationships:
    - Connected tables are placed near each other
    - Role-playing dimension copies are placed below their parent table
    - Includes overlap removal to prevent table collisions

    Args:
        table_names: List of table names to include in diagram.
        relationships: Optional list of relationships for clustering.
        role_playing_dims: Optional dict mapping dimension name to referencing tables.

    Returns:
        JSON string with diagram layout.
    """
    if not table_names:
        return json.dumps({
            "version": "1.1.0",
            "diagrams": [{"ordinal": 0, "scrollPosition": {"x": 0, "y": 0}, "nodes": [], "name": "All tables", "zoomValue": 100}],
            "selectedDiagram": "All tables",
            "defaultDiagram": "All tables"
        })

    # Layout constants - ensure spacing exceeds node dimensions
    NODE_WIDTH = 234
    NODE_HEIGHT = 200
    X_PADDING = 50       # Horizontal gap between nodes
    Y_PADDING = 30       # Vertical gap between nodes
    X_SPACING = NODE_WIDTH + X_PADDING    # 284 - full column width
    Y_SPACING = NODE_HEIGHT + Y_PADDING   # 230 - full row height

    # Build adjacency list for clustering
    from collections import defaultdict
    connections: dict[str, set[str]] = defaultdict(set)

    if relationships:
        for rel in relationships:
            if rel.from_table in table_names and rel.to_table in table_names:
                connections[rel.from_table].add(rel.to_table)
                connections[rel.to_table].add(rel.from_table)

    # Identify role-playing dimension copies (e.g., CUSTOMER_NATION, SUPPLIER_NATION)
    role_playing_copies: dict[str, str] = {}  # copy_name -> parent_table
    if role_playing_dims:
        for dim_name, referencing_tables in role_playing_dims.items():
            for ref_table in referencing_tables:
                copy_name = f"{ref_table}_{dim_name}"
                if copy_name in table_names:
                    role_playing_copies[copy_name] = ref_table

    # Find the "center" table (most connections) - this will be our anchor
    connection_counts = {name: len(connections.get(name, set())) for name in table_names}
    # Exclude role-playing copies from being the center
    main_tables = [t for t in table_names if t not in role_playing_copies]
    if main_tables:
        center_table = max(main_tables, key=lambda t: connection_counts.get(t, 0))
    else:
        center_table = table_names[0]

    # Position tables using BFS from center
    positions: dict[str, tuple[float, float]] = {}
    visited: set[str] = set()
    levels: dict[int, list[str]] = defaultdict(list)

    # BFS to assign levels (distance from center)
    from collections import deque
    queue = deque([(center_table, 0)])
    visited.add(center_table)
    levels[0].append(center_table)

    while queue:
        current, level = queue.popleft()
        for neighbor in connections.get(current, set()):
            if neighbor not in visited and neighbor not in role_playing_copies:
                visited.add(neighbor)
                levels[level + 1].append(neighbor)
                queue.append((neighbor, level + 1))

    # Add any unvisited tables (disconnected) to the last level
    for name in main_tables:
        if name not in visited:
            max_level = max(levels.keys()) if levels else 0
            levels[max_level + 1].append(name)

    # Calculate positions by level
    # Level 0 (center) goes in the middle column
    # Odd levels go to the right, even levels go to the left (alternating)
    max_level = max(levels.keys()) if levels else 0
    center_x = (max_level + 1) * X_SPACING  # Center column X position

    for level, tables_at_level in levels.items():
        # Determine X position based on level
        if level == 0:
            x = center_x
        elif level % 2 == 1:
            x = center_x + ((level + 1) // 2) * X_SPACING  # Right side
        else:
            x = center_x - (level // 2) * X_SPACING  # Left side

        # Stack tables vertically at this level (with proper spacing)
        total_height = len(tables_at_level) * Y_SPACING
        start_y = -total_height // 2 + Y_SPACING // 2

        for i, table in enumerate(tables_at_level):
            y = start_y + i * Y_SPACING
            positions[table] = (float(x), float(y))

    # Position role-playing copies below their parent tables
    # Group copies by parent to stack them properly
    copies_by_parent: dict[str, list[str]] = defaultdict(list)
    for copy_name, parent_table in role_playing_copies.items():
        copies_by_parent[parent_table].append(copy_name)

    for parent_table, copies in copies_by_parent.items():
        if parent_table in positions:
            parent_x, parent_y = positions[parent_table]
            # Stack copies vertically below the parent
            for i, copy_name in enumerate(copies):
                copy_y = parent_y + (i + 1) * Y_SPACING
                positions[copy_name] = (parent_x, copy_y)
        else:
            # Fallback: place at end of diagram
            max_x = max(p[0] for p in positions.values()) if positions else 0
            for i, copy_name in enumerate(copies):
                positions[copy_name] = (max_x + X_SPACING, float(i * Y_SPACING))

    # Remove any overlapping nodes
    positions = _remove_overlaps(positions, NODE_WIDTH, NODE_HEIGHT, padding=X_PADDING)

    # Normalize positions to start from (50, 50) with positive coordinates
    if positions:
        min_x = min(p[0] for p in positions.values())
        min_y = min(p[1] for p in positions.values())
        positions = {
            name: (x - min_x + 50, y - min_y + 50)
            for name, (x, y) in positions.items()
        }

    # Build nodes list
    nodes = []
    for i, name in enumerate(table_names):
        x, y = positions.get(name, (i * X_SPACING + 50, 50))
        nodes.append({
            "location": {"x": float(x), "y": float(y)},
            "nodeIndex": name,
            "size": {"height": NODE_HEIGHT, "width": NODE_WIDTH},
            "zIndex": i
        })

    layout = {
        "version": "1.1.0",
        "diagrams": [
            {
                "ordinal": 0,
                "scrollPosition": {"x": 0, "y": 0},
                "nodes": nodes,
                "name": "All tables",
                "zoomValue": 100,
                "pinKeyFieldsToTop": False,
                "showExtraHeaderInfo": False,
                "hideKeyFieldsWhenCollapsed": False
            }
        ],
        "selectedDiagram": "All tables",
        "defaultDiagram": "All tables"
    }
    return json.dumps(layout)


def generate_report_layout(page_name: str = "Page 1") -> str:
    """
    Generate Report/Layout JSON with theme reference.

    Args:
        page_name: Display name for the report page.

    Returns:
        JSON string with report layout including theme reference.
    """
    page_id = generate_page_id()

    # Config with theme collection matching working PBIX files
    config = {
        "version": "5.68",
        "themeCollection": {
            "baseTheme": {
                "name": "CY25SU11",
                "version": {
                    "visual": "2.4.0",
                    "report": "3.0.0",
                    "page": "2.3.0"
                },
                "type": 2
            }
        },
        "activeSectionIndex": 0,
        "defaultDrillFilterOtherVisuals": True,
        "settings": {
            "useNewFilterPaneExperience": True,
            "allowChangeFilterTypes": True,
            "useStylableVisualContainerHeader": True,
            "queryLimitOption": 6,
            "exportDataMode": 1,
            "useDefaultAggregateDisplayName": True,
            "useEnhancedTooltips": True
        },
        "objects": {
            "section": [{
                "properties": {
                    "verticalAlignment": {
                        "expr": {
                            "Literal": {
                                "Value": "'Top'"
                            }
                        }
                    }
                }
            }]
        }
    }

    layout = {
        "id": 0,
        "resourcePackages": [{
            "resourcePackage": {
                "name": "SharedResources",
                "type": 2,
                "items": [{
                    "type": 202,
                    "path": "BaseThemes/CY25SU11.json",
                    "name": "CY25SU11"
                }],
                "disabled": False
            }
        }],
        "sections": [
            {
                "id": 0,
                "name": page_id,
                "displayName": page_name,
                "filters": "[]",
                "ordinal": 0,
                "visualContainers": [],
                "config": "{}",
                "displayOption": 1,
                "width": 1280,
                "height": 720
            }
        ],
        "config": json.dumps(config),
        "layoutOptimization": 0
    }
    return json.dumps(layout)


def load_theme_file() -> bytes:
    """
    Load the CY25SU11.json theme file.

    Returns:
        Theme file content as bytes
    """
    import os
    locations = [
        os.path.join(os.path.dirname(__file__), 'CY25SU11.json'),
        'CY25SU11.json',
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'CY25SU11.json'),
    ]

    for path in locations:
        if os.path.exists(path):
            with open(path, 'rb') as f:
                return f.read()

    # Fallback: minimal theme
    return b'{"name":"CY25SU11","dataColors":["#118DFF","#12239E"]}'


def is_self_referential(rel: RelationshipMetadata) -> bool:
    """Check if relationship is self-referential (same table on both sides).

    Self-referential relationships (e.g., Employee -> Manager) are shown
    in the UI with a warning but NOT exported to Power BI since PBI
    doesn't support tables with relationships to themselves.

    Args:
        rel: Relationship metadata to check.

    Returns:
        True if from_table equals to_table.
    """
    return rel.from_table == rel.to_table


def collect_all_relationships(
    views_metadata: list[SemanticViewMetadata],
    session: Any = None
) -> list[RelationshipMetadata]:
    """
    Collect all relationships from multiple tables/views.

    Only includes relationships where BOTH tables are in the selection.
    Self-referential relationships ARE included (shown with warning in UI)
    but will be filtered out during PBIT export.

    Args:
        views_metadata: List of view metadata objects.
        session: Optional Snowpark session for cardinality enrichment.

    Returns:
        List of RelationshipMetadata for relationships between selected tables.
    """
    from .metadata_fetcher import enrich_relationship_with_cardinality

    # Get set of table names that are in our selection
    selected_tables = {m.view for m in views_metadata}

    # Build lookup for metadata by table name
    metadata_by_name = {m.view: m for m in views_metadata}

    all_relationships = []
    seen_ids = set()

    for metadata in views_metadata:
        if metadata.relationships:
            for rel in metadata.relationships:
                # NOTE: Self-referential relationships are now INCLUDED
                # They will be shown in UI with a warning, but filtered on export

                # Only include if BOTH tables are in our selection
                # This prevents dangling relationships to tables not in the model
                if rel.from_table in selected_tables and rel.to_table in selected_tables:
                    rel_id = rel.relationship_id
                    if rel_id not in seen_ids:
                        # Enrich with cardinality if session provided
                        if session and not rel.cardinality:
                            to_meta = metadata_by_name.get(rel.to_table)
                            if to_meta:
                                try:
                                    rel = enrich_relationship_with_cardinality(
                                        session, rel, metadata, to_meta
                                    )
                                except Exception as e:
                                    logger.warning(f"Cardinality enrichment failed for {rel.from_table}->{rel.to_table}: {e}")
                        all_relationships.append(rel)
                        seen_ids.add(rel_id)

    return all_relationships


def detect_ambiguous_paths(
    relationships: list[RelationshipMetadata],
    user_active_choices: dict[str, str] | None = None,
) -> tuple[list[RelationshipMetadata], list[RelationshipMetadata]]:
    """
    Detect ambiguous paths (diamond patterns) in relationships.

    Power BI requires that when multiple paths exist between two tables,
    all but one path must be marked as inactive.

    Algorithm:
    1. Build a directed graph from relationships
    2. For each table pair, find all paths
    3. If multiple paths exist, keep the shortest path active
       (unless user has made a choice via user_active_choices)

    Args:
        relationships: List of all relationships.
        user_active_choices: Optional dict mapping conflict_pair_id (e.g., "conflict_0")
            to the relationship_id that should be active. If provided, respects
            user's choice instead of defaulting to shortest path.

    Returns:
        Tuple of (active_relationships, inactive_relationships)
    """
    if not relationships:
        return [], []

    # Build adjacency list (graph)
    # from_table -> [(to_table, relationship)]
    from collections import defaultdict

    graph: dict[str, list[tuple[str, RelationshipMetadata]]] = defaultdict(list)
    all_tables: set[str] = set()

    for rel in relationships:
        graph[rel.from_table].append((rel.to_table, rel))
        all_tables.add(rel.from_table)
        all_tables.add(rel.to_table)

    # Depth limits to prevent exponential path exploration in dense graphs
    MAX_PATH_DEPTH = 10
    MAX_PATHS_PER_PAIR = 100

    def find_all_paths(
        start: str,
        end: str,
        visited: set[str] | None = None,
        depth: int = 0
    ) -> list[list[RelationshipMetadata]]:
        """Find all paths from start to end table with depth limits."""
        if visited is None:
            visited = set()

        # Depth limit to prevent exponential exploration
        if depth > MAX_PATH_DEPTH:
            return []

        if start == end:
            return [[]]

        if start in visited:
            return []

        visited = visited | {start}
        paths = []

        for next_table, rel in graph[start]:
            for path in find_all_paths(next_table, end, visited, depth + 1):
                paths.append([rel] + path)
                # Limit total paths to prevent memory issues
                if len(paths) >= MAX_PATHS_PER_PAIR:
                    return paths

        return paths

    # Find tables that are targets of multiple relationships (potential diamond centers)
    target_counts: dict[str, int] = defaultdict(int)
    for rel in relationships:
        target_counts[rel.to_table] += 1

    # Tables referenced by more than one relationship are potential diamond centers
    diamond_centers = {t for t, count in target_counts.items() if count > 1}

    # For each pair of tables, check if multiple paths exist
    relationships_to_deactivate: set[str] = set()

    for center in diamond_centers:
        # Find all tables that have a path to this center
        tables_with_paths: dict[str, list[list[RelationshipMetadata]]] = {}

        for table in all_tables:
            if table != center:
                paths = find_all_paths(table, center)
                if paths:
                    tables_with_paths[table] = paths

        # For any table with multiple paths to center, deactivate all but shortest
        for table, paths in tables_with_paths.items():
            if len(paths) > 1:
                # Sort by path length, keep shortest active
                paths_sorted = sorted(paths, key=len)

                # Deactivate all relationships in non-shortest paths
                shortest_path_rels = {r.relationship_id for r in paths_sorted[0]}

                for path in paths_sorted[1:]:
                    for rel in path:
                        # Only deactivate if this relationship isn't in shortest path
                        if rel.relationship_id not in shortest_path_rels:
                            relationships_to_deactivate.add(rel.relationship_id)

    # Handle multiple relationships pointing to the same target table
    # Power BI only allows one active relationship to a target table
    # Mark all but one as inactive, respecting user choices
    #
    # User choice format: user_active_choices maps "conflict_{index}" to active_rel_id
    conflict_pair_index = 0
    for center in diamond_centers:
        # Get all relationships that directly reference this center
        direct_refs = [rel for rel in relationships if rel.to_table == center]

        if len(direct_refs) > 1:
            # Multiple relationships point to this center
            # First relationship is "default active", others are "default inactive"
            primary_rel = direct_refs[0]

            for secondary_rel in direct_refs[1:]:
                # Check if user has made a choice for this conflict pair
                conflict_pair_key = f"conflict_{conflict_pair_index}"
                user_choice = None
                if user_active_choices:
                    user_choice = user_active_choices.get(conflict_pair_key)

                if user_choice:
                    # User has chosen which relationship should be active
                    # Deactivate the one they didn't choose
                    if user_choice == primary_rel.relationship_id:
                        relationships_to_deactivate.add(secondary_rel.relationship_id)
                    elif user_choice == secondary_rel.relationship_id:
                        relationships_to_deactivate.add(primary_rel.relationship_id)
                    else:
                        # Invalid choice - fall back to default
                        relationships_to_deactivate.add(secondary_rel.relationship_id)
                else:
                    # No user choice - default: keep first active, deactivate others
                    relationships_to_deactivate.add(secondary_rel.relationship_id)

                conflict_pair_index += 1

    # Split into active and inactive
    active = []
    inactive = []

    for rel in relationships:
        if rel.relationship_id in relationships_to_deactivate:
            inactive.append(rel)
        else:
            active.append(rel)

    return active, inactive


def detect_conflict_pairs(
    relationships: list[RelationshipMetadata]
) -> list[tuple[RelationshipMetadata, RelationshipMetadata, str]]:
    """
    Detect pairs of relationships that conflict (only one can be active).

    Uses the same graph traversal as detect_ambiguous_paths() to find
    diamond patterns where multiple paths lead to the same center table.

    Args:
        relationships: List of all relationships.

    Returns:
        List of tuples: (active_rel, inactive_rel, center_table_name)
        where active_rel and inactive_rel form a conflict pair and only one
        can be active. active_rel is the "default active" (from shorter path).
    """
    if not relationships:
        return []

    from collections import defaultdict

    # Build adjacency list (graph) - same as detect_ambiguous_paths
    graph: dict[str, list[tuple[str, RelationshipMetadata]]] = defaultdict(list)
    all_tables: set[str] = set()

    for rel in relationships:
        graph[rel.from_table].append((rel.to_table, rel))
        all_tables.add(rel.from_table)
        all_tables.add(rel.to_table)

    # Depth limits to prevent exponential path exploration in dense graphs
    MAX_PATH_DEPTH = 10
    MAX_PATHS_PER_PAIR = 100

    def find_all_paths(
        start: str,
        end: str,
        visited: set[str] | None = None,
        depth: int = 0
    ) -> list[list[RelationshipMetadata]]:
        """Find all paths from start to end table with depth limits."""
        if visited is None:
            visited = set()

        # Depth limit to prevent exponential exploration
        if depth > MAX_PATH_DEPTH:
            return []

        if start == end:
            return [[]]

        if start in visited:
            return []

        visited = visited | {start}
        paths = []

        for next_table, rel in graph[start]:
            for path in find_all_paths(next_table, end, visited, depth + 1):
                paths.append([rel] + path)
                # Limit total paths to prevent memory issues
                if len(paths) >= MAX_PATHS_PER_PAIR:
                    return paths

        return paths

    # Find tables that are targets of multiple relationships (potential diamond centers)
    target_counts: dict[str, int] = defaultdict(int)
    for rel in relationships:
        target_counts[rel.to_table] += 1

    # Tables referenced by more than one relationship are potential diamond centers
    diamond_centers = {t for t, count in target_counts.items() if count > 1}

    conflict_pairs: list[tuple[RelationshipMetadata, RelationshipMetadata, str]] = []
    seen_pairs: set[tuple[str, str]] = set()  # Avoid duplicate pairs

    # Method 1: Find conflicts from diamond patterns (multiple paths to same center)
    for center in diamond_centers:
        # Find all tables that have multiple paths to this center
        for table in all_tables:
            if table != center:
                paths = find_all_paths(table, center)
                if len(paths) > 1:
                    # Multiple paths from this table to the center
                    # Sort by path length, shortest path is "active"
                    paths_sorted = sorted(paths, key=len)
                    active_path = paths_sorted[0]

                    # Get the first relationship in the active path
                    if active_path:
                        active_rel = active_path[0]

                        # For each alternate path, pair its first relationship
                        for inactive_path in paths_sorted[1:]:
                            if inactive_path:
                                inactive_rel = inactive_path[0]

                                # Create pair if not already seen
                                pair_key = tuple(sorted([active_rel.relationship_id, inactive_rel.relationship_id]))
                                if pair_key not in seen_pairs:
                                    seen_pairs.add(pair_key)
                                    conflict_pairs.append((active_rel, inactive_rel, center))

    # Method 2: Direct multiple relationships to the same table
    rels_by_target: dict[str, list[RelationshipMetadata]] = defaultdict(list)
    for rel in relationships:
        rels_by_target[rel.to_table].append(rel)

    for center_table, incoming_rels in rels_by_target.items():
        if len(incoming_rels) >= 2:
            # Multiple relationships point directly to this table
            primary_rel = incoming_rels[0]
            for secondary_rel in incoming_rels[1:]:
                pair_key = tuple(sorted([primary_rel.relationship_id, secondary_rel.relationship_id]))
                if pair_key not in seen_pairs:
                    seen_pairs.add(pair_key)
                    conflict_pairs.append((primary_rel, secondary_rel, center_table))

    return conflict_pairs


def detect_role_playing_dimensions(
    relationships: list[RelationshipMetadata]
) -> dict[str, list[str]]:
    """
    Detect dimension tables that are referenced by multiple fact/lookup tables.

    Role-playing dimensions (like NATION used by both CUSTOMER and SUPPLIER)
    should be duplicated with role prefixes to avoid ambiguous paths.

    Args:
        relationships: List of all relationships.

    Returns:
        Dict mapping dimension table name to list of referencing tables.
        Example: {"NATION": ["CUSTOMER", "SUPPLIER"]}
    """
    from collections import defaultdict

    # Count references to each "to_table" (dimension side)
    dimension_refs: dict[str, list[str]] = defaultdict(list)

    for rel in relationships:
        # The "to_table" is the dimension (PK side)
        dimension_refs[rel.to_table].append(rel.from_table)

    # Only return dimensions with multiple references (role-playing)
    return {dim: refs for dim, refs in dimension_refs.items() if len(refs) > 1}


def create_role_playing_table(
    original_metadata: SemanticViewMetadata,
    role_prefix: str,
    original_table_name: str
) -> tuple[SemanticViewMetadata, str]:
    """
    Create a copy of a dimension table with role-prefixed name.

    Example: NATION with role_prefix="CUSTOMER" becomes "CUSTOMER_NATION"

    Args:
        original_metadata: The original dimension table metadata.
        role_prefix: The name of the table that references this dimension.
        original_table_name: The original Snowflake table name (for M expression).

    Returns:
        Tuple of (new_metadata, original_table_name) for tracking source mapping.
    """
    new_name = f"{role_prefix}_{original_metadata.view}"

    # Create new TableMetadata with updated comment
    new_table_metadata = None
    if original_metadata.table_metadata:
        original_comment = original_metadata.table_metadata.comment or ""
        new_table_metadata = TableMetadata(
            comment=f"{role_prefix}'s {original_metadata.view}" +
                    (f" - {original_comment}" if original_comment else ""),
            row_count=original_metadata.table_metadata.row_count
        )

    new_metadata = SemanticViewMetadata(
        database=original_metadata.database,
        schema=original_metadata.schema,
        view=new_name,  # Prefixed name
        columns=original_metadata.columns,  # Same columns
        object_type=original_metadata.object_type,
        table_metadata=new_table_metadata,
        constraints=original_metadata.constraints,
        relationships=[]  # Relationships will be rewritten separately
    )

    return new_metadata, original_table_name


def generate_pbi_relationships(
    relationships: list[RelationshipMetadata],
    inactive_relationships: list[RelationshipMetadata] | None = None
) -> list[dict[str, Any]]:
    """
    Generate PBI relationship definitions from RelationshipMetadata.

    Supports Many-to-Many (*:*) relationships for tables with composite PKs.
    M:M relationships use bidirectional cross-filtering per Microsoft best practices.

    Args:
        relationships: List of relationship metadata (all relationships).
        inactive_relationships: List of relationships that should be marked inactive.
            Used for resolving ambiguous paths (diamond patterns).

    Returns:
        List of PBI relationship dictionaries.
    """
    inactive_ids = set()
    if inactive_relationships:
        inactive_ids = {r.relationship_id for r in inactive_relationships}

    pbi_relationships = []

    for rel in relationships:
        # Skip self-referential relationships - Power BI doesn't support tables
        # having relationships to themselves (e.g., Employee -> Manager)
        if rel.from_table == rel.to_table:
            continue

        # Generate unique name for the relationship
        rel_name = rel.name or f"{rel.from_table}_{rel.from_column}_{rel.to_table}"

        pbi_rel = {
            "name": rel_name,
            "fromTable": rel.from_table,
            "fromColumn": rel.from_column,
            "toTable": rel.to_table,
            "toColumn": rel.to_column,
            "crossFilteringBehavior": "oneDirection"  # Safe default
        }

        # Handle Many-to-Many (*:*) cardinality for composite PK tables
        # Per Microsoft M:M guidance: https://learn.microsoft.com/en-us/power-bi/guidance/relationships-many-to-many
        if rel.cardinality and rel.cardinality.to_cardinality == "many":
            pbi_rel["fromCardinality"] = "many"
            pbi_rel["toCardinality"] = "many"
            pbi_rel["crossFilteringBehavior"] = "bothDirections"

        # Explicitly set isActive for ALL relationships
        # Power BI may default to inactive if not specified
        if rel.relationship_id in inactive_ids:
            pbi_rel["isActive"] = False
        else:
            pbi_rel["isActive"] = True  # Explicitly mark as active

        pbi_relationships.append(pbi_rel)

    return pbi_relationships


def _generate_m_expression(
    metadata: SemanticViewMetadata,
    server: str,
    warehouse: str
) -> list[str]:
    """
    Generate M expression lines for a table partition (custom connector).

    Args:
        metadata: View metadata.
        server: Snowflake server URL.
        warehouse: Snowflake warehouse name.

    Returns:
        List of M expression lines.
    """
    database = escape_m_string(metadata.database)
    schema = escape_m_string(metadata.schema)
    view_name = escape_m_string(metadata.view)

    # Escape variable names for M (may contain spaces/special chars)
    db_var = escape_m_identifier(f"{database}_DB")
    schema_var = escape_m_identifier(f"{schema}_Schema")
    view_var = escape_m_identifier(f"{view_name}1")

    return [
        "let",
        f'    Source = SnowflakeSemanticViews.Contents("{escape_m_string(server)}", "{escape_m_string(warehouse)}", null, null, null, null, null),',
        f'    {db_var} = Source{{[name="{database}"]}}[Data],',
        f'    {schema_var} = {db_var}{{[name="{schema}"]}}[Data],',
        f'    {view_var} = {schema_var}{{[name="{view_name}"]}}[Data]',
        "in",
        f"    {view_var}"
    ]


def _generate_native_m_expression(
    metadata: SemanticViewMetadata,
    server: str,
    warehouse: str,
    source_name: str = "SnowflakeNativeSource"
) -> list[str]:
    """
    Generate M expression lines for a table using native Snowflake connector.

    Uses Snowflake.Databases() for standard tables (not semantic views).

    Args:
        metadata: View metadata.
        server: Snowflake server URL.
        warehouse: Snowflake warehouse name.
        source_name: Name of the shared expression to reference.

    Returns:
        List of M expression lines.
    """
    database = escape_m_string(metadata.database)
    schema = escape_m_string(metadata.schema)
    table_name = escape_m_string(metadata.view)

    # Escape variable names for M (may contain spaces/special chars)
    db_var = escape_m_identifier(f"{database}_Database")
    schema_var = escape_m_identifier(f"{schema}_Schema")
    table_var = escape_m_identifier(f"{table_name}_Table")

    return [
        "let",
        f'    Source = #"{source_name}",',
        f'    {db_var} = Source{{[Name="{database}", Kind="Database"]}}[Data],',
        f'    {schema_var} = {db_var}{{[Name="{schema}", Kind="Schema"]}}[Data],',
        f'    {table_var} = {schema_var}{{[Name="{table_name}", Kind="Table"]}}[Data]',
        "in",
        f"    {table_var}"
    ]


def generate_dual_source_expressions(
    server: str,
    warehouse: str,
    has_semantic_views: bool,
    has_standard_tables: bool
) -> list[dict[str, Any]]:
    """
    Generate shared expression definitions for both connectors.

    Creates source expressions for:
    - SnowflakeSemanticViewsSource: Custom connector for semantic views
    - SnowflakeNativeSource: Native Snowflake connector for standard tables

    Args:
        server: Snowflake server URL.
        warehouse: Snowflake warehouse name.
        has_semantic_views: Whether semantic views are included.
        has_standard_tables: Whether standard tables/views are included.

    Returns:
        List of expression definition dictionaries.
    """
    expressions = []

    if has_semantic_views:
        expressions.append({
            "name": "SnowflakeSemanticViewsSource",
            "kind": "m",
            "expression": f'SnowflakeSemanticViews.Contents("{escape_m_string(server)}", "{escape_m_string(warehouse)}", null, null, null, null, null)',
            "annotations": [
                {
                    "name": "PBI_NavigationStepName",
                    "value": "Navigation"
                },
                {
                    "name": "PBI_ResultType",
                    "value": "Table"
                }
            ]
        })

    if has_standard_tables:
        expressions.append({
            "name": "SnowflakeNativeSource",
            "kind": "m",
            "expression": f'Snowflake.Databases("{escape_m_string(server)}", "{escape_m_string(warehouse)}")',
            "annotations": [
                {
                    "name": "PBI_NavigationStepName",
                    "value": "Navigation"
                },
                {
                    "name": "PBI_ResultType",
                    "value": "Table"
                }
            ]
        })

    return expressions


def _generate_empty_table_expression(metadata: SemanticViewMetadata) -> list[str]:
    """
    Generate M expression for an empty typed table (for ImageSave).

    This creates an M expression that returns an empty table with the correct
    column schema, allowing ImageSave to work without data source validation.

    Args:
        metadata: View metadata with column definitions.

    Returns:
        List of M expression lines.
    """
    # Build column type list: {{"ColName", type text}, {"ColNum", type number}}
    # Deduplicate columns to prevent M errors
    seen_columns = set()
    unique_columns = []
    dropped_columns = []
    for col in metadata.columns:
        if col.name in seen_columns:
            dropped_columns.append(col.name)
            continue
        seen_columns.add(col.name)
        unique_columns.append(col)

    if dropped_columns:
        logger.warning(
            f"Duplicate columns dropped from {metadata.view}: {dropped_columns}. "
            "This may indicate data modeling issues in the source."
        )

    col_types = []
    for col in unique_columns:
        pbi_type = snowflake_to_pbi_type(col.data_type)
        # Map PBI types to M types
        m_type_map = {
            "string": "text",
            "int64": "number",
            "double": "number",
            "decimal": "number",
            "boolean": "logical",
            "dateTime": "datetime",
            "date": "date",
            "time": "time",
            "binary": "binary",
        }
        m_type = m_type_map.get(pbi_type, "any")
        col_types.append(f'{{"{col.name}", type {m_type}}}')

    col_types_str = ", ".join(col_types)

    return [
        "let",
        f"    Source = #table(type table [{', '.join(f'[{c.name}]' for c in unique_columns)}], {{}})",
        "in",
        "    Source"
    ]


def _generate_table_definition(
    metadata: SemanticViewMetadata,
    server: str,
    warehouse: str
) -> dict[str, Any]:
    """
    Generate table definition for DataModelSchema.

    Args:
        metadata: View metadata.
        server: Snowflake server URL.
        warehouse: Snowflake warehouse name.

    Returns:
        Table definition dictionary.
    """
    view_name = metadata.view
    lineage_tag = generate_lineage_tag()
    m_expression = _generate_m_expression(metadata, server, warehouse)

    # Build columns
    # Power BI only allows ONE column per table with isKey=True
    # For composite PKs, we only mark the first PK column
    # Also track seen column names to prevent duplicates (BIM deserialization error)
    key_already_set = False
    seen_columns = set()
    dropped_columns = []
    columns = []
    for col in metadata.columns:
        # Skip duplicate column names (can occur if same column appears in multiple semantic kinds)
        if col.name in seen_columns:
            dropped_columns.append(col.name)
            continue
        seen_columns.add(col.name)

        pbi_type = snowflake_to_pbi_type(col.data_type)
        col_lineage = generate_lineage_tag()

        # For METRIC columns, use "double" with sourceProviderType and SummarizationSetBy annotation
        # This ensures Power BI preserves the summarizeBy setting when opening the PBIT file
        is_metric = col.kind == "METRIC"
        if is_metric and pbi_type == "decimal":
            pbi_type = "double"

        column_def = {
            "name": col.name,
            "dataType": pbi_type,
            "sourceColumn": col.source_column or col.name,  # Use original name for DirectQuery
            "lineageTag": col_lineage
        }

        # For METRIC columns, add sourceProviderType to indicate underlying Snowflake type
        if is_metric:
            column_def["sourceProviderType"] = "decimal"

        # Add column description if available
        if col.description:
            column_def["description"] = col.description

        # Mark primary key columns (only first one for composite PKs)
        if col.is_primary_key and not key_already_set:
            column_def["isKey"] = True
            key_already_set = True

        # Add summarization for numeric types (including decimal for Snowflake NUMBER types)
        if pbi_type in ("double", "int64", "decimal"):
            column_def["summarizeBy"] = "sum"
        else:
            column_def["summarizeBy"] = "none"

        # For METRIC columns, add annotations to preserve summarization settings
        if is_metric:
            column_def["annotations"] = [
                {"name": "SummarizationSetBy", "value": "User"},
                {"name": "PBI_FormatHint", "value": "{\"isGeneralNumber\":true}"}
            ]

        # Power BI-specific column properties (typically set via column_overrides)
        if col.is_hidden:
            column_def["isHidden"] = True
        if col.data_category:
            column_def["dataCategory"] = col.data_category
        if col.format_string:
            column_def["formatString"] = col.format_string

        columns.append(column_def)

    # Warn if columns were dropped due to duplicates
    if dropped_columns:
        logger.warning(
            f"Duplicate columns dropped from {metadata.view}: {dropped_columns}. "
            "This may indicate data modeling issues in the source."
        )

    table = {
        "name": view_name,
        "lineageTag": lineage_tag,
        "columns": columns,
        "partitions": [
            {
                "name": view_name,
                "mode": "directQuery",
                "source": {
                    "type": "m",
                    "expression": m_expression
                }
            }
        ],
        "annotations": [
            {
                "name": "PBI_ResultType",
                "value": "Table"
            }
        ]
    }

    # Add table description if available
    if metadata.table_metadata and metadata.table_metadata.comment:
        table["description"] = metadata.table_metadata.comment

    return table


def generate_data_model_schema(
    views_metadata: list[SemanticViewMetadata],
    server: str,
    warehouse: str,
    model_name: str = "SemanticModel"
) -> str:
    """
    Generate DataModelSchema JSON (equivalent to model.bim).

    Args:
        views_metadata: List of view metadata objects.
        server: Snowflake server URL.
        warehouse: Snowflake warehouse name.
        model_name: Name for the model.

    Returns:
        JSON string with complete data model schema.
    """
    # Generate tables
    tables = [
        _generate_table_definition(metadata, server, warehouse)
        for metadata in views_metadata
    ]

    # Build full schema
    now = datetime.utcnow().isoformat(timespec='milliseconds')
    schema = {
        "name": str(uuid.uuid4()),
        "compatibilityLevel": 1567,
        "createdTimestamp": now,
        "lastUpdate": now,
        "lastSchemaUpdate": now,
        "model": {
            "culture": "en-US",
            "dataAccessOptions": {
                "legacyRedirects": True,
                "returnErrorValuesAsNull": True
            },
            "defaultPowerBIDataSourceVersion": "powerBI_V3",
            "sourceQueryCulture": "en-US",
            "tables": tables,
            "annotations": [
                {
                    "name": "__PBI_TimeIntelligenceEnabled",
                    "value": "0"
                },
                {
                    "name": "PBIDesktopVersion",
                    "value": "2.149.178.0"
                },
                {
                    "name": "PBI_QueryOrder",
                    "value": json.dumps([m.view for m in views_metadata])
                },
                {
                    "name": "PBI_ProTooling",
                    "value": "[\"DevMode\"]"
                }
            ]
        }
    }

    return json.dumps(schema, indent=2)


def create_pbit_file(
    views_metadata: list[SemanticViewMetadata],
    server: str,
    warehouse: str,
    project_name: str,
    page_name: str = "Page 1",
    description: str = "",
    selected_relationships: list[RelationshipMetadata] | None = None,
    duplicate_role_playing_dims: dict[str, bool] | None = None,
    mode: str = "directQuery",
    user_active_choices: dict[str, str] | None = None,
) -> bytes:
    """
    Create a complete PBIT file.

    Args:
        views_metadata: List of view metadata objects.
        server: Snowflake server URL.
        warehouse: Snowflake warehouse name.
        project_name: Name for the project.
        page_name: Display name for the report page.
        description: Optional file description.
        selected_relationships: Optional list of user-selected relationships.
            If None, all relationships are auto-collected from metadata.
        duplicate_role_playing_dims: Optional dict mapping dimension names to
            whether they should be duplicated. If None, all role-playing
            dimensions are duplicated by default.
        user_active_choices: Optional dict mapping conflict_pair_key to the
            relationship_id that should be active.

    Returns:
        PBIT file as bytes.
    """
    # Calculate actual table names for DiagramLayout
    # (taking role-playing dimension duplication into account)
    if selected_relationships is not None:
        all_relationships = selected_relationships
    else:
        all_relationships = collect_all_relationships(views_metadata)

    role_playing_dims = detect_role_playing_dimensions(all_relationships)
    if duplicate_role_playing_dims is not None:
        role_playing_dims = {
            dim: refs for dim, refs in role_playing_dims.items()
            if duplicate_role_playing_dims.get(dim, True)
        }

    # Build table name list (original tables + duplicated role-playing dims)
    table_names = []
    for metadata in views_metadata:
        if metadata.view in role_playing_dims:
            # Skip original, add duplicated copies
            continue
        table_names.append(metadata.view)

    # Add duplicated dimension names
    for dim_name, referencing_tables in role_playing_dims.items():
        for ref_table in referencing_tables:
            table_names.append(f"{ref_table}_{dim_name}")

    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Version (UTF-16-LE)
        zf.writestr("Version", generate_version().encode('utf-16-le'))

        # [Content_Types].xml (UTF-8)
        zf.writestr("[Content_Types].xml", generate_content_types_xml().encode('utf-8'))

        # DataModelSchema (UTF-16-LE) - use DirectQuery schema with expressions section
        schema = generate_data_model_schema_directquery(
            views_metadata, server, warehouse, project_name,
            selected_relationships=selected_relationships,
            duplicate_role_playing_dims=duplicate_role_playing_dims,
            mode=mode,
            user_active_choices=user_active_choices,
        )
        zf.writestr("DataModelSchema", schema.encode('utf-16-le'))

        # Report/Layout (UTF-16-LE)
        layout = generate_report_layout(page_name)
        zf.writestr("Report/Layout", layout.encode('utf-16-le'))

        # Theme file (UTF-8) - required for report to load properly
        theme_content = load_theme_file()
        zf.writestr("Report/StaticResources/SharedResources/BaseThemes/CY25SU11.json", theme_content)

        # Settings (UTF-16-LE)
        zf.writestr("Settings", generate_settings().encode('utf-16-le'))

        # Metadata (UTF-16-LE)
        zf.writestr("Metadata", generate_metadata(description).encode('utf-16-le'))

        # DiagramLayout (UTF-16-LE) - relationship-based clustering layout
        diagram_layout = generate_diagram_layout(
            table_names,
            relationships=all_relationships,
            role_playing_dims=role_playing_dims,
        )
        zf.writestr("DiagramLayout", diagram_layout.encode('utf-16-le'))

        # SecurityBindings - empty/minimal (can be omitted, but include for compatibility)
        # This is a binary blob that Power BI uses for security. An empty file works.
        zf.writestr("SecurityBindings", b'')

    buffer.seek(0)
    return buffer.getvalue()


def create_single_view_pbit(
    metadata: SemanticViewMetadata,
    server: str,
    warehouse: str
) -> bytes:
    """
    Create a PBIT file for a single view.

    Args:
        metadata: View metadata.
        server: Snowflake server URL.
        warehouse: Snowflake warehouse name.

    Returns:
        PBIT file as bytes.
    """
    return create_pbit_file(
        [metadata],
        server,
        warehouse,
        metadata.view
    )


def _generate_table_definition_for_imagesave(
    metadata: SemanticViewMetadata,
    server: str,
    warehouse: str
) -> dict[str, Any]:
    """
    Generate table definition for ImageSave (Import mode with empty table).

    Unlike DirectQuery mode, this creates an Import mode partition with an
    empty table schema. This allows ImageSave to generate a valid ABF file.
    The M expression still references the connector so Power BI will prompt
    for connection when opened.

    Args:
        metadata: View metadata.
        server: Snowflake server URL.
        warehouse: Snowflake warehouse name.

    Returns:
        Table definition dictionary.
    """
    view_name = metadata.view
    lineage_tag = generate_lineage_tag()
    m_expression = _generate_m_expression(metadata, server, warehouse)

    # Build columns
    # Power BI only allows ONE column per table with isKey=True
    # For composite PKs, we only mark the first PK column
    # Also track seen column names to prevent duplicates (BIM deserialization error)
    key_already_set = False
    seen_columns = set()
    dropped_columns = []
    columns = []
    for col in metadata.columns:
        # Skip duplicate column names (can occur if same column appears in multiple semantic kinds)
        if col.name in seen_columns:
            dropped_columns.append(col.name)
            continue
        seen_columns.add(col.name)

        pbi_type = snowflake_to_pbi_type(col.data_type)
        col_lineage = generate_lineage_tag()

        # For METRIC columns, use "double" with sourceProviderType and SummarizationSetBy annotation
        # This ensures Power BI preserves the summarizeBy setting when opening the PBIT file
        is_metric = col.kind == "METRIC"
        if is_metric and pbi_type == "decimal":
            pbi_type = "double"

        column_def = {
            "name": col.name,
            "dataType": pbi_type,
            "sourceColumn": col.source_column or col.name,  # Use original name for DirectQuery
            "lineageTag": col_lineage
        }

        # For METRIC columns, add sourceProviderType to indicate underlying Snowflake type
        if is_metric:
            column_def["sourceProviderType"] = "decimal"

        # Add column description if available
        if col.description:
            column_def["description"] = col.description

        # Mark primary key columns (only first one for composite PKs)
        if col.is_primary_key and not key_already_set:
            column_def["isKey"] = True
            key_already_set = True

        # Add summarization for numeric types (including decimal for Snowflake NUMBER types)
        if pbi_type in ("double", "int64", "decimal"):
            column_def["summarizeBy"] = "sum"
        else:
            column_def["summarizeBy"] = "none"

        # For METRIC columns, add annotations to preserve summarization settings
        if is_metric:
            column_def["annotations"] = [
                {"name": "SummarizationSetBy", "value": "User"},
                {"name": "PBI_FormatHint", "value": "{\"isGeneralNumber\":true}"}
            ]

        # Power BI-specific column properties (typically set via column_overrides)
        if col.is_hidden:
            column_def["isHidden"] = True
        if col.data_category:
            column_def["dataCategory"] = col.data_category
        if col.format_string:
            column_def["formatString"] = col.format_string

        columns.append(column_def)

    # Warn if columns were dropped due to duplicates
    if dropped_columns:
        logger.warning(
            f"Duplicate columns dropped from {metadata.view}: {dropped_columns}. "
            "This may indicate data modeling issues in the source."
        )

    # Use Import mode for ImageSave compatibility
    table = {
        "name": view_name,
        "lineageTag": lineage_tag,
        "columns": columns,
        "partitions": [
            {
                "name": view_name,
                "mode": "import",
                "source": {
                    "type": "m",
                    "expression": m_expression
                }
            }
        ],
        "annotations": [
            {
                "name": "PBI_ResultType",
                "value": "Table"
            }
        ]
    }

    # Add table description if available
    if metadata.table_metadata and metadata.table_metadata.comment:
        table["description"] = metadata.table_metadata.comment

    return table


def _generate_table_definition_directquery(
    metadata: SemanticViewMetadata,
    server: str,
    warehouse: str,
    source_table_name: str | None = None,
    use_native: bool = False,
    mode: str = "directQuery"
) -> dict[str, Any]:
    """
    Generate table definition for DirectQuery mode.

    Uses a shared expression reference for the data source, which allows
    DirectQuery to work with TOM validation.

    Args:
        metadata: View metadata.
        server: Snowflake server URL.
        warehouse: Snowflake warehouse name.
        source_table_name: If provided, use this as the Snowflake source table name
            in the M expression. Used for role-playing dimension copies that reference
            the original table (e.g., "CUSTOMER_NATION" table references "NATION" source).
        use_native: If True, use native Snowflake connector (Snowflake.Databases).
            If False (default), use custom semantic views connector.
    """
    view_name = metadata.view  # Power BI table name (may be prefixed)
    source_name = source_table_name or metadata.view  # Snowflake source table name
    lineage_tag = generate_lineage_tag()

    # Build columns
    # Power BI only allows ONE column per table with isKey=True
    # For composite PKs, we only mark the first PK column
    # Also track seen column names to prevent duplicates (BIM deserialization error)
    key_already_set = False
    seen_columns = set()
    dropped_columns = []
    columns = []
    for col in metadata.columns:
        # Skip duplicate column names (can occur if same column appears in multiple semantic kinds)
        if col.name in seen_columns:
            dropped_columns.append(col.name)
            continue
        seen_columns.add(col.name)

        pbi_type = snowflake_to_pbi_type(col.data_type)
        col_lineage = generate_lineage_tag()

        # For METRIC columns, use "double" with sourceProviderType and SummarizationSetBy annotation
        # This ensures Power BI preserves the summarizeBy setting when opening the PBIT file
        is_metric = col.kind == "METRIC"
        if is_metric and pbi_type == "decimal":
            pbi_type = "double"

        column_def = {
            "name": col.name,
            "dataType": pbi_type,
            "sourceColumn": col.source_column or col.name,  # Use original name for DirectQuery
            "lineageTag": col_lineage
        }

        # For METRIC columns, add sourceProviderType to indicate underlying Snowflake type
        if is_metric:
            column_def["sourceProviderType"] = "decimal"

        # Add column description if available
        if col.description:
            column_def["description"] = col.description

        # Mark primary key columns (only first one for composite PKs)
        if col.is_primary_key and not key_already_set:
            column_def["isKey"] = True
            key_already_set = True

        # Add summarization for numeric types (including decimal for Snowflake NUMBER types)
        if pbi_type in ("double", "int64", "decimal"):
            column_def["summarizeBy"] = "sum"
        else:
            column_def["summarizeBy"] = "none"

        # For METRIC columns, add annotations to preserve summarization settings
        if is_metric:
            column_def["annotations"] = [
                {"name": "SummarizationSetBy", "value": "User"},
                {"name": "PBI_FormatHint", "value": "{\"isGeneralNumber\":true}"}
            ]

        # Power BI-specific column properties (typically set via column_overrides)
        if col.is_hidden:
            column_def["isHidden"] = True
        if col.data_category:
            column_def["dataCategory"] = col.data_category
        if col.format_string:
            column_def["formatString"] = col.format_string

        columns.append(column_def)

    # Warn if columns were dropped due to duplicates
    if dropped_columns:
        logger.warning(
            f"Duplicate columns dropped from {metadata.view}: {dropped_columns}. "
            "This may indicate data modeling issues in the source."
        )

    database = escape_m_string(metadata.database)
    schema = escape_m_string(metadata.schema)
    source_name_escaped = escape_m_string(source_name)

    # DirectQuery partition with expression referencing shared Source
    # NOTE: M expression references the ORIGINAL source table (for role-playing dims)
    # Escape variable names for M (may contain spaces/special chars)
    db_var_native = escape_m_identifier(f"{database}_Database")
    db_var_custom = escape_m_identifier(f"{database}_DB")
    schema_var = escape_m_identifier(f"{schema}_Schema")
    table_var = escape_m_identifier(f"{source_name_escaped}_Table")
    view_var = escape_m_identifier(f"{source_name_escaped}1")

    if use_native:
        # Native Snowflake connector: Snowflake.Databases()
        # Uses Kind="Database", Kind="Schema", Kind="Table" navigation
        m_expression = [
            "let",
            f'    Source = #"SnowflakeNativeSource",',
            f'    {db_var_native} = Source{{[Name="{database}", Kind="Database"]}}[Data],',
            f'    {schema_var} = {db_var_native}{{[Name="{schema}", Kind="Schema"]}}[Data],',
            f'    {table_var} = {schema_var}{{[Name="{source_name_escaped}", Kind="Table"]}}[Data]',
            "in",
            f"    {table_var}"
        ]
    else:
        # Custom semantic views connector: SnowflakeSemanticViews.Contents()
        # Uses name="{name}" navigation
        m_expression = [
            "let",
            f'    Source = #"SnowflakeSemanticViewsSource",',
            f'    {db_var_custom} = Source{{[name="{database}"]}}[Data],',
            f'    {schema_var} = {db_var_custom}{{[name="{schema}"]}}[Data],',
            f'    {view_var} = {schema_var}{{[name="{source_name_escaped}"]}}[Data]',
            "in",
            f"    {view_var}"
        ]

    table = {
        "name": view_name,
        "lineageTag": lineage_tag,
        "columns": columns,
        "partitions": [
            {
                "name": view_name,
                "mode": mode,
                "source": {
                    "type": "m",
                    "expression": m_expression
                }
            }
        ],
        "annotations": [
            {
                "name": "PBI_ResultType",
                "value": "Table"
            }
        ]
    }

    # Add table description if available
    if metadata.table_metadata and metadata.table_metadata.comment:
        table["description"] = metadata.table_metadata.comment

    return table


def generate_data_model_schema_for_imagesave(
    views_metadata: list[SemanticViewMetadata],
    server: str,
    warehouse: str,
    model_name: str = "SemanticModel"
) -> str:
    """
    Generate DataModelSchema JSON for ImageSave (Import mode).

    This generates a model suitable for ImageSave, using Import mode
    partitions instead of DirectQuery. The resulting model can be loaded
    by msmdsrv.exe and exported via ImageSave.

    Args:
        views_metadata: List of view metadata objects.
        server: Snowflake server URL.
        warehouse: Snowflake warehouse name.
        model_name: Name for the model.

    Returns:
        JSON string with complete data model schema.
    """
    # Generate tables with Import mode
    tables = [
        _generate_table_definition_for_imagesave(metadata, server, warehouse)
        for metadata in views_metadata
    ]

    # Build full schema
    now = datetime.utcnow().isoformat(timespec='milliseconds')
    schema = {
        "name": str(uuid.uuid4()),
        "compatibilityLevel": 1567,
        "createdTimestamp": now,
        "lastUpdate": now,
        "lastSchemaUpdate": now,
        "model": {
            "culture": "en-US",
            "dataAccessOptions": {
                "legacyRedirects": True,
                "returnErrorValuesAsNull": True
            },
            "defaultPowerBIDataSourceVersion": "powerBI_V3",
            "sourceQueryCulture": "en-US",
            "tables": tables,
            "annotations": [
                {
                    "name": "__PBI_TimeIntelligenceEnabled",
                    "value": "0"
                },
                {
                    "name": "PBIDesktopVersion",
                    "value": "2.149.178.0"
                },
                {
                    "name": "PBI_QueryOrder",
                    "value": json.dumps([m.view for m in views_metadata])
                },
                {
                    "name": "PBI_ProTooling",
                    "value": "[\"DevMode\"]"
                }
            ]
        }
    }

    return json.dumps(schema, indent=2)


def generate_data_model_schema_directquery(
    views_metadata: list[SemanticViewMetadata],
    server: str,
    warehouse: str,
    model_name: str = "SemanticModel",
    selected_relationships: list[RelationshipMetadata] | None = None,
    duplicate_role_playing_dims: dict[str, bool] | None = None,
    mode: str = "directQuery",
    user_active_choices: dict[str, str] | None = None,
) -> str:
    """
    Generate DataModelSchema JSON for DirectQuery mode.

    This generates a model with DirectQuery partitions that reference
    a shared expression for the data source connection.

    Handles role-playing dimensions by duplicating dimension tables with
    role prefixes (e.g., NATION becomes CUSTOMER_NATION and SUPPLIER_NATION)
    so all relationships can be active.

    Args:
        views_metadata: List of view metadata objects.
        server: Snowflake server URL.
        warehouse: Snowflake warehouse name.
        model_name: Name for the model.
        selected_relationships: Optional list of user-selected relationships.
            If None, all relationships are auto-collected from metadata.
        duplicate_role_playing_dims: Optional dict mapping dimension names to
            whether they should be duplicated. If None, all role-playing
            dimensions are duplicated by default.
        mode: Partition mode - "directQuery" or "import".
        user_active_choices: Optional dict mapping conflict_pair_key to the
            relationship_id that should be active. Used to respect user's
            choice when multiple paths exist to the same table.

    Returns:
        JSON string with complete data model schema.
    """
    # Use selected relationships if provided, otherwise collect all from metadata
    if selected_relationships is not None:
        all_relationships = selected_relationships
    else:
        all_relationships = collect_all_relationships(views_metadata)

    # Detect role-playing dimensions (dimensions referenced by multiple tables)
    role_playing_dims = detect_role_playing_dimensions(all_relationships)

    # Filter based on user selection (default: duplicate all)
    if duplicate_role_playing_dims is not None:
        role_playing_dims = {
            dim: refs for dim, refs in role_playing_dims.items()
            if duplicate_role_playing_dims.get(dim, True)
        }

    # Create duplicated dimension tables and track source mappings
    duplicated_tables: list[tuple[SemanticViewMetadata, str]] = []  # (metadata, source_name)
    relationship_rewrites: dict[tuple[str, str], str] = {}  # (from_table, to_table) -> new_to_table

    for dim_name, referencing_tables in role_playing_dims.items():
        # Find the original dimension metadata
        original_dim = next((m for m in views_metadata if m.view == dim_name), None)
        if not original_dim:
            continue

        for ref_table in referencing_tables:
            # Create role-prefixed copy (e.g., CUSTOMER_NATION)
            new_dim, source_name = create_role_playing_table(original_dim, ref_table, dim_name)
            duplicated_tables.append((new_dim, source_name))

            # Track rewrite: (CUSTOMER, NATION) -> CUSTOMER_NATION
            relationship_rewrites[(ref_table, dim_name)] = new_dim.view

    # Build final table list:
    # - Include original tables that are NOT being duplicated as role-playing dims
    # - Include all duplicated role-playing dimension copies
    # Tuple format: (metadata, source_name, use_native)
    tables_to_generate: list[tuple[SemanticViewMetadata, str | None, bool]] = []

    for metadata in views_metadata:
        if metadata.view in role_playing_dims:
            # This is a role-playing dimension - skip original, use copies instead
            continue
        # Determine connector type based on object_type
        # Semantic views use custom connector, tables/views use native connector
        use_native = metadata.object_type in ("TABLE", "VIEW")
        tables_to_generate.append((metadata, None, use_native))

    # Add duplicated tables (use same connector type as original)
    for dup_metadata, source_name in duplicated_tables:
        use_native = dup_metadata.object_type in ("TABLE", "VIEW")
        tables_to_generate.append((dup_metadata, source_name, use_native))

    # Generate table definitions with appropriate connector
    tables = [
        _generate_table_definition_directquery(
            metadata, server, warehouse, source_name, use_native=use_native, mode=mode
        )
        for metadata, source_name, use_native in tables_to_generate
    ]

    # Determine which connectors are needed
    has_semantic_views = any(m.object_type == "SEMANTIC_VIEW" for m, _, _ in tables_to_generate)
    has_standard_tables = any(m.object_type in ("TABLE", "VIEW") for m, _, _ in tables_to_generate)

    # Create shared expressions for the data sources (custom and/or native)
    expressions = generate_dual_source_expressions(
        server, warehouse, has_semantic_views, has_standard_tables
    )

    # Rewrite relationships to use duplicated tables
    # Two cases to handle:
    # 1. INCOMING to role-playing dim: CUSTOMER->NATION becomes CUSTOMER->CUSTOMER_NATION
    # 2. OUTGOING from role-playing dim: NATION->REGION becomes CUSTOMER_NATION->REGION AND SUPPLIER_NATION->REGION
    #
    # Special case: If both from_table AND to_table are role-playing dims:
    #   SUPPLIER->NATION (where SUPPLIER is duplicated to LINEITEM_SUPPLIER, PARTSUPP_SUPPLIER)
    #   should become LINEITEM_SUPPLIER->SUPPLIER_NATION, PARTSUPP_SUPPLIER->SUPPLIER_NATION
    rewritten_relationships = []
    for rel in all_relationships:
        # Check if this is an OUTGOING relationship from a role-playing dimension
        if rel.from_table in role_playing_dims:
            # Duplicate this relationship for each role-prefixed copy
            for ref_table in role_playing_dims[rel.from_table]:
                new_from_table = f"{ref_table}_{rel.from_table}"

                # Also check if to_table needs rewriting (if it's also a role-playing dim)
                # Use the ORIGINAL from_table to look up the rewrite
                new_to_table = relationship_rewrites.get((rel.from_table, rel.to_table), rel.to_table)

                rewritten_rel = RelationshipMetadata(
                    name=f"{ref_table}_{rel.name}" if rel.name else None,
                    from_table=new_from_table,
                    from_columns=rel.from_column,
                    to_table=new_to_table,  # May be rewritten if to_table is also role-playing
                    to_columns=rel.to_column
                )
                rewritten_relationships.append(rewritten_rel)
        else:
            # Check if this is an INCOMING relationship to a role-playing dimension
            new_to_table = relationship_rewrites.get((rel.from_table, rel.to_table), rel.to_table)

            # Create new relationship with potentially rewritten to_table
            rewritten_rel = RelationshipMetadata(
                name=rel.name,
                from_table=rel.from_table,
                from_columns=rel.from_column,
                to_table=new_to_table,  # May be rewritten to prefixed name
                to_columns=rel.to_column
            )
            rewritten_relationships.append(rewritten_rel)

    # With duplicated role-playing dimensions, there are no ambiguous paths
    # Only detect ambiguous paths for relationships that weren't rewritten
    # Pass user_active_choices to respect user's preference for which relationships are active
    active_rels, inactive_rels = detect_ambiguous_paths(
        rewritten_relationships,
        user_active_choices=user_active_choices
    )
    pbi_relationships = generate_pbi_relationships(rewritten_relationships, inactive_rels)

    # Build full schema
    now = datetime.utcnow().isoformat(timespec='milliseconds')
    model = {
        "culture": "en-US",
        "dataAccessOptions": {
            "legacyRedirects": True,
            "returnErrorValuesAsNull": True
        },
        "defaultPowerBIDataSourceVersion": "powerBI_V3",
        "sourceQueryCulture": "en-US",
        "tables": tables,
        "expressions": expressions,
        "annotations": [
            {
                "name": "__PBI_TimeIntelligenceEnabled",
                "value": "0"
            },
            {
                "name": "PBIDesktopVersion",
                "value": "2.149.178.0"
            },
            {
                "name": "PBI_QueryOrder",
                "value": json.dumps([m.view for m, _, _ in tables_to_generate])
            },
            {
                "name": "PBI_ProTooling",
                "value": "[\"DevMode\"]"
            }
        ]
    }

    # Add relationships if any exist
    if pbi_relationships:
        model["relationships"] = pbi_relationships

    schema = {
        "name": str(uuid.uuid4()),
        "compatibilityLevel": 1567,
        "createdTimestamp": now,
        "lastUpdate": now,
        "lastSchemaUpdate": now,
        "model": model
    }

    return json.dumps(schema, indent=2)
