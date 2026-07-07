"""
Snowflake Design System Theme Configuration.

Centralized theme constants based on official Snowflake brand guidelines.
Reference: snowflake-assets-main/styles/snowflake-theme.css
"""

# =============================================================================
# COLOR PALETTE - Primary
# =============================================================================

COLORS = {
    # Primary brand colors
    "blue": "#29B5E8",
    "blue_rgb": "41, 181, 232",
    "blue_light": "#75CDD7",
    "blue_dark": "#11567F",  # Mid-Blue

    # Midnight - Titles and headings
    "midnight": "#000000",

    # Grays
    "gray_dark": "#5B5B5B",
    "gray_medium": "#8A8A8A",
    "gray_light": "#E5E5E5",
    "gray_lighter": "#F5F5F5",
    "white": "#FFFFFF",

    # Secondary colors (use sparingly)
    "star_blue": "#75CDD7",
    "valencia_orange": "#FF9F36",
    "first_light": "#D45B90",
    "purple_moon": "#7254A3",

    # Semantic colors
    "success": "#34C759",
    "success_light": "#D4EDDA",
    "warning": "#FF9F36",
    "warning_light": "#FFF3CD",
    "error": "#DC3545",
    "error_light": "#F8D7DA",
    "info": "#29B5E8",
    "info_light": "#D1ECF1",

    # Interactive states
    "hover": "rgba(41, 181, 232, 0.1)",
    "active": "rgba(41, 181, 232, 0.2)",
    "focus": "rgba(41, 181, 232, 0.4)",
    "disabled": "#E5E5E5",
}

# =============================================================================
# DARK THEME COLORS
# =============================================================================

DARK_COLORS = {
    "bg_primary": "#0D1117",
    "bg_secondary": "#161B22",
    "bg_tertiary": "#21262D",
    "text_primary": "#F0F6FC",
    "text_secondary": "#8B949E",
    "text_tertiary": "#6E7681",
    "border_color": "#30363D",
    "border_color_dark": "#484F58",
}

# =============================================================================
# OBJECT TYPE COLORS (Snowflake Secondary Palette)
# =============================================================================

OBJECT_TYPE_COLORS = {
    "SEMANTIC_VIEW": {
        "primary": "#7254A3",      # Purple Moon
        "background": "#F0EBF8",
        "border": "#7254A3",
    },
    "TABLE": {
        "primary": "#75CDD7",      # Star Blue
        "background": "#E8F6F7",
        "border": "#75CDD7",
    },
    "VIEW": {
        "primary": "#FF9F36",      # Valencia Orange
        "background": "#FFF5E6",
        "border": "#FF9F36",
    },
}

# =============================================================================
# TYPOGRAPHY
# =============================================================================

TYPOGRAPHY = {
    # Font families
    "font_primary": "'Arial', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    "font_mono": "'SF Mono', 'Monaco', 'Inconsolata', 'Roboto Mono', monospace",

    # Font sizes (rem)
    "text_xs": "0.75rem",      # 12px
    "text_sm": "0.875rem",     # 14px
    "text_base": "1rem",       # 16px
    "text_lg": "1.125rem",     # 18px
    "text_xl": "1.25rem",      # 20px
    "text_2xl": "1.5rem",      # 24px
    "text_3xl": "1.875rem",    # 30px
    "text_4xl": "2.25rem",     # 36px
    "text_5xl": "3rem",        # 48px

    # Font weights
    "font_normal": 400,
    "font_medium": 500,
    "font_semibold": 600,
    "font_bold": 700,

    # Line heights
    "leading_tight": 1.25,
    "leading_normal": 1.5,
    "leading_relaxed": 1.75,
}

# =============================================================================
# SPACING & BORDERS
# =============================================================================

SPACING = {
    "space_1": "0.25rem",    # 4px
    "space_2": "0.5rem",     # 8px
    "space_3": "0.75rem",    # 12px
    "space_4": "1rem",       # 16px
    "space_5": "1.25rem",    # 20px
    "space_6": "1.5rem",     # 24px
    "space_8": "2rem",       # 32px
    "space_10": "2.5rem",    # 40px
    "space_12": "3rem",      # 48px
}

BORDERS = {
    "radius_sm": "0.25rem",   # 4px
    "radius_md": "0.5rem",    # 8px
    "radius_lg": "0.75rem",   # 12px
    "radius_xl": "1rem",      # 16px
    "radius_full": "9999px",
}

SHADOWS = {
    "shadow_sm": "0 1px 2px 0 rgba(0, 0, 0, 0.05)",
    "shadow_md": "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)",
    "shadow_lg": "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)",
    "shadow_xl": "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)",
}

