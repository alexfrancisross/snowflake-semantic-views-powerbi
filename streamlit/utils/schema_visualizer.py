"""
Schema Visualizer for Power BI Semantic Model Generator.

Provides interactive graph visualization of tables and their relationships
using streamlit-flow-component. Creates Power BI-like data model diagrams
with color-coded nodes and edges based on object type and fan-out risk.
"""

import streamlit as st
from typing import Optional

try:
    from streamlit_flow import streamlit_flow
    from streamlit_flow.elements import StreamlitFlowNode, StreamlitFlowEdge
    from streamlit_flow.state import StreamlitFlowState
    from streamlit_flow.layouts import LayeredLayout, ManualLayout
    FLOW_AVAILABLE = True
except ImportError:
    FLOW_AVAILABLE = False

# Node colors by object type (Snowflake Design System - Secondary Palette)
NODE_STYLES = {
    "SEMANTIC_VIEW": {
        "background": "#F0EBF8",      # Light Purple Moon
        "border": "#7254A3",          # Purple Moon
        "header": "#7254A3",
    },
    "TABLE": {
        "background": "#E8F6F7",      # Light Star Blue
        "border": "#75CDD7",          # Star Blue
        "header": "#75CDD7",
    },
    "VIEW": {
        "background": "#FFF5E6",      # Light Valencia Orange
        "border": "#FF9F36",          # Valencia Orange
        "header": "#FF9F36",
    },
}

# Edge colors - Snowflake Design System
EDGE_COLOR_NORMAL = "#8A8A8A"  # Snowflake Gray Medium
EDGE_COLOR_RISKY = "#DC3545"   # Snowflake Error Red


def create_node_style(obj_type: str, is_selected: bool = False) -> dict:
    """
    Create CSS style dict for a table node.

    Args:
        obj_type: Type of object (SEMANTIC_VIEW, TABLE, VIEW)
        is_selected: Whether this node is currently selected

    Returns:
        Dictionary of CSS styles for the node
    """
    colors = NODE_STYLES.get(obj_type, NODE_STYLES["TABLE"])

    return {
        "backgroundColor": colors["background"],
        "border": f"{'3px' if is_selected else '2px'} solid {colors['border']}",
        "borderRadius": "6px",
        "padding": "8px 12px",
        "minWidth": "140px",
        "boxShadow": "0 2px 4px rgba(0,0,0,0.1)" if is_selected else "none",
    }


def create_node_content(
    table_name: str,
    col_count: int,
    obj_type: str,
    columns: list = None
) -> str:
    """
    Create display content for a table node.

    For semantic views, shows grouped column counts (D:X M:Y F:Z).
    For regular tables/views, shows total column count.

    Args:
        table_name: Name of the table/view
        col_count: Number of columns in the table
        obj_type: Type of object for icon selection
        columns: Optional list of ColumnMetadata for grouped display

    Returns:
        Formatted string for node label
    """
    # Semantic views: show D:X M:Y F:Z format
    if obj_type == "SEMANTIC_VIEW" and columns:
        dims = sum(1 for c in columns if getattr(c, 'kind', None) == "DIMENSION")
        metrics = sum(1 for c in columns if getattr(c, 'kind', None) == "METRIC")
        facts = sum(1 for c in columns if getattr(c, 'kind', None) == "FACT")

        parts = []
        if dims:
            parts.append(f"D:{dims}")
        if metrics:
            parts.append(f"M:{metrics}")
        if facts:
            parts.append(f"F:{facts}")

        if parts:
            return f"{table_name}\n{' '.join(parts)}"

    # Default: simple column count
    return f"{table_name}\n({col_count} cols)"


def get_cardinality_label(rel) -> str:
    """
    Get cardinality label string for a relationship (e.g., '*:1', '1:1').

    Args:
        rel: Relationship metadata with optional cardinality info

    Returns:
        String like '*:1' or '1:*' or empty if no cardinality info
    """
    if not hasattr(rel, 'cardinality') or not rel.cardinality:
        return ""

    from_card = getattr(rel.cardinality, 'from_cardinality', None)
    to_card = getattr(rel.cardinality, 'to_cardinality', None)

    if not from_card or not to_card:
        return ""

    from_sym = "1" if from_card == "one" else "*"
    to_sym = "1" if to_card == "one" else "*"

    return f"{from_sym}:{to_sym}"


