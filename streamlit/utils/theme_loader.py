"""
Theme and Static Asset Loader for the Power BI Semantic Model Generator.

This module centralizes the loading and injection of CSS and JavaScript assets.
It provides functions to inject theme styles, custom CSS, and JavaScript
in a controlled, organized manner.

Usage:
    from theme_loader import inject_all_styles, inject_scripts

    # In your main app:
    inject_all_styles(dark_mode=False)
    inject_scripts()
"""

from pathlib import Path
import streamlit as st

from .snowflake_theme import get_full_theme_css
from .tooltips import inject_tooltip_css, inject_skeleton_css


# =============================================================================
# ASSET PATHS
# =============================================================================

STATIC_DIR = Path(__file__).parent.parent / "static"
STYLES_DIR = STATIC_DIR / "styles"
SCRIPTS_DIR = STATIC_DIR / "scripts"


# =============================================================================
# CSS LOADING
# =============================================================================

def _load_css_file(filename: str) -> str:
    """Load CSS content from a static file.

    Args:
        filename: Name of the CSS file in static/styles/

    Returns:
        CSS content as string, or empty string if file not found
    """
    css_path = STYLES_DIR / filename
    if css_path.exists():
        return css_path.read_text(encoding="utf-8")
    return ""


def get_main_css() -> str:
    """Get the main application CSS.

    Returns:
        Main CSS content
    """
    return _load_css_file("main.css")


def inject_theme_css(dark_mode: bool = False) -> None:
    """Inject the Snowflake Design System theme CSS.

    Args:
        dark_mode: Whether to use dark mode colors
    """
    theme_css = get_full_theme_css(dark_mode)
    st.markdown(f"<style>{theme_css}</style>", unsafe_allow_html=True)


def inject_main_css() -> None:
    """Inject the main application CSS from static file."""
    if st.session_state.get("_main_css_injected"):
        return

    main_css = get_main_css()
    if main_css:
        st.markdown(f"<style>{main_css}</style>", unsafe_allow_html=True)

    st.session_state._main_css_injected = True


def inject_all_styles(dark_mode: bool = False) -> None:
    """Inject all CSS styles in the correct order.

    Order:
    1. Snowflake Design System theme (base)
    2. Main application CSS (app-specific)
    3. Tooltip CSS
    4. Skeleton loading CSS

    Args:
        dark_mode: Whether to use dark mode colors
    """
    # 1. Base theme
    inject_theme_css(dark_mode)

    # 2. Main app CSS
    inject_main_css()

    # 3. Component CSS
    inject_tooltip_css()
    inject_skeleton_css()

    # 4. Dark mode attribute
    if dark_mode:
        st.markdown(
            "<script>document.documentElement.setAttribute('data-theme', 'dark');</script>",
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            "<script>document.documentElement.removeAttribute('data-theme');</script>",
            unsafe_allow_html=True
        )


# =============================================================================
# JAVASCRIPT LOADING
# =============================================================================

def _load_js_file(filename: str) -> str:
    """Load JavaScript content from a static file.

    Args:
        filename: Name of the JS file in static/scripts/

    Returns:
        JavaScript content as string, or empty string if file not found
    """
    js_path = SCRIPTS_DIR / filename
    if js_path.exists():
        return js_path.read_text(encoding="utf-8")
    return ""


def inject_expander_state_js() -> None:
    """Inject JavaScript for expander state persistence.

    Uses session state to prevent duplicate injection.
    """
    if st.session_state.get("_expander_js_injected"):
        return

    js_content = _load_js_file("expander-state.js")
    if js_content:
        st.markdown(f"<script>{js_content}</script>", unsafe_allow_html=True)
    else:
        # Fallback: inline version if file not found
        _inject_expander_state_js_inline()

    st.session_state._expander_js_injected = True