# =============================================================================
# CSS GENERATION HELPERS
# =============================================================================

def get_css_variables(dark_mode: bool = False) -> str:
    """Generate CSS custom properties for theming."""

    # Base colors always available
    css = f"""
    :root {{
        /* Primary Colors */
        --sf-blue: {COLORS['blue']};
        --sf-blue-rgb: {COLORS['blue_rgb']};
        --sf-blue-light: {COLORS['blue_light']};
        --sf-blue-dark: {COLORS['blue_dark']};
        --sf-mid-blue: {COLORS['blue_dark']};
        --sf-midnight: {COLORS['midnight']};

        /* Grays */
        --sf-gray-dark: {COLORS['gray_dark']};
        --sf-gray-medium: {COLORS['gray_medium']};
        --sf-gray-light: {COLORS['gray_light']};
        --sf-gray-lighter: {COLORS['gray_lighter']};
        --sf-white: {COLORS['white']};

        /* Secondary Colors */
        --sf-star-blue: {COLORS['star_blue']};
        --sf-valencia-orange: {COLORS['valencia_orange']};
        --sf-first-light: {COLORS['first_light']};
        --sf-purple-moon: {COLORS['purple_moon']};

        /* Semantic Colors */
        --sf-success: {COLORS['success']};
        --sf-success-light: {COLORS['success_light']};
        --sf-warning: {COLORS['warning']};
        --sf-warning-light: {COLORS['warning_light']};
        --sf-error: {COLORS['error']};
        --sf-error-light: {COLORS['error_light']};
        --sf-info: {COLORS['info']};
        --sf-info-light: {COLORS['info_light']};

        /* Interactive States */
        --sf-hover: {COLORS['hover']};
        --sf-active: {COLORS['active']};
        --sf-focus: {COLORS['focus']};
        --sf-disabled: {COLORS['disabled']};

        /* Typography */
        --sf-font-primary: {TYPOGRAPHY['font_primary']};
        --sf-font-mono: {TYPOGRAPHY['font_mono']};
        --sf-text-xs: {TYPOGRAPHY['text_xs']};
        --sf-text-sm: {TYPOGRAPHY['text_sm']};
        --sf-text-base: {TYPOGRAPHY['text_base']};
        --sf-text-lg: {TYPOGRAPHY['text_lg']};
        --sf-text-xl: {TYPOGRAPHY['text_xl']};
        --sf-text-2xl: {TYPOGRAPHY['text_2xl']};
        --sf-text-3xl: {TYPOGRAPHY['text_3xl']};
        --sf-text-4xl: {TYPOGRAPHY['text_4xl']};
        --sf-font-normal: {TYPOGRAPHY['font_normal']};
        --sf-font-medium: {TYPOGRAPHY['font_medium']};
        --sf-font-semibold: {TYPOGRAPHY['font_semibold']};
        --sf-font-bold: {TYPOGRAPHY['font_bold']};

        /* Spacing */
        --sf-space-1: {SPACING['space_1']};
        --sf-space-2: {SPACING['space_2']};
        --sf-space-3: {SPACING['space_3']};
        --sf-space-4: {SPACING['space_4']};
        --sf-space-6: {SPACING['space_6']};
        --sf-space-8: {SPACING['space_8']};

        /* Borders & Radius */
        --sf-radius-sm: {BORDERS['radius_sm']};
        --sf-radius-md: {BORDERS['radius_md']};
        --sf-radius-lg: {BORDERS['radius_lg']};
        --sf-radius-xl: {BORDERS['radius_xl']};
        --sf-radius-full: {BORDERS['radius_full']};

        /* Shadows */
        --sf-shadow-sm: {SHADOWS['shadow_sm']};
        --sf-shadow-md: {SHADOWS['shadow_md']};
        --sf-shadow-lg: {SHADOWS['shadow_lg']};

        /* Theme-dependent (Light Mode Default) */
        --sf-bg-primary: {COLORS['white']};
        --sf-bg-secondary: {COLORS['gray_lighter']};
        --sf-bg-tertiary: {COLORS['gray_light']};
        --sf-text-primary: {COLORS['midnight']};
        --sf-text-secondary: {COLORS['gray_dark']};
        --sf-text-tertiary: {COLORS['gray_medium']};
        --sf-border-color: {COLORS['gray_light']};
    }}
    """

    # Add dark mode overrides
    if dark_mode:
        css += f"""
        :root {{
            --sf-bg-primary: {DARK_COLORS['bg_primary']};
            --sf-bg-secondary: {DARK_COLORS['bg_secondary']};
            --sf-bg-tertiary: {DARK_COLORS['bg_tertiary']};
            --sf-text-primary: {DARK_COLORS['text_primary']};
            --sf-text-secondary: {DARK_COLORS['text_secondary']};
            --sf-text-tertiary: {DARK_COLORS['text_tertiary']};
            --sf-border-color: {DARK_COLORS['border_color']};
        }}
        """

    return css


