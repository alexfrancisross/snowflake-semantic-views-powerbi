_M='granularity'
_L='cardinality'
_K='fan_out'
_J='import'
_I='directquery'
_H='metric'
_G='dimension'
_F='semantic_view'
_E='utf-8'
_D='loading_spinner.gif'
_C='img'
_B='Loading...'
_A=True
import streamlit as st,streamlit.components.v1 as components,html,uuid
TERM_DEFINITIONS={_F:'A Snowflake object that defines metrics and dimensions for analytical queries. It pre-defines how data should be aggregated, ensuring consistent calculations across all reports.',_G:'A categorical attribute used to group or filter data (e.g., Region, Product Category, Date). Dimensions provide context for metrics and appear in rows, columns, or filters in reports.',_H:'A pre-aggregated numeric measure defined in a semantic view (e.g., Total Sales, Avg Order Value). Metrics are automatically calculated by Snowflake when queried.','fact':'A raw numeric value at the detail level (e.g., individual order amounts). Unlike metrics, facts are not pre-aggregated and require explicit aggregation in reports.',_I:'A Power BI connection mode where data stays in Snowflake and queries run live. Ideal for large datasets and real-time reporting, but requires good query performance.',_J:"A Power BI connection mode where data is loaded into Power BI's in-memory engine. Faster report interactions but requires periodic refresh and uses local memory.",_K:'A data modeling issue where joining tables causes row multiplication. Occurs in many-to-many relationships and can lead to inflated measures (double counting).',_L:'The relationship type between tables: One-to-Many (1:N), Many-to-One (N:1), or Many-to-Many (M:N). Affects how Power BI aggregates data across related tables.',_M:'The level of detail in data (e.g., daily vs monthly, order line vs order header). In semantic views, metrics must be at equal or higher granularity than dimensions.','bridge_table':'An intermediate table that connects two tables in a many-to-many relationship. Contains only the keys from both tables, resolving fan-out issues.','role_playing':'When a single dimension table is used multiple times with different meanings (e.g., Date table used as Order Date and Ship Date). Requires separate relationships.','star_schema':'A data model design with a central fact table connected to multiple dimension tables. The simplest and most efficient pattern for analytical queries.','snowflake_schema':'A variation of star schema where dimension tables are normalized into sub-dimensions. More complex but can save storage for large dimension hierarchies.'}
TOOLTIP_CSS='\n<style>\n.ux-tooltip {\n    position: relative;\n    display: inline;\n    border-bottom: 1px dotted #11567F;\n    cursor: help;\n    color: inherit;\n}\n.ux-tooltip:hover {\n    border-bottom-color: #29B5E8;\n}\n/* Native tooltip styling via title attribute */\n.ux-tooltip[title] {\n    text-decoration: none;\n}\n</style>\n'
def inject_tooltip_css():st.markdown(TOOLTIP_CSS,unsafe_allow_html=_A)
def term_with_tooltip(term,display_text=None):
	B=display_text;A=term;C=TERM_DEFINITIONS.get(A.lower(),'')
	if not C:return B or A
	D=B or A.replace('_',' ').title();return f'<span class="ux-tooltip" title="{C}">{D}</span>'
