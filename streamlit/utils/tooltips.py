"""
Tooltip definitions and UI helpers for the Power BI Semantic Model Generator.

Provides user-friendly explanations for domain-specific terminology
and reusable UI components like code blocks with copy buttons.
"""

import streamlit as st
import streamlit.components.v1 as components
import html
import uuid

# Technical term definitions
TERM_DEFINITIONS = {
    "semantic_view": (
        "A Snowflake object that defines metrics and dimensions for analytical queries. "
        "It pre-defines how data should be aggregated, ensuring consistent calculations across all reports."
    ),
    "dimension": (
        "A categorical attribute used to group or filter data (e.g., Region, Product Category, Date). "
        "Dimensions provide context for metrics and appear in rows, columns, or filters in reports."
    ),
    "metric": (
        "A pre-aggregated numeric measure defined in a semantic view (e.g., Total Sales, Avg Order Value). "
        "Metrics are automatically calculated by Snowflake when queried."
    ),
    "fact": (
        "A raw numeric value at the detail level (e.g., individual order amounts). "
        "Unlike metrics, facts are not pre-aggregated and require explicit aggregation in reports."
    ),
    "directquery": (
        "A Power BI connection mode where data stays in Snowflake and queries run live. "
        "Ideal for large datasets and real-time reporting, but requires good query performance."
    ),
    "import": (
        "A Power BI connection mode where data is loaded into Power BI's in-memory engine. "
        "Faster report interactions but requires periodic refresh and uses local memory."
    ),
    "fan_out": (
        "A data modeling issue where joining tables causes row multiplication. "
        "Occurs in many-to-many relationships and can lead to inflated measures (double counting)."
    ),
    "cardinality": (
        "The relationship type between tables: One-to-Many (1:N), Many-to-One (N:1), or Many-to-Many (M:N). "
        "Affects how Power BI aggregates data across related tables."
    ),
    "granularity": (
        "The level of detail in data (e.g., daily vs monthly, order line vs order header). "
        "In semantic views, metrics must be at equal or higher granularity than dimensions."
    ),
    "bridge_table": (
        "An intermediate table that connects two tables in a many-to-many relationship. "
        "Contains only the keys from both tables, resolving fan-out issues."
    ),
    "role_playing": (
        "When a single dimension table is used multiple times with different meanings "
        "(e.g., Date table used as Order Date and Ship Date). Requires separate relationships."
    ),
    "star_schema": (
        "A data model design with a central fact table connected to multiple dimension tables. "
        "The simplest and most efficient pattern for analytical queries."
    ),
    "snowflake_schema": (
        "A variation of star schema where dimension tables are normalized into sub-dimensions. "
        "More complex but can save storage for large dimension hierarchies."
    ),
}

# CSS for tooltip styling (Snowflake Design System)
TOOLTIP_CSS = """
<style>
.ux-tooltip {
    position: relative;
    display: inline;
    border-bottom: 1px dotted #11567F;
    cursor: help;
    color: inherit;
}
.ux-tooltip:hover {
    border-bottom-color: #29B5E8;
}
/* Native tooltip styling via title attribute */
.ux-tooltip[title] {
    text-decoration: none;
}
</style>
"""


def inject_tooltip_css():
    """Inject CSS for tooltip styling. Call once at app start."""
    st.markdown(TOOLTIP_CSS, unsafe_allow_html=True)


def term_with_tooltip(term: str, display_text: str = None) -> str:
    """
    Render a term with a tooltip showing its definition.

    Args:
        term: The technical term key (must exist in TERM_DEFINITIONS)
        display_text: Optional display text (defaults to capitalized term)

    Returns:
        HTML string with tooltip markup
    """
    definition = TERM_DEFINITIONS.get(term.lower(), "")
    if not definition:
        return display_text or term

    label = display_text or term.replace("_", " ").title()
    # Use title attribute for native browser tooltip
    return f'<span class="ux-tooltip" title="{definition}">{label}</span>'