def get_component_css() -> str:
    """Generate CSS for Snowflake-styled components."""
    return """
    /* Typography - Strict Snowflake Compliance */
    /* Exclude Material Icons (data-testid="stIconMaterial") from font override */
    body, .stApp, .stMarkdown, p, div {
        font-family: var(--sf-font-primary) !important;
    }

    /* Apply font to spans but NOT icon spans */
    span:not([data-testid="stIconMaterial"]):not([class*="material"]):not(.material-icons) {
        font-family: var(--sf-font-primary) !important;
    }

    code, pre, .stCode {
        font-family: var(--sf-font-mono) !important;
    }

    h1 {
        font-size: var(--sf-text-4xl) !important;
        font-weight: var(--sf-font-bold) !important;
        color: var(--sf-midnight) !important;
    }

    h2 {
        font-size: var(--sf-text-3xl) !important;
        font-weight: var(--sf-font-bold) !important;
        color: var(--sf-midnight) !important;
    }

    h3 {
        font-size: var(--sf-text-2xl) !important;
        font-weight: var(--sf-font-semibold) !important;
        color: var(--sf-midnight) !important;
    }

    h4 {
        font-size: var(--sf-text-xl) !important;
        font-weight: var(--sf-font-semibold) !important;
        color: var(--sf-text-primary) !important;
    }

    /* Buttons - Full Snowflake Replacement */
    .stButton > button[kind="primary"],
    .stDownloadButton > button {
        background-color: var(--sf-blue) !important;
        color: var(--sf-white) !important;
        border: 2px solid var(--sf-blue) !important;
        border-radius: var(--sf-radius-md) !important;
        font-weight: var(--sf-font-bold) !important;
        text-transform: uppercase !important;
        letter-spacing: 0.02em !important;
        padding: var(--sf-space-2) var(--sf-space-4) !important;
        transition: all 0.2s ease !important;
    }

    .stButton > button[kind="primary"]:hover,
    .stDownloadButton > button:hover {
        background-color: var(--sf-mid-blue) !important;
        border-color: var(--sf-mid-blue) !important;
        box-shadow: var(--sf-shadow-md) !important;
    }

    .stButton > button[kind="secondary"] {
        background-color: transparent !important;
        color: var(--sf-blue) !important;
        border: 2px solid var(--sf-blue) !important;
        border-radius: var(--sf-radius-md) !important;
        font-weight: var(--sf-font-bold) !important;
    }

    .stButton > button[kind="secondary"]:hover {
        background-color: var(--sf-hover) !important;
    }

    /* Cards/Expanders - Snowflake Accent Border */
    .stExpander {
        background-color: var(--sf-bg-primary) !important;
        border: 1px solid var(--sf-border-color) !important;
        border-left: 4px solid var(--sf-blue) !important;
        border-radius: var(--sf-radius-lg) !important;
        box-shadow: var(--sf-shadow-sm) !important;
    }

    .stExpander:hover {
        box-shadow: var(--sf-shadow-md) !important;
    }

    .stExpander [data-testid="stExpanderToggleIcon"] {
        color: var(--sf-blue) !important;
    }

    /* Alerts - Full Snowflake Style */
    div[data-testid="stAlert"] {
        border-radius: var(--sf-radius-md) !important;
        border-left-width: 4px !important;
        border-left-style: solid !important;
    }

    div[data-testid="stAlert"][data-baseweb*="info"],
    div[data-testid="stAlert"]:has([data-testid="stAlertIcon-info"]) {
        background-color: var(--sf-info-light) !important;
        border-left-color: var(--sf-info) !important;
    }

    div[data-testid="stAlert"][data-baseweb*="success"],
    div[data-testid="stAlert"]:has([data-testid="stAlertIcon-success"]) {
        background-color: var(--sf-success-light) !important;
        border-left-color: var(--sf-success) !important;
    }

    div[data-testid="stAlert"][data-baseweb*="warning"],
    div[data-testid="stAlert"]:has([data-testid="stAlertIcon-warning"]) {
        background-color: var(--sf-warning-light) !important;
        border-left-color: var(--sf-warning) !important;
    }

    div[data-testid="stAlert"][data-baseweb*="error"],
    div[data-testid="stAlert"]:has([data-testid="stAlertIcon-error"]) {
        background-color: var(--sf-error-light) !important;
        border-left-color: var(--sf-error) !important;
    }

    /* Progress Steps - Snowflake Colors */
    .step-complete {
        background: var(--sf-success-light);
        border-left: 4px solid var(--sf-success);
        padding: var(--sf-space-2) var(--sf-space-4);
        border-radius: var(--sf-radius-sm);
        margin: var(--sf-space-1) 0;
    }

    .step-current {
        background: var(--sf-info-light);
        border-left: 4px solid var(--sf-blue);
        padding: var(--sf-space-2) var(--sf-space-4);
        border-radius: var(--sf-radius-sm);
        margin: var(--sf-space-1) 0;
        font-weight: var(--sf-font-medium);
    }

    .step-pending {
        background: var(--sf-bg-secondary);
        border-left: 4px solid var(--sf-gray-light);
        padding: var(--sf-space-2) var(--sf-space-4);
        border-radius: var(--sf-radius-sm);
        margin: var(--sf-space-1) 0;
        color: var(--sf-text-secondary);
    }

    /* Scrollable tabs */
    .stTabs [data-baseweb="tab-list"] {
        overflow-x: auto;
        overflow-y: hidden;
        flex-wrap: nowrap;
        scrollbar-width: thin;
        scrollbar-color: var(--sf-blue) var(--sf-bg-secondary);
        padding-bottom: 4px;
    }

    .stTabs [data-baseweb="tab-list"]::-webkit-scrollbar {
        height: 6px;
    }

    .stTabs [data-baseweb="tab-list"]::-webkit-scrollbar-track {
        background: var(--sf-bg-secondary);
        border-radius: 3px;
    }

    .stTabs [data-baseweb="tab-list"]::-webkit-scrollbar-thumb {
        background: var(--sf-blue);
        border-radius: 3px;
    }

    .stTabs [data-baseweb="tab"] {
        white-space: nowrap;
        flex-shrink: 0;
    }

    /* Select boxes and inputs */
    .stSelectbox [data-baseweb="select"] > div {
        border-color: var(--sf-border-color) !important;
        border-radius: var(--sf-radius-md) !important;
    }

    .stSelectbox [data-baseweb="select"] > div:focus-within {
        border-color: var(--sf-blue) !important;
        box-shadow: 0 0 0 1px var(--sf-blue) !important;
    }

    /* Multiselect tags - Snowflake Blue */
    .stMultiSelect [data-baseweb="tag"] {
        background-color: var(--sf-blue) !important;
        border-radius: var(--sf-radius-md) !important;
    }

    .stMultiSelect [data-baseweb="tag"] span {
        color: var(--sf-white) !important;
    }

    .stMultiSelect [data-baseweb="tag"] [data-baseweb="tag-action"] {
        color: var(--sf-white) !important;
    }

    .stMultiSelect [data-baseweb="tag"]:hover {
        background-color: var(--sf-mid-blue) !important;
    }

    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background-color: var(--sf-bg-secondary) !important;
        min-width: 24rem !important;
    }

    section[data-testid="stSidebar"] .stMarkdown {
        color: var(--sf-text-primary) !important;
    }
    """