def _inject_expander_state_js_inline() -> None:
    """Fallback: Inject inline expander state JavaScript."""
    st.markdown("""
    <script>
    (function() {
        const STORAGE_KEY = 'pbi_expander_states_v2';
        let isApplying = false;

        function getStoredStates() {
            try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}'); }
            catch (e) { return {}; }
        }

        function saveState(key, isOpen) {
            if (isApplying) return;
            const states = getStoredStates();
            states[key] = isOpen;
            localStorage.setItem(STORAGE_KEY, JSON.stringify(states));
        }

        function getExpanderKey(details) {
            const summary = details.querySelector('summary');
            if (!summary) return null;
            let text = summary.textContent.trim().replace(/^[^A-Za-z]+/, '');
            const match = text.match(/^([A-Za-z][A-Za-z\\s\\-]+?)(?:\\s*[\\(\\[0-9]|$)/);
            return match ? match[1].trim() : text.substring(0, 20).trim();
        }

        function applyStoredStates() {
            isApplying = true;
            const states = getStoredStates();
            document.querySelectorAll('details[data-testid="stExpander"]').forEach(d => {
                const key = getExpanderKey(d);
                if (key && states.hasOwnProperty(key) && d.open !== states[key]) {
                    d.open = states[key];
                }
            });
            isApplying = false;
        }

        let timeout = null;
        function debouncedApply() {
            if (timeout) clearTimeout(timeout);
            timeout = setTimeout(applyStoredStates, 100);
        }

        document.addEventListener('toggle', e => {
            if (e.target.matches('details[data-testid="stExpander"]')) {
                const key = getExpanderKey(e.target);
                if (key) saveState(key, e.target.open);
            }
        }, true);

        debouncedApply();
        new MutationObserver(m => { if (m.some(x => x.addedNodes.length)) debouncedApply(); })
            .observe(document.body, { childList: true, subtree: true });
    })();
    </script>
    """, unsafe_allow_html=True)


def inject_pbi_capitalization_fix() -> None:
    """Inject JavaScript fix for Power BI name capitalization.

    Fixes issue where Power BI capitalizes connector display names incorrectly.
    """
    if st.session_state.get("_pbi_fix_injected"):
        return

    st.markdown("""
    <script>
    (function() {
        function fixCapitalization() {
            const elements = document.querySelectorAll(
                'h1, h2, h3, .stMarkdown p, span[data-testid="stWidgetLabel"]'
            );
            elements.forEach(function(el) {
                if (el.textContent.includes('Power BI') ||
                    el.textContent.includes('Power Bi') ||
                    el.textContent.includes('POWER BI')) {
                    el.innerHTML = el.innerHTML
                        .replace(/Power Bi/g, 'Power BI')
                        .replace(/POWER BI/g, 'Power BI');
                }
            });
        }

        // Run on load and after Streamlit updates
        fixCapitalization();
        const observer = new MutationObserver(function() {
            fixCapitalization();
        });
        observer.observe(document.body, { childList: true, subtree: true });
    })();
    </script>
    """, unsafe_allow_html=True)

    st.session_state._pbi_fix_injected = True


def inject_scripts() -> None:
    """Inject all JavaScript files in the correct order.

    Order:
    1. Expander state persistence
    2. Power BI capitalization fix
    """
    inject_expander_state_js()
    inject_pbi_capitalization_fix()


# =============================================================================
# COMBINED INITIALIZATION
# =============================================================================

def initialize_theme(dark_mode: bool = None) -> None:
    """Initialize all theme assets (CSS and JavaScript).

    This is the main entry point for theme initialization.
    Call this once at the start of your Streamlit app.

    Args:
        dark_mode: Whether to use dark mode. If None, reads from session state.

    Example:
        from theme_loader import initialize_theme

        def main():
            initialize_theme()
            st.title("My App")
            ...
    """
    # Get dark mode from session state if not specified
    if dark_mode is None:
        dark_mode = st.session_state.get("dark_mode", False)

    # Inject all styles
    inject_all_styles(dark_mode)

    # Inject all scripts
    inject_scripts()
