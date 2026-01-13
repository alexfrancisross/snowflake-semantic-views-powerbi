/**
 * Expander State Persistence
 *
 * Persists Streamlit expander (details/summary) open/closed state
 * across page reruns using localStorage.
 *
 * Usage: Inject this script once at app startup via st.markdown()
 */

(function() {
    'use strict';

    const STORAGE_KEY = 'pbi_expander_states_v2';
    let isApplying = false;

    /**
     * Get stored expander states from localStorage
     * @returns {Object} Map of expander keys to boolean (open) states
     */
    function getStoredStates() {
        try {
            return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
        } catch (e) {
            console.warn('[ExpanderState] Failed to parse stored states:', e);
            return {};
        }
    }

    /**
     * Save an expander state to localStorage
     * @param {string} key - Expander identifier
     * @param {boolean} isOpen - Whether expander is open
     */
    function saveState(key, isOpen) {
        if (isApplying) return; // Don't save during apply phase
        try {
            const states = getStoredStates();
            states[key] = isOpen;
            localStorage.setItem(STORAGE_KEY, JSON.stringify(states));
        } catch (e) {
            console.warn('[ExpanderState] Failed to save state:', e);
        }
    }

    /**
     * Extract a stable key from an expander's label
     *
     * Removes dynamic parts like counts and numbers to get a stable identifier.
     * Examples:
     *   "Relationships (0/2 selected)" -> "Relationships"
     *   "Selected Objects (5 objects)" -> "Selected Objects"
     *   "Schema Diagram" -> "Schema Diagram"
     *
     * @param {HTMLDetailsElement} details - The details element
     * @returns {string|null} Stable key or null if extraction fails
     */
    function getExpanderKey(details) {
        const summary = details.querySelector('summary');
        if (!summary) return null;

        let text = summary.textContent.trim();

        // Skip leading non-letter characters (emojis, icons, etc)
        text = text.replace(/^[^A-Za-z]+/, '');

        // Extract just the main label before parentheses or numbers
        const match = text.match(/^([A-Za-z][A-Za-z\s\-]+?)(?:\s*[\(\[0-9]|$)/);
        if (match) {
            return match[1].trim();
        }

        // Fallback: first 20 chars
        return text.substring(0, 20).trim();
    }

    /**
     * Apply stored states to all expanders on the page
     */
    function applyStoredStates() {
        isApplying = true;

        try {
            const states = getStoredStates();
            const expanders = document.querySelectorAll('details[data-testid="stExpander"]');

            expanders.forEach(function(details) {
                const key = getExpanderKey(details);
                if (key && states.hasOwnProperty(key)) {
                    if (details.open !== states[key]) {
                        details.open = states[key];
                    }
                }
            });
        } finally {
            isApplying = false;
        }
    }

    /**
     * Set up event listeners for expander toggle events
     */
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

    // Debounce helper
    let applyTimeout = null;
    function debouncedApply() {
        if (applyTimeout) clearTimeout(applyTimeout);
        applyTimeout = setTimeout(applyStoredStates, 100);
    }

    /**
     * Initialize the expander state persistence
     */
    function init() {
        setupListeners();

        // Apply states after DOM is ready
        debouncedApply();

        // Watch for Streamlit rerenders that add new expanders
        const observer = new MutationObserver(function(mutations) {
            for (const mutation of mutations) {
                if (mutation.addedNodes.length > 0) {
                    debouncedApply();
                    break;
                }
            }
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    }

    // Run when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