def get_dark_mode_css() -> str:
    """Generate CSS overrides for dark mode."""
    return f"""
    /* Dark Mode Overrides */
    [data-theme="dark"] {{
        --sf-bg-primary: {DARK_COLORS['bg_primary']};
        --sf-bg-secondary: {DARK_COLORS['bg_secondary']};
        --sf-bg-tertiary: {DARK_COLORS['bg_tertiary']};
        --sf-text-primary: {DARK_COLORS['text_primary']};
        --sf-text-secondary: {DARK_COLORS['text_secondary']};
        --sf-text-tertiary: {DARK_COLORS['text_tertiary']};
        --sf-border-color: {DARK_COLORS['border_color']};
    }}

    [data-theme="dark"] body,
    [data-theme="dark"] .stApp {{
        background-color: var(--sf-bg-primary) !important;
        color: var(--sf-text-primary) !important;
    }}

    [data-theme="dark"] h1,
    [data-theme="dark"] h2,
    [data-theme="dark"] h3,
    [data-theme="dark"] h4 {{
        color: var(--sf-text-primary) !important;
    }}

    [data-theme="dark"] .stExpander {{
        background-color: var(--sf-bg-secondary) !important;
        border-color: var(--sf-border-color) !important;
    }}

    [data-theme="dark"] section[data-testid="stSidebar"] {{
        background-color: var(--sf-bg-secondary) !important;
    }}

    [data-theme="dark"] .stSelectbox [data-baseweb="select"] > div {{
        background-color: var(--sf-bg-tertiary) !important;
        border-color: var(--sf-border-color) !important;
        color: var(--sf-text-primary) !important;
    }}
    """