def render_term(term: str, display_text: str = None):
    """
    Render a term with tooltip using st.markdown.

    Args:
        term: The technical term key
        display_text: Optional display text
    """
    html = term_with_tooltip(term, display_text)
    st.markdown(html, unsafe_allow_html=True)


def tooltip_label(term: str, prefix: str = "", suffix: str = "") -> str:
    """
    Create a label with embedded tooltip HTML.

    Useful for form labels and headers that need inline tooltips.

    Args:
        term: The technical term key
        prefix: Text before the tooltip term
        suffix: Text after the tooltip term

    Returns:
        HTML string with prefix + tooltip + suffix
    """
    tooltip_html = term_with_tooltip(term)
    return f"{prefix}{tooltip_html}{suffix}"


# Convenience functions for common terms
def dimensions_label() -> str:
    """Return 'Dimensions' with tooltip."""
    return term_with_tooltip("dimension", "Dimensions")


def metrics_label() -> str:
    """Return 'Metrics' with tooltip."""
    return term_with_tooltip("metric", "Metrics")


def facts_label() -> str:
    """Return 'Facts' with tooltip."""
    return term_with_tooltip("fact", "Facts")


def directquery_label() -> str:
    """Return 'DirectQuery' with tooltip."""
    return term_with_tooltip("directquery", "DirectQuery")


def import_label() -> str:
    """Return 'Import' with tooltip."""
    return term_with_tooltip("import", "Import")


def semantic_view_label() -> str:
    """Return 'Semantic View' with tooltip."""
    return term_with_tooltip("semantic_view", "Semantic View")


def fan_out_label() -> str:
    """Return 'Fan-out' with tooltip."""
    return term_with_tooltip("fan_out", "Fan-out")


def cardinality_label() -> str:
    """Return 'Cardinality' with tooltip."""
    return term_with_tooltip("cardinality", "Cardinality")


def granularity_label() -> str:
    """Return 'Granularity' with tooltip."""
    return term_with_tooltip("granularity", "Granularity")


# === Code Block with Copy Button ===

# CSS for copy button styling (Snowflake Design System)
COPY_BUTTON_CSS = """
<style>
.ux-code-container {
    position: relative;
    margin: 8px 0;
}
.ux-copy-btn {
    position: absolute;
    top: 8px;
    right: 8px;
    padding: 4px 12px;
    background: #29B5E8;
    color: white;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 600;
    z-index: 10;
    transition: background 0.2s;
    text-transform: uppercase;
    letter-spacing: 0.02em;
}
.ux-copy-btn:hover {
    background: #11567F;
}
.ux-copy-btn.copied {
    background: #34C759;
}
.ux-code-block {
    background: #1e1e1e;
    color: #d4d4d4;
    padding: 12px;
    padding-top: 40px;
    border-radius: 12px;
    overflow-x: auto;
    font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Roboto Mono', monospace;
    font-size: 13px;
    line-height: 1.5;
    white-space: pre-wrap;
    word-wrap: break-word;
}
</style>
"""

def inject_copy_button_css():
    """Inject CSS for copy button styling. Call once at app start.

    Uses session state to track injection status instead of global variable.
    """
    if st.session_state.get("_copy_css_injected"):
        return
    st.markdown(COPY_BUTTON_CSS, unsafe_allow_html=True)
    st.session_state._copy_css_injected = True


def code_with_copy(code: str, language: str = "sql", key: str = None) -> None:
    """
    Display a code block with a copy-to-clipboard button.

    Args:
        code: The code string to display
        language: Language for syntax highlighting hint (display only)
        key: Optional unique key for the component
    """
    # Generate unique ID for this code block
    block_id = key or f"code_{uuid.uuid4().hex[:8]}"

    # Escape HTML entities in code
    escaped_code = html.escape(code)

    # Create the HTML with embedded JavaScript
    html_content = f"""
    <div class="ux-code-container">
        <button class="ux-copy-btn" onclick="copyCode_{block_id}(this)" title="Copy to clipboard">
            Copy
        </button>
        <pre class="ux-code-block"><code>{escaped_code}</code></pre>
    </div>
    <script>
    function copyCode_{block_id}(btn) {{
        const code = {repr(code)};
        navigator.clipboard.writeText(code).then(function() {{
            btn.textContent = 'Copied!';
            btn.classList.add('copied');
            setTimeout(function() {{
                btn.textContent = 'Copy';
                btn.classList.remove('copied');
            }}, 2000);
        }}).catch(function(err) {{
            console.error('Failed to copy:', err);
            btn.textContent = 'Failed';
        }});
    }}
    </script>
    """

    # Inject CSS if not already done
    inject_copy_button_css()

    # Render the HTML
    st.markdown(html_content, unsafe_allow_html=True)