def render_term(term,display_text=None):A=term_with_tooltip(term,display_text);st.markdown(A,unsafe_allow_html=_A)
def tooltip_label(term,prefix='',suffix=''):A=term_with_tooltip(term);return f"{prefix}{A}{suffix}"
def dimensions_label():return term_with_tooltip(_G,'Dimensions')
def metrics_label():return term_with_tooltip(_H,'Metrics')
def facts_label():return term_with_tooltip('fact','Facts')
def directquery_label():return term_with_tooltip(_I,'DirectQuery')
def import_label():return term_with_tooltip(_J,'Import')
def semantic_view_label():return term_with_tooltip(_F,'Semantic View')
def fan_out_label():return term_with_tooltip(_K,'Fan-out')
def cardinality_label():return term_with_tooltip(_L,'Cardinality')
def granularity_label():return term_with_tooltip(_M,'Granularity')
COPY_BUTTON_CSS="\n<style>\n.ux-code-container {\n    position: relative;\n    margin: 8px 0;\n}\n.ux-copy-btn {\n    position: absolute;\n    top: 8px;\n    right: 8px;\n    padding: 4px 12px;\n    background: #29B5E8;\n    color: white;\n    border: none;\n    border-radius: 8px;\n    cursor: pointer;\n    font-size: 12px;\n    font-weight: 600;\n    z-index: 10;\n    transition: background 0.2s;\n    text-transform: uppercase;\n    letter-spacing: 0.02em;\n}\n.ux-copy-btn:hover {\n    background: #11567F;\n}\n.ux-copy-btn.copied {\n    background: #34C759;\n}\n.ux-code-block {\n    background: #1e1e1e;\n    color: #d4d4d4;\n    padding: 12px;\n    padding-top: 40px;\n    border-radius: 12px;\n    overflow-x: auto;\n    font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Roboto Mono', monospace;\n    font-size: 13px;\n    line-height: 1.5;\n    white-space: pre-wrap;\n    word-wrap: break-word;\n}\n</style>\n"
def inject_copy_button_css():
	if st.session_state.get('_copy_css_injected'):return
	st.markdown(COPY_BUTTON_CSS,unsafe_allow_html=_A);st.session_state._copy_css_injected=_A
def code_with_copy(code,language='sql',key=None):A=key or f"code_{uuid.uuid4().hex[:8]}";B=html.escape(code);C=f"""
    <div class=\"ux-code-container\">
        <button class=\"ux-copy-btn\" onclick=\"copyCode_{A}(this)\" title=\"Copy to clipboard\">
            Copy
        </button>
        <pre class=\"ux-code-block\"><code>{B}</code></pre>
    </div>
    <script>
    function copyCode_{A}(btn) {{
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
    """;inject_copy_button_css();st.markdown(C,unsafe_allow_html=_A)
SKELETON_CSS='\n<style>\n.ux-skeleton {\n    background: linear-gradient(90deg, #F5F5F5 25%, #E5E5E5 50%, #F5F5F5 75%);\n    background-size: 200% 100%;\n    animation: ux-shimmer 1.5s infinite;\n    border-radius: 8px;\n}\n@keyframes ux-shimmer {\n    0% { background-position: 200% 0; }\n    100% { background-position: -200% 0; }\n}\n.ux-skeleton-text {\n    height: 16px;\n    margin: 8px 0;\n}\n.ux-skeleton-title {\n    height: 24px;\n    width: 40%;\n    margin: 12px 0;\n}\n.ux-skeleton-card {\n    padding: 16px;\n    border: 1px solid #E5E5E5;\n    border-left: 4px solid #29B5E8;\n    border-radius: 12px;\n    margin: 8px 0;\n}\n.ux-skeleton-row {\n    display: flex;\n    gap: 12px;\n    margin: 8px 0;\n}\n.ux-skeleton-tree-item {\n    height: 32px;\n    margin: 4px 0;\n}\n</style>\n'
def inject_skeleton_css():
	if st.session_state.get('_skeleton_css_injected'):return
	st.markdown(SKELETON_CSS,unsafe_allow_html=_A);st.session_state._skeleton_css_injected=_A
def show_skeleton_text(lines=3,width_percent=100):
	A=width_percent;inject_skeleton_css();B=[]
	for C in range(lines):D=A-C*10 if C<3 else A-20;B.append(f'<div class="ux-skeleton ux-skeleton-text" style="width: {D}%;"></div>')
	st.markdown('\n'.join(B),unsafe_allow_html=_A)
def show_skeleton_tree(items=5):
	inject_skeleton_css();A=[]
	for C in range(items):B=C%3*20;D=100-B-20;A.append(f'<div class="ux-skeleton ux-skeleton-tree-item" style="width: {D}%; margin-left: {B}px;"></div>')
	st.markdown('\n'.join(A),unsafe_allow_html=_A)