def get_edge_style(risk_level: str) -> dict:
    """
    Get edge style based on fan-out risk level.

    Args:
        risk_level: Risk level string (critical, high, medium, low, none)

    Returns:
        Dictionary of CSS styles for the edge
    """
    # Any risk level other than "none" or "low" is considered risky
    is_risky = risk_level in ["critical", "high", "medium"]
    color = EDGE_COLOR_RISKY if is_risky else EDGE_COLOR_NORMAL

    return {
        "stroke": color,
        "strokeWidth": 3 if is_risky else 2,
    }


def _remove_overlaps(
    positions: dict[str, tuple[float, float]],
    node_width: float,
    node_height: float,
    padding: float = 20.0,
) -> dict[str, tuple[float, float]]:
    """
    Greedy overlap removal - shift overlapping nodes apart.

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

                overlap_x = (node_width + padding) - abs(x1 - x2)
                overlap_y = (node_height + padding) - abs(y1 - y2)

                if overlap_x > 0 and overlap_y > 0:
                    if overlap_x < overlap_y:
                        shift = overlap_x + 1
                        if x2 >= x1:
                            pos[name2] = (x2 + shift, y2)
                        else:
                            pos[name2] = (x2 - shift, y2)
                    else:
                        shift = overlap_y + 1
                        if y2 >= y1:
                            pos[name2] = (x2, y2 + shift)
                        else:
                            pos[name2] = (x2, y2 - shift)
                    changed = True

    return pos


def calculate_node_positions(
    tables: list,
    relationships: list,
    role_playing_dims: dict[str, list[str]] = None,
) -> dict:
    """
    Calculate positions using relationship-based clustering.

    Layout:
    - TOP: Tables with relationships (BFS from most-connected center)
    - Role-playing copies positioned below their parent
    - BOTTOM: 3-column grid for unrelated tables + semantic views

    Args:
        tables: List of table metadata objects
        relationships: List of relationship objects
        role_playing_dims: Optional dict mapping dimension name to referencing tables

    Returns:
        Dictionary mapping table names to (x, y) positions
    """
    from collections import defaultdict, deque

    # Layout constants (scaled for streamlit-flow)
    # NODE_WIDTH accounts for long table names like "REGIONAL_SALES_SEMANTIC"
    NODE_WIDTH = 200
    NODE_HEIGHT = 55
    X_PADDING = 100
    Y_PADDING = 10
    X_SPACING = NODE_WIDTH + X_PADDING    # 300
    Y_SPACING = NODE_HEIGHT + Y_PADDING   # 65
    BOTTOM_GAP = 120  # Larger gap to separate related tables from standalone grid

    positions = {}

    if not tables:
        return positions

    # Build table name set
    table_names = {t.view for t in tables}

    # Build adjacency list from relationships
    connections: dict[str, set[str]] = defaultdict(set)
    if relationships:
        for rel in relationships:
            if rel.from_table in table_names and rel.to_table in table_names:
                connections[rel.from_table].add(rel.to_table)
                connections[rel.to_table].add(rel.from_table)

    # Identify role-playing copies
    role_playing_copies: dict[str, str] = {}  # copy_name -> parent_table
    if role_playing_dims:
        for dim_name, referencing_tables in role_playing_dims.items():
            for ref_table in referencing_tables:
                copy_name = f"{ref_table}_{dim_name}"
                if copy_name in table_names:
                    role_playing_copies[copy_name] = ref_table

    # Partition tables: related (has connections) vs unrelated
    related_tables = []
    unrelated_tables = []

    for table in tables:
        table_name = table.view
        # Skip role-playing copies - they'll be positioned with their parent
        if table_name in role_playing_copies:
            continue
        # Check if this table has any relationships
        if table_name in connections and connections[table_name]:
            related_tables.append(table)
        else:
            unrelated_tables.append(table)

    # === Position related tables using BFS clustering ===
    if related_tables:
        # Find center table (most connections)
        connection_counts = {t.view: len(connections.get(t.view, set())) for t in related_tables}
        center_table = max(connection_counts, key=connection_counts.get)

        # BFS to assign levels (distance from center)
        levels: dict[int, list[str]] = defaultdict(list)
        visited: set[str] = set()
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

        # Add any unvisited related tables
        for table in related_tables:
            if table.view not in visited:
                max_level = max(levels.keys()) if levels else 0
                levels[max_level + 1].append(table.view)

        # Calculate positions by level
        max_level = max(levels.keys()) if levels else 0
        center_x = (max_level + 1) * X_SPACING

        for level, tables_at_level in levels.items():
            # Level 0 = center, odd levels = right, even levels = left
            if level == 0:
                x = center_x
            elif level % 2 == 1:
                x = center_x + ((level + 1) // 2) * X_SPACING
            else:
                x = center_x - (level // 2) * X_SPACING

            # Stack tables vertically at this level
            total_height = len(tables_at_level) * Y_SPACING
            start_y = 50 - total_height // 2 + Y_SPACING // 2

            for i, table_name in enumerate(tables_at_level):
                y = start_y + i * Y_SPACING
                positions[table_name] = (float(x), float(y))

        # Position role-playing copies below their parent
        copies_by_parent: dict[str, list[str]] = defaultdict(list)
        for copy_name, parent_table in role_playing_copies.items():
            copies_by_parent[parent_table].append(copy_name)

        for parent_table, copies in copies_by_parent.items():
            if parent_table in positions:
                parent_x, parent_y = positions[parent_table]
                for i, copy_name in enumerate(copies):
                    copy_y = parent_y + (i + 1) * Y_SPACING
                    positions[copy_name] = (parent_x, copy_y)
            else:
                # Fallback if parent not in positions
                max_x = max(p[0] for p in positions.values()) if positions else 0
                for i, copy_name in enumerate(copies):
                    positions[copy_name] = (max_x + X_SPACING, float(i * Y_SPACING + 50))

        # Remove overlaps
        positions = _remove_overlaps(positions, NODE_WIDTH, NODE_HEIGHT, padding=X_PADDING)

    # === Position unrelated tables at bottom in 3-column grid ===
    if unrelated_tables:
        # Calculate bottom_y (below all related tables) and horizontal center
        if positions:
            bottom_y = max(y for _, y in positions.values()) + BOTTOM_GAP
            # Center the grid horizontally under the main data model
            min_main_x = min(x for x, _ in positions.values())
            max_main_x = max(x for x, _ in positions.values())
            center_main_x = (min_main_x + max_main_x) / 2
        else:
            bottom_y = 50
            center_main_x = X_SPACING * 1.5  # Default center if no related tables

        # Separate unrelated tables by type
        semantic_views = [t for t in unrelated_tables if getattr(t, 'object_type', '') == 'SEMANTIC_VIEW']
        views = [t for t in unrelated_tables if getattr(t, 'object_type', '') == 'VIEW']
        orphan_tables = [t for t in unrelated_tables if getattr(t, 'object_type', 'TABLE') == 'TABLE']

        # 3-column layout - use same spacing as main model to prevent overlaps
        col_spacing = X_SPACING
        y_row_spacing = Y_SPACING

        # Calculate grid width and starting X position (centered under main model)
        grid_width = col_spacing * 2  # 3 columns = 2 gaps
        grid_start_x = center_main_x - grid_width / 2

        # Column 1: Tables (blue) - leftmost
        for i, table in enumerate(orphan_tables):
            positions[table.view] = (grid_start_x, bottom_y + i * y_row_spacing)

        # Column 2: Views (orange) - center
        for i, table in enumerate(views):
            positions[table.view] = (grid_start_x + col_spacing, bottom_y + i * y_row_spacing)

        # Column 3: Semantic Views (purple) - rightmost
        for i, table in enumerate(semantic_views):
            positions[table.view] = (grid_start_x + col_spacing * 2, bottom_y + i * y_row_spacing)

    # Note: Don't run _remove_overlaps on grid section - it breaks column alignment
    # The grid layout is already properly spaced with X_SPACING and Y_SPACING

    # Normalize positions to start from (50, 50)
    if positions:
        min_x = min(p[0] for p in positions.values())
        min_y = min(p[1] for p in positions.values())
        positions = {
            name: (x - min_x + 50, y - min_y + 50)
            for name, (x, y) in positions.items()
        }

    return positions


def create_flow_nodes(
    tables: list,
    relationships: list = None,
    selected_table: Optional[str] = None,
    role_playing_dims: dict[str, list[str]] = None,
) -> list:
    """
    Create StreamlitFlowNode objects from table metadata.

    Args:
        tables: List of SemanticViewMetadata objects
        relationships: List of relationship objects for star schema positioning
        selected_table: Optional table name to highlight
        role_playing_dims: Optional dict mapping dimension name to referencing tables

    Returns:
        List of StreamlitFlowNode objects
    """
    nodes = []
    positions = calculate_node_positions(tables, relationships or [], role_playing_dims)

    for table in tables:
        table_name = table.view
        obj_type = getattr(table, 'object_type', 'TABLE')
        columns = table.columns if hasattr(table, 'columns') else []
        col_count = len(columns)
        is_selected = selected_table and table_name.upper() == selected_table.upper()

        # Create node with Power BI styling
        # Pass columns for semantic view grouped display (D:X M:Y F:Z)
        node = StreamlitFlowNode(
            id=table_name,
            pos=positions.get(table_name, (0, 0)),
            data={"content": create_node_content(table_name, col_count, obj_type, columns)},
            node_type="default",
            style=create_node_style(obj_type, is_selected),
            source_position="right",
            target_position="left",
            draggable=True,
        )
        nodes.append(node)

    return nodes


def create_flow_edges(
    relationships: list,
    tables: list
) -> list:
    """
    Create StreamlitFlowEdge objects from relationship metadata.

    Visual indicators (no labels for clean diagram):
    - Normal relationships: gray lines
    - Fan-out risk: red animated lines
    - Self-referential: dashed orange lines

    Relationship details are shown in the checkbox list on the left.

    Args:
        relationships: List of RelationshipMetadata objects
        tables: List of table metadata for validation

    Returns:
        List of StreamlitFlowEdge objects
    """
    edges = []
    table_names = {table.view for table in tables}

    for i, rel in enumerate(relationships):
        # Only add edge if both tables are in our list
        if rel.from_table not in table_names or rel.to_table not in table_names:
            continue

        # Check for self-referential relationship
        is_self_ref = rel.from_table == rel.to_table

        # Determine edge style based on fan-out risk or self-ref
        risk_level = "none"
        if hasattr(rel, 'fan_out_risk') and rel.fan_out_risk:
            risk_level = getattr(rel.fan_out_risk, 'risk_level', 'none')

        if is_self_ref:
            # Self-referential: dashed orange line (warning style)
            edge_style = {
                "stroke": "#FFA500",  # Orange warning color
                "strokeWidth": 2,
                "strokeDasharray": "5,5",  # Dashed line
            }
        else:
            edge_style = get_edge_style(risk_level)

        # No labels on edges - keeps diagram clean
        # Relationship details shown in checkbox list on left panel
        edge = StreamlitFlowEdge(
            id=f"e{i}_{rel.from_table}_{rel.to_table}",
            source=rel.from_table,
            target=rel.to_table,
            edge_type="smoothstep",
            style=edge_style,
            label="",  # Clean diagram - no edge labels
            animated=risk_level in ["critical", "high", "medium"] and not is_self_ref,
        )
        edges.append(edge)

    return edges


def render_schema_visualizer(
    tables: list,
    relationships: list,
    selected_table: Optional[str] = None,
    key: str = "schema_flow",
    role_playing_dims: dict[str, list[str]] = None,
) -> Optional[str]:
    """
    Render the interactive schema graph visualization.

    Creates a Power BI-style data model diagram with:
    - Tables as colored rectangular boxes
    - Relationships as connecting lines
    - Color coding by object type and fan-out risk
    - Interactive drag, zoom, and pan
    - Relationship-based clustering layout

    Args:
        tables: List of SemanticViewMetadata objects
        relationships: List of RelationshipMetadata objects
        selected_table: Optional table name to highlight
        key: Unique key for the Streamlit component
        role_playing_dims: Optional dict mapping dimension name to referencing tables

    Returns:
        Name of clicked node (if any), or None
    """
    if not FLOW_AVAILABLE:
        st.warning(
            "Schema visualizer requires streamlit-flow-component. "
            "Install with: pip install streamlit-flow-component"
        )
        return None

    if not tables:
        st.info("No tables to visualize")
        return None

    # Create nodes and edges (pass relationships for BFS clustering layout)
    nodes = create_flow_nodes(tables, relationships, selected_table, role_playing_dims)
    edges = create_flow_edges(relationships, tables)

    if not nodes:
        st.info("No data to display in graph")
        return None

    # Calculate height based on number of nodes (taller for better visibility)
    num_nodes = len(nodes)
    height = min(700, max(450, num_nodes * 60))

    # Create state with ManualLayout to use our calculated positions
    # (LayeredLayout ignores our type-based grouping)
    state = StreamlitFlowState(nodes, edges)
    layout = ManualLayout()

    # Use fragment to isolate component state changes from page reruns
    # Note: Fragment may still re-execute internally but won't affect main page
    @st.fragment
    def _render_flow():
        streamlit_flow(
            key=key,
            state=state,
            height=height,
            fit_view=True,
            show_controls=True,
            show_minimap=False,
            allow_zoom=True,
            pan_on_drag=True,
            layout=layout,
            get_node_on_click=False,
            hide_watermark=True,
        )

    try:
        _render_flow()
        return None
    except Exception as e:
        st.error(f"Error rendering schema diagram: {e}")
        return None


def show_graph_legend():
    """Display legend explaining graph colors and shapes (Snowflake Design System)."""
    st.markdown("""
    <style>
        @keyframes legendDash {
            0% { background-position: 0 0; }
            100% { background-position: 20px 0; }
        }
    </style>
    <div style="display: flex; gap: 16px; flex-wrap: wrap; padding: 10px 12px; background: #F5F5F5; border-radius: 8px; border-left: 4px solid #29B5E8; margin-top: 8px; align-items: center;">
        <div style="display: flex; align-items: center; gap: 6px;">
            <div style="width: 16px; height: 16px; background: #E8F6F7; border: 2px solid #75CDD7; border-radius: 4px;"></div>
            <span style="font-size: 12px; color: #5B5B5B;">Table</span>
        </div>
        <div style="display: flex; align-items: center; gap: 6px;">
            <div style="width: 16px; height: 16px; background: #FFF5E6; border: 2px solid #FF9F36; border-radius: 4px;"></div>
            <span style="font-size: 12px; color: #5B5B5B;">View</span>
        </div>
        <div style="display: flex; align-items: center; gap: 6px;">
            <div style="width: 16px; height: 16px; background: #F0EBF8; border: 2px solid #7254A3; border-radius: 4px;"></div>
            <span style="font-size: 12px; color: #5B5B5B;">Semantic View</span>
        </div>
        <div style="width: 1px; height: 16px; background: #E5E5E5;"></div>
        <div style="display: flex; align-items: center; gap: 6px;">
            <div style="width: 20px; height: 3px; background: repeating-linear-gradient(90deg, #DC3545 0px, #DC3545 4px, transparent 4px, transparent 8px); background-size: 8px 3px; animation: legendDash 0.5s linear infinite;"></div>
            <span style="font-size: 12px; color: #5B5B5B;">Fan-out risk</span>
        </div>
        <div style="display: flex; align-items: center; gap: 6px;">
            <div style="width: 20px; height: 2px; background: repeating-linear-gradient(90deg, #FFA500 0px, #FFA500 4px, transparent 4px, transparent 8px);"></div>
            <span style="font-size: 12px; color: #5B5B5B;">Self-ref</span>
        </div>
        <div style="display: flex; align-items: center; gap: 6px;">
            <div style="width: 20px; height: 2px; background: #8A8A8A;"></div>
            <span style="font-size: 12px; color: #5B5B5B;">Normal</span>
        </div>
        <div style="width: 1px; height: 16px; background: #E5E5E5;"></div>
        <div style="display: flex; align-items: center; gap: 6px;">
            <span style="font-size: 11px; color: #5B5B5B; font-style: italic;">D=Dimension M=Metric F=Fact</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