# === Loading Skeletons ===

SKELETON_CSS = """
<style>
.ux-skeleton {
    background: linear-gradient(90deg, #F5F5F5 25%, #E5E5E5 50%, #F5F5F5 75%);
    background-size: 200% 100%;
    animation: ux-shimmer 1.5s infinite;
    border-radius: 8px;
}
@keyframes ux-shimmer {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
}
.ux-skeleton-text {
    height: 16px;
    margin: 8px 0;
}
.ux-skeleton-title {
    height: 24px;
    width: 40%;
    margin: 12px 0;
}
.ux-skeleton-card {
    padding: 16px;
    border: 1px solid #E5E5E5;
    border-left: 4px solid #29B5E8;
    border-radius: 12px;
    margin: 8px 0;
}
.ux-skeleton-row {
    display: flex;
    gap: 12px;
    margin: 8px 0;
}
.ux-skeleton-tree-item {
    height: 32px;
    margin: 4px 0;
}
</style>
"""

def inject_skeleton_css():
    """Inject CSS for skeleton loading. Call once at app start.

    Uses session state to track injection status instead of global variable.
    """
    if st.session_state.get("_skeleton_css_injected"):
        return
    st.markdown(SKELETON_CSS, unsafe_allow_html=True)
    st.session_state._skeleton_css_injected = True


def show_skeleton_text(lines: int = 3, width_percent: int = 100) -> None:
    """Show skeleton text placeholder lines."""
    inject_skeleton_css()
    html_lines = []
    for i in range(lines):
        # Vary width for more natural look
        w = width_percent - (i * 10) if i < 3 else width_percent - 20
        html_lines.append(f'<div class="ux-skeleton ux-skeleton-text" style="width: {w}%;"></div>')
    st.markdown("\n".join(html_lines), unsafe_allow_html=True)


def show_skeleton_tree(items: int = 5) -> None:
    """Show skeleton tree placeholder."""
    inject_skeleton_css()
    html_items = []
    for i in range(items):
        indent = (i % 3) * 20  # Simulate tree hierarchy
        width = 100 - indent - 20
        html_items.append(f'<div class="ux-skeleton ux-skeleton-tree-item" style="width: {width}%; margin-left: {indent}px;"></div>')
    st.markdown("\n".join(html_items), unsafe_allow_html=True)


def show_skeleton_card(title: bool = True, lines: int = 2) -> None:
    """Show skeleton card placeholder."""
    inject_skeleton_css()
    content = []
    if title:
        content.append('<div class="ux-skeleton ux-skeleton-title"></div>')
    for i in range(lines):
        w = 90 - (i * 15)
        content.append(f'<div class="ux-skeleton ux-skeleton-text" style="width: {w}%;"></div>')
    st.markdown(f'<div class="ux-skeleton-card">{"".join(content)}</div>', unsafe_allow_html=True)


def show_skeleton_progress(message: str = "Loading...") -> None:
    """Show skeleton with loading message - use as spinner replacement."""
    inject_skeleton_css()
    html_content = f"""
    <div style="display: flex; align-items: center; gap: 12px; padding: 12px; background: #F5F5F5; border-radius: 12px; border-left: 4px solid #29B5E8; margin: 8px 0;">
        <div class="ux-skeleton" style="width: 24px; height: 24px; border-radius: 50%;"></div>
        <div style="flex: 1;">
            <div style="color: #5B5B5B; font-size: 14px; margin-bottom: 8px;">{html.escape(message)}</div>
            <div class="ux-skeleton ux-skeleton-text" style="width: 60%;"></div>
        </div>
    </div>
    """
    st.markdown(html_content, unsafe_allow_html=True)