def show_skeleton_card(title=_A,lines=2):
	inject_skeleton_css();A=[]
	if title:A.append('<div class="ux-skeleton ux-skeleton-title"></div>')
	for B in range(lines):C=90-B*15;A.append(f'<div class="ux-skeleton ux-skeleton-text" style="width: {C}%;"></div>')
	st.markdown(f'<div class="ux-skeleton-card">{"".join(A)}</div>',unsafe_allow_html=_A)
def show_skeleton_progress(message=_B):inject_skeleton_css();A=f'''
    <div style="display: flex; align-items: center; gap: 12px; padding: 12px; background: #F5F5F5; border-radius: 12px; border-left: 4px solid #29B5E8; margin: 8px 0;">
        <div class="ux-skeleton" style="width: 24px; height: 24px; border-radius: 50%;"></div>
        <div style="flex: 1;">
            <div style="color: #5B5B5B; font-size: 14px; margin-bottom: 8px;">{html.escape(message)}</div>
            <div class="ux-skeleton ux-skeleton-text" style="width: 60%;"></div>
        </div>
    </div>
    ''';st.markdown(A,unsafe_allow_html=_A)
def show_loading_spinner(message=_B,size=48):
	A=size;import base64 as D;from pathlib import Path;B=Path(__file__).parent.parent/_C/_D
	if B.exists():E=D.b64encode(B.read_bytes()).decode(_E);C=f'<img src="data:image/gif;base64,{E}" width="{A}" height="{A}" />'
	else:C=f'<div class="ux-skeleton" style="width: {A}px; height: {A}px; border-radius: 50%;"></div>';inject_skeleton_css()
	F=f'''
    <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 24px; gap: 16px;">
        {C}
        <div style="color: #5B5B5B; font-size: 14px; text-align: center;">{html.escape(message)}</div>
    </div>
    ''';st.markdown(F,unsafe_allow_html=_A)
def show_loading_inline(message=_B,size=24):
	A=size;import base64 as D;from pathlib import Path;B=Path(__file__).parent.parent/_C/_D
	if B.exists():E=D.b64encode(B.read_bytes()).decode(_E);C=f'<img src="data:image/gif;base64,{E}" width="{A}" height="{A}" style="vertical-align: middle;" />'
	else:C=f'<div class="ux-skeleton" style="width: {A}px; height: {A}px; border-radius: 50%; display: inline-block;"></div>';inject_skeleton_css()
	F=f'''
    <div style="display: flex; align-items: center; gap: 12px; padding: 12px; background: #F5F5F5; border-radius: 12px; border-left: 4px solid #29B5E8; margin: 8px 0;">
        {C}
        <span style="color: #5B5B5B; font-size: 14px;">{html.escape(message)}</span>
    </div>
    ''';st.markdown(F,unsafe_allow_html=_A)
from contextlib import contextmanager
@contextmanager
def snowflake_spinner(message=_B,size=32):
	A=size;import base64 as E;from pathlib import Path;B=st.empty();C=Path(__file__).parent.parent/_C/_D
	if C.exists():F=E.b64encode(C.read_bytes()).decode(_E);D=f'<img src="data:image/gif;base64,{F}" width="{A}" height="{A}" style="vertical-align: middle;" />'
	else:inject_skeleton_css();D=f'<div class="ux-skeleton" style="width: {A}px; height: {A}px; border-radius: 50%; display: inline-block;"></div>'
	G=f'''
    <div style="display: flex; align-items: center; gap: 12px; padding: 12px; background: #F5F5F5; border-radius: 12px; border-left: 4px solid #29B5E8; margin: 8px 0;">
        {D}
        <span style="color: #5B5B5B; font-size: 14px;">{html.escape(message)}</span>
    </div>
    '''
	try:B.markdown(G,unsafe_allow_html=_A);yield
	finally:B.empty()