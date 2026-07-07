"""
Page modules for the Power BI Semantic Model Generator wizard.

Each page represents a step in the wizard workflow:
- step_select: Browse and select Snowflake objects
- step_review: Review selected objects and metadata
- step_model: Configure data model relationships
- step_semantic: Create/configure semantic views
- step_generate: Generate and download output files

Usage:
    from pages import render_current_step, get_page_by_step

    # Render the current wizard step
    render_current_step(session, app_state)

    # Get a specific page
    page = get_page_by_step(step_index)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

import streamlit as st

from utils.config import CONFIG, WIZARD_STEPS, get_wizard_step_by_index
from utils.logging_config import get_logger
from utils.error_handling import show_error

if TYPE_CHECKING:
    from session_manager import AppState

logger = get_logger(__name__)


# =============================================================================
# BASE PAGE CLASS
# =============================================================================

@dataclass
class PageContext:
    """Context passed to page render methods.

    Attributes:
        session: Snowflake session for queries
        app_state: Current application state
        step_index: Current wizard step index
    """
    session: Any
    app_state: "AppState"
    step_index: int


class BasePage(ABC):
    """Abstract base class for wizard pages.

    Each wizard step should be implemented as a subclass of BasePage.
    This provides a consistent interface and allows for incremental
    migration from the monolithic streamlit_app.py.
    """

    def __init__(self, step_index: int):
        """Initialize the page.

        Args:
            step_index: The wizard step index (0-4)
        """
        self.step_index = step_index
        self.step_config = get_wizard_step_by_index(step_index)

    @property
    def name(self) -> str:
        """Get the page name."""
        return self.step_config.name if self.step_config else f"Step {self.step_index}"

    @property
    def description(self) -> str:
        """Get the page description."""
        return self.step_config.description if self.step_config else ""

    @property
    def icon(self) -> str:
        """Get the page icon."""
        return self.step_config.icon if self.step_config else "info"

    def render_header(self) -> None:
        """Render the page header with title and description."""
        st.subheader(f"{self.name}")
        if self.description:
            st.caption(self.description)

    def render_navigation_buttons(
        self,
        can_go_back: bool = True,
        can_go_next: bool = True,
        back_label: str = "Back",
        next_label: str = "Next",
        next_disabled: bool = False,
    ) -> tuple[bool, bool]:
        """Render back/next navigation buttons.

        Args:
            can_go_back: Whether to show the back button
            can_go_next: Whether to show the next button
            back_label: Label for back button
            next_label: Label for next button
            next_disabled: Whether next button is disabled

        Returns:
            Tuple of (back_clicked, next_clicked)
        """
        col1, col2, col3 = st.columns([1, 4, 1])

        back_clicked = False
        next_clicked = False

        with col1:
            if can_go_back and self.step_index > 0:
                if st.button(f"← {back_label}", width="stretch"):
                    back_clicked = True
                    self._go_to_step(self.step_index - 1)

        with col3:
            if can_go_next and self.step_index < CONFIG.WIZARD_TOTAL_STEPS - 1:
                if st.button(
                    f"{next_label} ->",
                    type="primary",
                    width="stretch",
                    disabled=next_disabled
                ):
                    next_clicked = True
                    self._go_to_step(self.step_index + 1)

        return back_clicked, next_clicked

    def _go_to_step(self, step: int) -> None:
        """Navigate to a specific wizard step.

        Args:
            step: Target step index
        """
        st.session_state.wizard_step = step
        st.rerun()

    @abstractmethod
    def render(self, context: PageContext) -> None:
        """Render the page content.

        This method should be implemented by each page subclass.

        Args:
            context: Page context with session and state
        """
        pass

    def validate(self, context: PageContext) -> bool:
        """Validate whether the user can proceed to the next step.

        Override this method to add validation logic.

        Args:
            context: Page context with session and state

        Returns:
            True if validation passes, False otherwise
        """
        return True


# =============================================================================
# PAGE REGISTRY
# =============================================================================

# Registry of page classes by step index
_page_registry: dict[int, type[BasePage]] = {}


def register_page(step_index: int):
    """Decorator to register a page class for a step.

    Usage:
        @register_page(0)
        class SelectPage(BasePage):
            ...
    """
    def decorator(cls: type[BasePage]) -> type[BasePage]:
        _page_registry[step_index] = cls
        return cls
    return decorator


def get_page_by_step(step_index: int) -> BasePage | None:
    """Get a page instance for a specific step.

    Args:
        step_index: The wizard step index

    Returns:
        Page instance if registered, None otherwise
    """
    page_cls = _page_registry.get(step_index)
    if page_cls:
        return page_cls(step_index)
    return None


def is_page_implemented(step_index: int) -> bool:
    """Check if a page is implemented (registered).

    Args:
        step_index: The wizard step index

    Returns:
        True if the page has a registered implementation
    """
    return step_index in _page_registry


def render_current_step(session: Any, app_state: "AppState") -> bool:
    """Render the current wizard step.

    This function checks if a page is registered for the current step.
    If so, it renders using the new page system. Otherwise, returns False
    to indicate the caller should use the legacy rendering.

    Args:
        session: Snowflake session
        app_state: Application state

    Returns:
        True if the step was rendered by a registered page, False otherwise
    """
    # Scroll to top of page on step change
    import streamlit.components.v1 as components
    components.html(
        """<script>
        window.parent.document.querySelector('section.main').scrollTo(0, 0);
        </script>""",
        height=0
    )

    # Sync wizard_step from st.session_state (buttons set this) to app_state
    if "wizard_step" in st.session_state:
        app_state.wizard_step = st.session_state.wizard_step

    current_step = app_state.wizard_step

    page = get_page_by_step(current_step)
    # Use INFO level for visibility - this helps debug fallback issues
    logger.info(f"[PAGE_SYSTEM] current_step={current_step}, page={page}, registry_keys={list(_page_registry.keys())}")

    if page is None:
        logger.error(f"[PAGE_SYSTEM] No page registered for step {current_step}! Registry has: {list(_page_registry.keys())}")
        return False

    context = PageContext(
        session=session,
        app_state=app_state,
        step_index=current_step,
    )

    try:
        page.render(context)
        return True
    except Exception as e:
        logger.error(f"Error rendering page {current_step}: {e}", exc_info=True)
        # Store error in session state so fallback can display it
        st.session_state._page_render_error = str(e)
        show_error(
            f"Error rendering wizard step",
            details=str(e),
            suggestion="Try refreshing the page or starting over"
        )
        return False


# =============================================================================
# AUTO-IMPORT PAGE MODULES
# =============================================================================
# Import step modules here to ensure @register_page decorators run
# even when Streamlit reloads (avoids Python import caching issues)

# Wrap imports in try-except to catch import errors that would prevent page registration
try:
    from pages import step_review  # Step 0: Review Selected Objects
    logger.debug("[PAGE_SYSTEM] Successfully imported step_review")
except Exception as e:
    logger.error(f"[PAGE_SYSTEM] Failed to import step_review: {e}", exc_info=True)

try:
    from pages import step_model   # Step 1: Design Data Model
    logger.debug("[PAGE_SYSTEM] Successfully imported step_model")
except Exception as e:
    logger.error(f"[PAGE_SYSTEM] Failed to import step_model: {e}", exc_info=True)

try:
    from pages import step_generate  # Step 2: Generate Output
    logger.debug("[PAGE_SYSTEM] Successfully imported step_generate")
except Exception as e:
    logger.error(f"[PAGE_SYSTEM] Failed to import step_generate: {e}", exc_info=True)

# Log final registry state
logger.info(f"[PAGE_SYSTEM] Final registry after imports: {list(_page_registry.keys())}")


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "BasePage",
    "PageContext",
    "register_page",
    "get_page_by_step",
    "is_page_implemented",
    "render_current_step",
]
