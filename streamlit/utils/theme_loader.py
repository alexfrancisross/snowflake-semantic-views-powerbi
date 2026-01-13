_B=False
_A=True
from pathlib import Path
import streamlit as st
from.snowflake_theme import get_full_theme_css
from.tooltips import inject_tooltip_css,inject_skeleton_css
STATIC_DIR=Path(__file__).parent.parent/'static'
STYLES_DIR=STATIC_DIR/'styles'
SCRIPTS_DIR=STATIC_DIR/'scripts'
def _load_css_file(filename):
	A=STYLES_DIR/filename
	if A.exists():return A.read_text(encoding='utf-8')
	return''
def get_main_css():return _load_css_file('main.css')
def inject_theme_css(dark_mode=_B):A=get_full_theme_css(dark_mode);st.markdown(f"<style>{A}</style>",unsafe_allow_html=_A)
def inject_main_css():
	if st.session_state.get('_main_css_injected'):return
	A=get_main_css()
	if A:st.markdown(f"<style>{A}</style>",unsafe_allow_html=_A)
	st.session_state._main_css_injected=_A
def inject_all_styles(dark_mode=_B):
	A=dark_mode;inject_theme_css(A);inject_main_css();inject_tooltip_css();inject_skeleton_css()
	if A:st.markdown("<script>document.documentElement.setAttribute('data-theme', 'dark');</script>",unsafe_allow_html=_A)
	else:st.markdown("<script>document.documentElement.removeAttribute('data-theme');</script>",unsafe_allow_html=_A)
def _load_js_file(filename):
	A=SCRIPTS_DIR/filename
	if A.exists():return A.read_text(encoding='utf-8')
	return''
def inject_expander_state_js():
	if st.session_state.get('_expander_js_injected'):return
	A=_load_js_file('expander-state.js')
	if A:st.markdown(f"<script>{A}</script>",unsafe_allow_html=_A)
	else:_inject_expander_state_js_inline()
	st.session_state._expander_js_injected=_A
def _inject_expander_state_js_inline():st.markdown('\n    <script>\n    (function() {\n        const STORAGE_KEY = \'pbi_expander_states_v2\';\n        let isApplying = false;\n\n        function getStoredStates() {\n            try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || \'{}\'); }\n            catch (e) { return {}; }\n        }\n\n        function saveState(key, isOpen) {\n            if (isApplying) return;\n            const states = getStoredStates();\n            states[key] = isOpen;\n            localStorage.setItem(STORAGE_KEY, JSON.stringify(states));\n        }\n\n        function getExpanderKey(details) {\n            const summary = details.querySelector(\'summary\');\n            if (!summary) return null;\n            let text = summary.textContent.trim().replace(/^[^A-Za-z]+/, \'\');\n            const match = text.match(/^([A-Za-z][A-Za-z\\s\\-]+?)(?:\\s*[\\(\\[0-9]|$)/);\n            return match ? match[1].trim() : text.substring(0, 20).trim();\n        }\n\n        function applyStoredStates() {\n            isApplying = true;\n            const states = getStoredStates();\n            document.querySelectorAll(\'details[data-testid="stExpander"]\').forEach(d => {\n                const key = getExpanderKey(d);\n                if (key && states.hasOwnProperty(key) && d.open !== states[key]) {\n                    d.open = states[key];\n                }\n            });\n            isApplying = false;\n        }\n\n        let timeout = null;\n        function debouncedApply() {\n            if (timeout) clearTimeout(timeout);\n            timeout = setTimeout(applyStoredStates, 100);\n        }\n\n        document.addEventListener(\'toggle\', e => {\n            if (e.target.matches(\'details[data-testid="stExpander"]\')) {\n                const key = getExpanderKey(e.target);\n                if (key) saveState(key, e.target.open);\n            }\n        }, true);\n\n        debouncedApply();\n        new MutationObserver(m => { if (m.some(x => x.addedNodes.length)) debouncedApply(); })\n            .observe(document.body, { childList: true, subtree: true });\n    })();\n    </script>\n    ',unsafe_allow_html=_A)
def inject_pbi_capitalization_fix():
	if st.session_state.get('_pbi_fix_injected'):return
	st.markdown('\n    <script>\n    (function() {\n        function fixCapitalization() {\n            const elements = document.querySelectorAll(\n                \'h1, h2, h3, .stMarkdown p, span[data-testid="stWidgetLabel"]\'\n            );\n            elements.forEach(function(el) {\n                if (el.textContent.includes(\'Power BI\') ||\n                    el.textContent.includes(\'Power Bi\') ||\n                    el.textContent.includes(\'POWER BI\')) {\n                    el.innerHTML = el.innerHTML\n                        .replace(/Power Bi/g, \'Power BI\')\n                        .replace(/POWER BI/g, \'Power BI\');\n                }\n            });\n        }\n\n        // Run on load and after Streamlit updates\n        fixCapitalization();\n        const observer = new MutationObserver(function() {\n            fixCapitalization();\n        });\n        observer.observe(document.body, { childList: true, subtree: true });\n    })();\n    </script>\n    ',unsafe_allow_html=_A);st.session_state._pbi_fix_injected=_A
def inject_scripts():inject_expander_state_js();inject_pbi_capitalization_fix()
def initialize_theme(dark_mode=None):
	A=dark_mode
	if A is None:A=st.session_state.get('dark_mode',_B)
	inject_all_styles(A);inject_scripts()