def show_loading_spinner(message: str = "Loading...", size: int = 48) -> None:
    """Show Snowflake branded animated loading spinner with message.

    Args:
        message: Loading message to display
        size: Size of the spinner in pixels (default 48)
    """
    import base64
    from pathlib import Path

    # Load the spinner GIF as base64
    gif_path = Path(__file__).parent.parent / "img" / "loading_spinner.gif"
    if gif_path.exists():
        gif_data = base64.b64encode(gif_path.read_bytes()).decode('utf-8')
        spinner_html = f'<img src="data:image/gif;base64,{gif_data}" width="{size}" height="{size}" />'
    else:
        # Fallback to CSS spinner if GIF not found
        spinner_html = f'<div class="ux-skeleton" style="width: {size}px; height: {size}px; border-radius: 50%;"></div>'
        inject_skeleton_css()

    html_content = f"""
    <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 24px; gap: 16px;">
        {spinner_html}
        <div style="color: #5B5B5B; font-size: 14px; text-align: center;">{html.escape(message)}</div>
    </div>
    """
    st.markdown(html_content, unsafe_allow_html=True)


def show_loading_inline(message: str = "Loading...", size: int = 24) -> None:
    """Show inline loading spinner with message (horizontal layout).

    Args:
        message: Loading message to display
        size: Size of the spinner in pixels (default 24)
    """
    import base64
    from pathlib import Path

    gif_path = Path(__file__).parent.parent / "img" / "loading_spinner.gif"
    if gif_path.exists():
        gif_data = base64.b64encode(gif_path.read_bytes()).decode('utf-8')
        spinner_html = f'<img src="data:image/gif;base64,{gif_data}" width="{size}" height="{size}" style="vertical-align: middle;" />'
    else:
        spinner_html = f'<div class="ux-skeleton" style="width: {size}px; height: {size}px; border-radius: 50%; display: inline-block;"></div>'
        inject_skeleton_css()

    html_content = f"""
    <div style="display: flex; align-items: center; gap: 12px; padding: 12px; background: #F5F5F5; border-radius: 12px; border-left: 4px solid #29B5E8; margin: 8px 0;">
        {spinner_html}
        <span style="color: #5B5B5B; font-size: 14px;">{html.escape(message)}</span>
    </div>
    """
    st.markdown(html_content, unsafe_allow_html=True)


from contextlib import contextmanager


@contextmanager
def snowflake_spinner(message: str = "Loading...", size: int = 32):
    """Context manager for Snowflake branded loading spinner.

    Use as drop-in replacement for st.spinner():
        with snowflake_spinner("Loading data..."):
            data = fetch_data()

    Args:
        message: Loading message to display
        size: Size of the spinner in pixels (default 32)
    """
    import base64
    from pathlib import Path

    placeholder = st.empty()

    # Build spinner HTML
    gif_path = Path(__file__).parent.parent / "img" / "loading_spinner.gif"
    if gif_path.exists():
        gif_data = base64.b64encode(gif_path.read_bytes()).decode('utf-8')
        spinner_html = f'<img src="data:image/gif;base64,{gif_data}" width="{size}" height="{size}" style="vertical-align: middle;" />'
    else:
        inject_skeleton_css()
        spinner_html = f'<div class="ux-skeleton" style="width: {size}px; height: {size}px; border-radius: 50%; display: inline-block;"></div>'

    html_content = f"""
    <div style="display: flex; align-items: center; gap: 12px; padding: 12px; background: #F5F5F5; border-radius: 12px; border-left: 4px solid #29B5E8; margin: 8px 0;">
        {spinner_html}
        <span style="color: #5B5B5B; font-size: 14px;">{html.escape(message)}</span>
    </div>
    """

    try:
        placeholder.markdown(html_content, unsafe_allow_html=True)
        yield
    finally:
        placeholder.empty()