def get_full_theme_css(dark_mode: bool = False) -> str:
    """Get complete theme CSS including variables and components."""
    return get_css_variables(dark_mode) + get_component_css() + get_dark_mode_css()


# =============================================================================
# SVG ICON HELPERS
# =============================================================================

from pathlib import Path
import re

# Icon name to file mapping
ICONS = {
    "connected": "connected.svg",
    "analytics": "analytics.svg",
    "verified": "verified.svg",
    "data_engineering": "migration_tools.svg",  # Design Data Model page
    "cloud": "icon_database_013.png",  # Create Semantic View page
    "rocket": "rocket.svg",
    "code": "code.svg",
    "docs": "docs.svg",
    "copy": "copy_icon.svg",
    "cube": "cube.svg",
    "table": "table.svg",
    "view": "view.svg",
    "snowflake": "snowflake.svg",
    "select": "select.svg",
    "download": "download.svg",
    "lock": "lock.svg",
    "checkmark": "checkmark.svg",
    "plus": "plus.svg",
    "database": "database.svg",
    "schema": "schema.svg",
}


def get_svg_icon(icon_name: str, size: int = 24, color: str = None) -> str:
    """
    Load and return an icon (SVG or PNG) as a base64-encoded img tag.

    Args:
        icon_name: Name of the icon (e.g., 'connected', 'rocket')
        size: Size in pixels (default 24)
        color: Optional color override (hex code like '#29B5E8') - only works for SVG

    Returns:
        HTML img tag with base64-encoded image, or empty string if icon not found
    """
    import base64

    if icon_name not in ICONS:
        return ""

    img_dir = Path(__file__).parent.parent / "img"
    icon_path = img_dir / ICONS[icon_name]

    if not icon_path.exists():
        return ""

    try:
        # Handle PNG files
        if icon_path.suffix.lower() == '.png':
            png_bytes = icon_path.read_bytes()
            b64_png = base64.b64encode(png_bytes).decode('utf-8')
            return f'<img src="data:image/png;base64,{b64_png}" width="{size}" height="{size}" style="vertical-align: middle; display: inline-block;" />'

        # Handle SVG files
        svg_content = icon_path.read_text(encoding="utf-8")

        # Normalize spaces in svg tag
        svg_content = re.sub(r'<svg\s+', '<svg ', svg_content)

        # Check if width/height attributes exist
        has_width = 'width="' in svg_content
        has_height = 'height="' in svg_content

        if has_width:
            svg_content = re.sub(r'width="[^"]*"', f'width="{size}"', svg_content)
        if has_height:
            svg_content = re.sub(r'height="[^"]*"', f'height="{size}"', svg_content)

        # If no width/height, add them to the svg tag
        if not has_width or not has_height:
            svg_content = re.sub(
                r'<svg ',
                f'<svg width="{size}" height="{size}" ',
                svg_content
            )

        # Override fill color if specified
        if color:
            svg_content = re.sub(
                r'fill="#[0-9A-Fa-f]{6}"',
                f'fill="{color}"',
                svg_content
            )

        # Encode as base64 data URL for reliable rendering in Streamlit
        svg_bytes = svg_content.encode('utf-8')
        b64_svg = base64.b64encode(svg_bytes).decode('utf-8')

        return f'<img src="data:image/svg+xml;base64,{b64_svg}" width="{size}" height="{size}" style="vertical-align: middle; display: inline-block;" />'
    except Exception as e:
        return ""


def icon_header(icon_name: str, text: str, size: int = 28, color: str = None) -> str:
    """
    Create a header with an inline SVG icon.

    Args:
        icon_name: Name of the icon
        text: Header text
        size: Icon size in pixels (default 28)
        color: Optional color override

    Returns:
        HTML string for use with st.markdown(unsafe_allow_html=True)
    """
    icon_svg = get_svg_icon(icon_name, size, color)
    return f'{icon_svg} {text}'


def icon_button_label(icon_name: str, text: str, size: int = 18, color: str = None) -> str:
    """
    Create a button label with an inline SVG icon.

    Args:
        icon_name: Name of the icon
        text: Button text
        size: Icon size in pixels (default 18)
        color: Optional color override

    Returns:
        HTML string for button label
    """
    icon_svg = get_svg_icon(icon_name, size, color)
    return f'{icon_svg} {text}'
