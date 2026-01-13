_V='tree_reset_counter'
_U='selected_objects'
_T='#29B5E8'
_S='search_filter'
_R='cube'
_Q='view'
_P='img'
_O='selected_relationships'
_N='wizard_step'
_M='VIEW'
_L='table'
_K='manual_relationships'
_J='TABLE'
_I='views_metadata'
_H='SEMANTIC_VIEW'
_G='_exec_id'
_F='object'
_E='schema'
_D='database'
_C=None
_B=False
_A=True
import streamlit as st,streamlit_antd_components as sac,pandas as pd,base64
from datetime import datetime
from pathlib import Path
from utils.metadata_fetcher import get_databases,get_schemas,get_all_objects,get_view_metadata,get_metadata_batch_parallel,get_semantic_views,get_tables,SemanticViewMetadata,ObjectInfo,ObjectType,RelationshipMetadata,enrich_relationship_with_cardinality,assess_fan_out_risk,detect_all_relationships,detect_schema_type,identify_base_table,can_have_metrics,can_have_facts,detect_indirect_connections
from utils.tmdl_generator import generate_multi_view_tmdl_project
from utils.zip_packager import create_zip_with_connector,create_connector_only_zip,get_connector_bytes
from utils.pbit_generator import create_pbit_file,collect_all_relationships,detect_ambiguous_paths,detect_role_playing_dimensions
from utils.fan_out_validator import validate_measure_dimension_combinations,detect_relationship_issue_type,RelationshipIssue
from utils.snowflake_ddl_generator import detect_role_playing_dimensions,detect_circular_relationships,execute_ddl,DDLResult,generate_dax_measure
from utils.snowflake_session import get_snowflake_session,get_session_info,is_running_in_snowflake,IN_SNOWFLAKE
from utils.tooltips import inject_tooltip_css,term_with_tooltip,dimensions_label,metrics_label,facts_label,directquery_label,semantic_view_label,fan_out_label,granularity_label,inject_skeleton_css,show_skeleton_tree,show_skeleton_card,show_skeleton_progress,snowflake_spinner
from utils.schema_visualizer import render_schema_visualizer,show_graph_legend,FLOW_AVAILABLE
from utils.snowflake_theme import get_full_theme_css,COLORS,DARK_COLORS,icon_header,get_svg_icon
from utils.ui_helpers import generate_project_name,get_object_icon_key,get_object_icon_html,get_connector_badge_html,display_column_metadata
from utils.config import CONFIG,WIZARD_STEPS,OBJECT_TYPES,get_object_type_config
from utils.session_manager import get_app_state,reset_app_state,migrate_legacy_state,init_session_state as init_app_state,sync_from_legacy,sync_to_legacy
from utils.relationship_suggester import create_manual_relationship
from utils.validation import validate_identifier,validate_semantic_view_name,validate_qualified_name,sanitize_for_display,escape_identifier,build_qualified_name,ValidationResult
from utils.theme_loader import initialize_theme,inject_all_styles,inject_scripts
from utils.logging_config import get_logger,log_user_action,log_performance
from utils.error_handling import handle_error,safe_execute,error_boundary,SnowflakeConnectionError,MetadataFetchError
from pages import render_current_step,is_page_implemented,PageContext
logger=get_logger(__name__)
def inject_custom_css():
	A=st.session_state.get('dark_mode',_B);initialize_theme(A);B=get_full_theme_css(A);st.markdown(f'''
    <style>
    {B}

    /* Reduce top padding in main content area */
    .main .block-container {{
        padding-top: 0 !important;
        margin-top: 0 !important;
    }}

    /* Remove padding from app view container */
    [data-testid="stAppViewContainer"] {{
        padding-top: 0 !important;
    }}

    /* Remove top margin from main section */
    section[data-testid="stMain"] {{
        padding-top: 0 !important;
    }}


    /* Target the main block container */
    [data-testid="stMainBlockContainer"] {{
        padding-top: 0 !important;
        margin-top: 0 !important;
    }}

    /* Logo header alignment */
    .logo-header {{
        display: flex;
        align-items: center;
        gap: 1rem;
        margin-bottom: 1rem;
    }}

    /* Responsive steps/stepper component */
    .stCustomComponentV1 {{
        min-width: 0 !important;
    }}

    /* On smaller screens, allow horizontal scroll for steps */
    @media (max-width: 1200px) {{
        [data-testid="stCustomComponentV1"] {{
            overflow-x: auto !important;
            scrollbar-width: thin;
        }}
        [data-testid="stCustomComponentV1"]::-webkit-scrollbar {{
            height: 4px;
        }}
        [data-testid="stCustomComponentV1"]::-webkit-scrollbar-thumb {{
            background: #29B5E8;
            border-radius: 2px;
        }}
    }}

    /* Selection status card - sticky header above tree */
    .selection-status-card {{
        position: sticky;
        top: 0;
        z-index: 100;
        background: linear-gradient(135deg, #E8F6FA 0%, #F0FAFC 100%);
        border-left: 4px solid #29B5E8;
        border-radius: 6px;
        padding: 12px 16px;
        margin-bottom: 12px;
        font-size: 14px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }}
    </style>
    ''',unsafe_allow_html=_A)
	if A:st.markdown("\n        <script>\n        document.documentElement.setAttribute('data-theme', 'dark');\n        </script>\n        ",unsafe_allow_html=_A)
	else:st.markdown("\n        <script>\n        document.documentElement.removeAttribute('data-theme');\n        </script>\n        ",unsafe_allow_html=_A)
	inject_tooltip_css();inject_skeleton_css();inject_expander_state_js()
def inject_expander_state_js():st.markdown('\n    <script>\n    (function() {\n        const STORAGE_KEY = \'pbi_expander_states_v2\';\n        let isApplying = false;\n\n        // Get stored states from localStorage\n        function getStoredStates() {\n            try {\n                return JSON.parse(localStorage.getItem(STORAGE_KEY) || \'{}\');\n            } catch (e) {\n                return {};\n            }\n        }\n\n        // Save state to localStorage\n        function saveState(key, isOpen) {\n            if (isApplying) return; // Don\'t save during apply phase\n            const states = getStoredStates();\n            states[key] = isOpen;\n            localStorage.setItem(STORAGE_KEY, JSON.stringify(states));\n        }\n\n        // Get stable key from expander label (remove dynamic parts like counts)\n        function getExpanderKey(details) {\n            const summary = details.querySelector(\'summary\');\n            if (!summary) return null;\n\n            let text = summary.textContent.trim();\n            // Skip leading non-letter characters (emojis, icons, etc)\n            text = text.replace(/^[^A-Za-z]+/, \'\');\n            // Extract just the main label before parentheses or numbers\n            // e.g., "Relationships (0/2 selected)" -> "Relationships"\n            // e.g., "Selected Objects (5 objects, 73 columns)" -> "Selected Objects"\n            // e.g., "Schema Diagram" -> "Schema Diagram"\n            const match = text.match(/^([A-Za-z][A-Za-z\\s\\-]+?)(?:\\s*[\\(\\[0-9]|$)/);\n            if (match) {\n                return match[1].trim();\n            }\n            // Fallback: first 20 chars\n            return text.substring(0, 20).trim();\n        }\n\n        // Apply stored states to expanders\n        function applyStoredStates() {\n            isApplying = true;\n            const states = getStoredStates();\n            const expanders = document.querySelectorAll(\'details[data-testid="stExpander"]\');\n\n            expanders.forEach(details => {\n                const key = getExpanderKey(details);\n                if (key && states.hasOwnProperty(key)) {\n                    if (details.open !== states[key]) {\n                        details.open = states[key];\n                    }\n                }\n            });\n            isApplying = false;\n        }\n\n        // Listen for expander toggles\n        function setupListeners() {\n            document.addEventListener(\'toggle\', function(e) {\n                if (e.target.matches(\'details[data-testid="stExpander"]\')) {\n                    const key = getExpanderKey(e.target);\n                    if (key) {\n                        saveState(key, e.target.open);\n                    }\n                }\n            }, true);\n        }\n\n        // Debounce function\n        let applyTimeout = null;\n        function debouncedApply() {\n            if (applyTimeout) clearTimeout(applyTimeout);\n            applyTimeout = setTimeout(applyStoredStates, 100);\n        }\n\n        // Initialize\n        function init() {\n            setupListeners();\n            // Apply states after DOM is ready\n            debouncedApply();\n            // Watch for Streamlit rerenders\n            const observer = new MutationObserver((mutations) => {\n                // Only apply if new expanders were added\n                for (const mutation of mutations) {\n                    if (mutation.addedNodes.length > 0) {\n                        debouncedApply();\n                        break;\n                    }\n                }\n            });\n            observer.observe(document.body, { childList: true, subtree: true });\n        }\n\n        // Run when DOM is ready\n        if (document.readyState === \'loading\') {\n            document.addEventListener(\'DOMContentLoaded\', init);\n        } else {\n            init();\n        }\n    })();\n    </script>\n    ',unsafe_allow_html=_A)
def get_wizard_step():
	if _N not in st.session_state:st.session_state.wizard_step=0
	return st.session_state.wizard_step
def show_progress_indicator():
	L='transparent';K='#d9d9d9';J='#52c41a';F='normal';M=bool(st.session_state.get(_I));N=len(st.session_state.get(_I,[]));O=N<=1 or st.session_state.get(_O)is not _C;G=get_wizard_step();H=[('1. Review Selected Objects',_A),('2. Design Data Model',M),('3. Generate Output',O)];A='<div style="display: flex; justify-content: space-between; align-items: center; margin: 4px 0;">'
	for(E,(P,Q))in enumerate(H):
		R=E==G;I=E<G;S=not Q
		if R:B=_T;C='#E6F7FC';D='600'
		elif I:B=J;C='#f6ffed';D=F
		elif S:B=K;C=L;D=F
		else:B='#666';C=L;D=F
		A+=f'\n        <div style="flex: 1; text-align: center; padding: 8px 12px; border-radius: 4px; background: {C};">\n            <span style="color: {B}; font-weight: {D}; font-size: 14px;">{P}</span>\n        </div>\n        '
		if E<len(H)-1:T=J if I else K;A+=f'<div style="flex: 0.5; height: 2px; background: {T};"></div>'
	A+='</div>';st.markdown(A,unsafe_allow_html=_A)
def load_svg_icon(icon_name):
	B=Path(__file__).parent/_P;A=B/f"{icon_name}.svg"
	if A.exists():C=A.read_text(encoding='utf-8');D=base64.b64encode(C.encode()).decode();return f"data:image/svg+xml;base64,{D}"
	return''
ICON_DATA={_L:load_svg_icon(_L),_Q:load_svg_icon(_Q),_R:load_svg_icon(_R),_D:load_svg_icon(_D),_E:load_svg_icon(_E)}
OBJECT_TYPE_ICONS={_H:_R,_M:_Q,_J:_L}
def get_icon_html(icon_key,size=16):
	A=ICON_DATA.get(icon_key,'')
	if A:return f'<img src="{A}" width="{size}" height="{size}" style="vertical-align: middle; margin-right: 4px;">'
	return''
def init_session_state():
	init_app_state()
	if _N not in st.session_state:st.session_state.wizard_step=0
def toggle_object_selection(database,schema,name,object_type):
	A=database,schema,name,object_type
	if A in st.session_state.selected_objects:st.session_state.selected_objects.remove(A)
	else:st.session_state.selected_objects.append(A)
def is_object_selected(database,schema,name,object_type):return(database,schema,name,object_type)in st.session_state.selected_objects
def matches_search(search_term,database,schema='',obj_name=''):
	A=search_term
	if not A:return _A
	B=f"{database}.{schema}.{obj_name}".upper();return A in B
def build_tree_items(databases,search_term=''):
	D=search_term;L=[];F={}
	for A in databases:
		if D:
			Q=D in A.upper();G=_B
			if A in st.session_state.loaded_schemas:
				for B in st.session_state.loaded_schemas[A]:
					if matches_search(D,A,B):G=_A;break
					E=A,B
					if E in st.session_state.loaded_objects:
						for C in st.session_state.loaded_objects[E]:
							if matches_search(D,A,B,C.name):G=_A;break
			if not Q and not G:continue
		M=A;F[M]=_D,A,_C,_C,_C;H=[]
		if A in st.session_state.loaded_schemas:
			for B in st.session_state.loaded_schemas[A]:
				if D:
					R=matches_search(D,A,B);E=A,B;N=_B
					if E in st.session_state.loaded_objects:
						for C in st.session_state.loaded_objects[E]:
							if matches_search(D,A,B,C.name):N=_A;break
					if not R and not N:continue
				O=f"{A}.{B}";F[O]=_E,A,B,_C,_C;I=[];E=A,B
				if E in st.session_state.loaded_objects:
					for C in st.session_state.loaded_objects[E]:
						if D and not matches_search(D,A,B,C.name):continue
						P=f"{A}.{B}.{C.name}";F[P]=_F,A,B,C.name,C.object_type
						if C.object_type==_H:J=sac.BsIcon(name='box',color='#7254A3');K=sac.Tag('Semantic',color='purple')
						elif C.object_type==_M:J=sac.BsIcon(name='eye',color='#FF9F36');K=sac.Tag('View',color='orange')
						else:J=sac.BsIcon(name=_L,color='#75CDD7');K=sac.Tag('Table',color='cyan')
						I.append(sac.TreeItem(P,icon=J,tag=K))
				else:I.append(sac.TreeItem('⏳ Loading objects...',disabled=_A))
				H.append(sac.TreeItem(O,icon='folder2-open',children=I))
		else:H.append(sac.TreeItem('⏳ Loading schemas...',disabled=_A))
		L.append(sac.TreeItem(M,icon=_D,children=H))
	return L,F
def _clean_tree_session_state():
	if _U in st.session_state:
		E=[]
		for B in st.session_state.selected_objects:
			if B is not _C and isinstance(B,(list,tuple))and len(B)>=4:
				if all(A is not _C for A in B[:4]):E.append(B)
		st.session_state.selected_objects=E
	if'expanded_nodes'in st.session_state:st.session_state.expanded_nodes=[A for A in st.session_state.expanded_nodes if A is not _C and isinstance(A,str)]
	C=[]
	for A in list(st.session_state.keys()):
		if A.startswith('object_tree_'):
			D=st.session_state[A]
			if D is _C:C.append(A)
			elif isinstance(D,list)and any(A is _C for A in D):C.append(A)
	for A in C:del st.session_state[A]
def _get_pending_metadata_count():
	if not st.session_state.selected_objects:return 0
	A={(A.database,A.schema,A.view)for A in st.session_state.views_metadata};B=sum(1 for(B,C,D,E)in st.session_state.selected_objects if(B,C,D)not in A);return B
def _get_spinner_gif_base64():
	import base64 as B;from pathlib import Path;A=Path(__file__).parent/_P/'loading_spinner.gif'
	if A.exists():return B.b64encode(A.read_bytes()).decode('utf-8')
	return''
def _render_status_card_html(selected_count,is_read_only=_B,pending_load_count=0):
	F=pending_load_count;E=is_read_only;A=selected_count
	if A==0:return''
	C=F>0 and not E
	if E:B='<span style="font-size:18px;">🔒</span>';D=f"<strong>{A}</strong> object(s) locked"
	elif C:
		G=_get_spinner_gif_base64()
		if G:B=f'<img src="data:image/gif;base64,{G}" width="20" height="20" style="vertical-align: middle;" />'
		else:B='<span style="font-size:18px;">⏳</span>'
		D=f'<strong>{A}</strong> selected, <strong style="color:#29B5E8">{F}</strong> loading...'
	else:B='<span style="font-size:18px;">✓</span>';D=f"<strong>{A}</strong> object(s) selected"
	H=''
	if C:H='\n        <style>\n            .selection-status-card.loading {\n                border-left-color: #29B5E8 !important;\n                background: linear-gradient(135deg, #E8F6FA 0%, #F0FAFC 100%) !important;\n            }\n        </style>\n        '
	I='selection-status-card loading'if C else'selection-status-card';return f'''
        {H}
        <div class="{I}">
            <span style="margin-right:10px;">{B}</span>
            {D}
        </div>
    '''
def render_selection_status_header(is_read_only=_B,pending_load_count=0):
	C=len(st.session_state.selected_objects);A=st.empty();B=_render_status_card_html(C,is_read_only,pending_load_count)
	if B:A.markdown(B,unsafe_allow_html=_A)
	return A
def update_status_header_loading(placeholder,pending_count):
	B=len(st.session_state.selected_objects);A=_render_status_card_html(B,is_read_only=_B,pending_load_count=pending_count)
	if A:placeholder.markdown(A,unsafe_allow_html=_A)
def _get_pre_selected_labels():
	A=[];D=st.session_state.get(_G,0);logger.debug(f"[EXEC:{D}][PRE_SELECT] selected_objects count: {len(st.session_state.selected_objects)}")
	for B in st.session_state.selected_objects:
		if B is _C or not isinstance(B,(list,tuple))or len(B)<4:continue
		E,F,C,H=B
		if C is not _C and isinstance(C,str):G=f"{E}.{F}.{C}";A.append(G)
	logger.debug(f"[EXEC:{D}][PRE_SELECT] Qualified labels to pass to tree: {len(A)}, first 5: {A[:5]}");return A if A else _C
def _get_open_index():
	_ensure_selected_parents_expanded()
	if not st.session_state.expanded_nodes:return
	A=[A for A in st.session_state.expanded_nodes if A is not _C and isinstance(A,str)];return A if A else _C
def _ensure_selected_parents_expanded():
	if not st.session_state.selected_objects:return
	C=set();D=set()
	for B in st.session_state.selected_objects:
		if B is _C or not isinstance(B,(list,tuple))or len(B)<4:continue
		A,E,G,H=B
		if A:C.add(A)
		if A and E:D.add(f"{A}.{E}")
	for A in C:
		if A not in st.session_state.expanded_nodes:st.session_state.expanded_nodes.append(A)
	for F in D:
		if F not in st.session_state.expanded_nodes:st.session_state.expanded_nodes.append(F)
def _parse_tree_result(result):
	A=result
	if hasattr(A,'selected')and hasattr(A,'expanded'):B=A.selected if isinstance(A.selected,list)else[A.selected]if A.selected else[];C=A.expanded or[]
	else:B=A if isinstance(A,list)else[A]if A else[];C=[]
	B=[A for A in B if A is not _C and not str(A).startswith('⏳')];return B,C
def _sync_expansion_state(expanded,open_index):
	E=open_index;D=expanded;G=st.session_state.get(_G,0);A=set(A for A in D if A is not _C)if D else set();F=set(st.session_state.expanded_nodes)if st.session_state.expanded_nodes else set();B=set(E)if E else set();C=A|B|F;logger.debug(f"[EXEC:{G}][SYNC_EXPAND] tree_returned={len(A)}, passed={len(B)}, saved={len(F)}, merged={len(C)}")
	if A and A!=B:st.session_state.expanded_nodes=list(A|B)
	elif C:st.session_state.expanded_nodes=list(C)
	else:st.session_state.expanded_nodes=[]
def _process_lazy_loading(session,label_map):
	L=label_map;K=session;D=st.session_state.get(_G,0);F=_B;G=list(st.session_state.expanded_nodes or[]);logger.debug(f"[EXEC:{D}][LAZY_LOAD] Processing {len(G)} expanded nodes: {G[:5]}")
	for M in G:
		if M not in L:continue
		C=L[M]
		if C[0]==_D:
			A=C[1]
			if A not in st.session_state.loaded_schemas:
				with snowflake_spinner(f"Loading schemas for {A}..."):
					try:
						H=get_schemas(K,A);st.session_state.loaded_schemas[A]=H;F=_A;logger.debug(f"[EXEC:{D}][LAZY_LOAD] Loaded {len(H)} schemas for {A}")
						for I in H:
							B=f"{A}.{I}"
							if B not in st.session_state.expanded_nodes:st.session_state.expanded_nodes.append(B);logger.debug(f"[EXEC:{D}][LAZY_LOAD] Auto-expanded schema: {B}")
					except Exception as J:st.error(f"Error loading schemas: {J}")
			else:
				for I in st.session_state.loaded_schemas.get(A,[]):
					B=f"{A}.{I}"
					if B not in st.session_state.expanded_nodes:st.session_state.expanded_nodes.append(B)
		elif C[0]==_E:
			A,E=C[1],C[2];N=A,E
			if N not in st.session_state.loaded_objects:
				with snowflake_spinner(f"Loading objects for {E}..."):
					try:O=get_all_objects(K,A,E);st.session_state.loaded_objects[N]=O;F=_A;logger.debug(f"[EXEC:{D}][LAZY_LOAD] Loaded {len(O)} objects for {A}.{E}")
					except Exception as J:st.error(f"Error loading objects: {J}")
	return F
def _process_tree_selections(session,selected,label_map):
	T=selected;S=session;F=label_map;N=_B;logger.debug(f"[PROCESS_SEL] Input: {len(T)} selected items from tree");logger.debug(f"[PROCESS_SEL] Current selected_objects: {len(st.session_state.selected_objects)}");U=set()
	for(E,B)in F.items():
		if B[0]==_F:U.add(B[3])
	logger.debug(f"[PROCESS_SEL] Visible objects in tree: {len(U)}");O=set()
	for E in T:
		if E in F:
			B=F[E]
			if B[0]==_D:O.add(B[1])
			elif B[0]==_F:O.add(B[1])
	logger.debug(f"[PROCESS_SEL] Selected databases: {O}");b=bool(st.session_state.get(_S,'').strip())
	if st.session_state.get('_just_reset',_B):G=[];st.session_state._just_reset=_B;logger.debug('[PROCESS_SEL] Just reset - not preserving any selections')
	else:
		G=[]
		for(A,P,H,Q)in st.session_state.selected_objects:
			c=H not in U
			if b:
				if c:G.append((A,P,H,Q))
			elif c and A in O:G.append((A,P,H,Q))
		logger.debug(f"[PROCESS_SEL] Preserved (hidden, filter_active={b}): {len(G)}")
	I=[]
	for E in T:
		if E not in F:continue
		B=F[E]
		if B[0]==_D:
			A=B[1];V=_B
			if A not in st.session_state.loaded_schemas:
				with snowflake_spinner(f"Loading schemas for {A}..."):
					try:f=get_schemas(S,A);st.session_state.loaded_schemas[A]=f;V=_A
					except Exception as J:st.error(f"Error loading schemas for {A}: {J}");continue
			if A not in st.session_state.expanded_nodes:st.session_state.expanded_nodes.append(A)
			g=st.session_state.loaded_schemas.get(A,[])
			for C in g:
				D=A,C
				if D not in st.session_state.loaded_objects:
					with snowflake_spinner(f"Loading objects for {C}..."):
						try:W=get_all_objects(S,A,C);st.session_state.loaded_objects[D]=W;V=_A
						except Exception as J:st.error(f"Error loading objects for {C}: {J}");continue
				K=f"{A}.{C}"
				if K not in st.session_state.expanded_nodes:st.session_state.expanded_nodes.append(K)
				for L in st.session_state.loaded_objects.get(D,[]):I.append((A,C,L.name,L.object_type))
			if V:N=_A
			continue
		if B[0]==_F:j,A,P,H,Q=B;I.append((A,P,H,Q))
		elif B[0]==_E:
			A=B[1];C=B[2];D=A,C
			if D not in st.session_state.loaded_objects:
				with snowflake_spinner(f"Loading objects for {C}..."):
					try:W=get_all_objects(S,A,C);st.session_state.loaded_objects[D]=W;N=_A
					except Exception as J:st.error(f"Error loading objects for {C}: {J}");continue
				K=f"{A}.{C}"
				if K not in st.session_state.expanded_nodes:st.session_state.expanded_nodes.append(K)
			for L in st.session_state.loaded_objects.get(D,[]):I.append((A,C,L.name,L.object_type))
	h=G+I;d=set();R=[]
	for X in h:
		if X not in d:d.add(X);R.append(X)
	M=st.session_state.get(_G,0);logger.debug(f"[EXEC:{M}][PROCESS_SEL] new_object_selections={len(I)}, unique_selections={len(R)}");Y=set(st.session_state.selected_objects);Z=set(R);e=Y!=Z;i=Z-Y;a=Y-Z;logger.debug(f"[EXEC:{M}][PROCESS_SEL] Changes: added={len(i)}, removed={len(a)}, changed={e}")
	if a:logger.debug(f"[EXEC:{M}][PROCESS_SEL] Removed items: {list(a)[:5]}")
	st.session_state.selected_objects=R;logger.debug(f"[EXEC:{M}][STATE_UPDATE] selected_objects now has {len(st.session_state.selected_objects)} items")
	if e:logger.debug(f"[EXEC:{M}][PROCESS_SEL] Selections changed - setting needs_rerun=True");N=_A
	return N
def _sync_metadata_with_selections(session):
	C=st.session_state.get(_G,0);I=len(st.session_state.views_metadata);D={(A,B,C)for(A,B,C,D)in st.session_state.selected_objects};E={(A.database,A.schema,A.view)for A in st.session_state.views_metadata};logger.debug(f"[EXEC:{C}][METADATA_SYNC] selected_keys={len(D)}, loaded_keys={len(E)}")
	if D:logger.debug(f"[EXEC:{C}][METADATA_SYNC] First 3 selected: {list(D)[:3]}")
	if E:logger.debug(f"[EXEC:{C}][METADATA_SYNC] First 3 loaded: {list(E)[:3]}")
	st.session_state.views_metadata=[A for A in st.session_state.views_metadata if(A.database,A.schema,A.view)in D];J=len(st.session_state.views_metadata)<I;A={A.view for A in st.session_state.views_metadata}
	if _K in st.session_state:st.session_state.manual_relationships=[B for B in st.session_state.manual_relationships if B.from_table in A and B.to_table in A]
	if'bridge_relationships'in st.session_state:st.session_state.bridge_relationships=[B for B in st.session_state.bridge_relationships if B.from_table in A and B.to_table in A]
	if _O in st.session_state and A:K={B for(B,C)in st.session_state.selected_relationships.items()if any(A in B for A in A)};st.session_state.selected_relationships={A:B for(A,B)in st.session_state.selected_relationships.items()if A in K}
	if'active_relationship_choices'in st.session_state and A:st.session_state.active_relationship_choices={B:C for(B,C)in st.session_state.active_relationship_choices.items()if any(A in B for A in A)}
	B=[(A,B,C,D)for(A,B,C,D)in st.session_state.selected_objects if(A,B,C)not in E];F=_B
	if B:
		logger.debug(f"[EXEC:{C}][METADATA_SYNC] Loading {len(B)} objects: {B[:3]}");G=st.session_state.get('_status_header_placeholder')
		if G:update_status_header_loading(G,len(B))
		try:
			with snowflake_spinner(f"Loading metadata for {len(B)} object(s)..."):L=get_metadata_batch_parallel(session,B,max_workers=8);st.session_state.views_metadata.extend(L)
			F=_A;logger.debug(f"[EXEC:{C}][METADATA_SYNC] Loaded {len(B)} objects, total metadata: {len(st.session_state.views_metadata)}")
		except Exception as H:logger.error(f"[EXEC:{C}][METADATA_SYNC] Failed to load metadata: {H}",exc_info=_A);st.error(f"Failed to load metadata for selected objects: {H}")
	return F or J
def render_tree_navigation(session,databases):
	c=databases;T=session;st.markdown(f"### {icon_header('select','Select Objects',size=24)}",unsafe_allow_html=_A)
	@st.fragment
	def A():
		r=st.session_state.get(_N,0);D=r>=2;s=_get_pending_metadata_count();t=render_selection_status_header(D,s);st.session_state._status_header_placeholder=t;_clean_tree_session_state();E=st.text_input('🔍 Filter databases',placeholder='Type to filter by database name...',key=_S).strip().upper();U=st.session_state.get('_prev_search_filter','');K=E!=U;u=K and not E and U;d=K and E;st.session_state._prev_search_filter=E
		if K:logger.debug(f"[TREE_NAV] Filter changed: '{U}' -> '{E}' (cleared={u}, activated={d})")
		if not c:st.warning('No databases found.');return
		L,F=build_tree_items(c,E)
		if not L:st.info('No matching databases found.');return
		A=_get_pre_selected_labels();e=_get_open_index();G=set()
		def f(items):
			for A in items:
				G.add(A.label)
				if A.children:f(A.children)
		f(L);V=_B;logger.debug(f"[TREE_NAV] all_tree_labels count: {len(G)}")
		if d:A=[];logger.debug(f"[TREE_NAV] Filter activated - forcing empty pre_selected (unchecked)")
		elif A:
			C=[A for A in A if A in G];W=len(A)-len(C);logger.debug(f"[TREE_NAV] pre_selected={len(A)}, valid={len(C)}, missing={W}")
			if W>0:
				M=set()
				for H in A:
					if H not in G:
						N=H.split('.')
						if len(N)>=2:
							g=N[0];h=f"{N[0]}.{N[1]}"
							if h in G:M.add(h)
							elif g in G:M.add(g)
				C=list(set(C)|M);logger.debug(f"[TREE_NAV] Added parent labels: {M}, total valid: {len(C)}")
			if W>len(A)//2:V=_A
			A=C if C else[]
		else:A=[]
		i=f"object_tree_{st.session_state.get(_V,0)}";B=st.session_state.get(_G,0);logger.debug(f"[EXEC:{B}][TREE_INPUT] tree_key={i}, index={len(A)if A else 0} items, tree_items={len(L)}")
		if D:st.info('⚠️ Object selection is locked on the Generate step. Go back to modify selections.')
		v=sac.tree(items=L,index=A,open_index=e,label='Select objects:'if not D else'Selected objects (locked):',icon='diagram-3',color=_T if not D else'#8A8A8A',open_all=_B,checkbox=_A,checkbox_strict=_B,show_line=_A,return_index=_B,key=i);O,j=_parse_tree_result(v);_sync_expansion_state(j,e);logger.debug(f"[EXEC:{B}][TREE_OUTPUT] selected={len(O)} items, first 5: {O[:5]}");logger.debug(f"[EXEC:{B}][TREE_EXPANDED] expanded_from_tree={len(j)}, expanded_nodes={len(st.session_state.expanded_nodes)}, first 3: {st.session_state.expanded_nodes[:3]if st.session_state.expanded_nodes else[]}");logger.debug(f"[EXEC:{B}][TREE_STATE] pre_selected was: {len(A)if A else 0} items");k=_process_lazy_loading(T,F)
		def w(labels,lmap):
			F=lmap;A=set()
			for C in labels:
				D=F.get(C)
				if not D:A.add(C);continue
				G=D[0]
				if G==_F:A.add(C)
				elif G==_D:
					H=D[1];E=_B
					for(I,B)in F.items():
						if B[0]==_F and B[1]==H:A.add(I);E=_A
					if not E:A.add(C)
				elif G==_E:
					H,J=D[1],D[2];E=_B
					for(I,B)in F.items():
						if B[0]==_F and B[1]==H and B[2]==J:A.add(I);E=_A
					if not E:A.add(C)
			return A
		X=set(A)if A else set();l=set(O);Y=w(l,F);logger.debug(f"[EXEC:{B}][TREE_EXPAND] raw={len(l)}, expanded={len(Y)}");I=Y-X;P=X-Y;logger.debug(f"[TREE_NAV] New selections (added): {len(I)}: {list(I)[:5]}");logger.debug(f"[TREE_NAV] Removed selections: {len(P)}: {list(P)[:5]}");Z=_B;x=len(P)>0;m={A[0]for A in st.session_state.selected_objects}
		if len(X)>0 and I and not x:
			Q=_A
			for H in I:
				J=F.get(H)
				if J and J[0]==_D:
					a=J[1]
					if a not in m:Q=_B;logger.debug(f"[TREE_NAV] Genuine new database selection: {H}");break
					else:logger.debug(f"[TREE_NAV] Spurious db selection (already has objects): {H}")
				elif J and J[0]==_E:
					a=J[1]
					if a not in m:Q=_B;break
				else:Q=_B;break
			Z=Q and any(F.get(A,(_C,))[0]in(_D,_E)for A in I)
		n=bool(st.session_state.get(_S,'').strip());o={A for A in I if A in F};b=bool(o);logger.debug(f"[EXEC:{B}][GUARDS] is_read_only={D}, spurious={Z}, expected_missing={V}, needs_lazy_rerun={k}, removals={len(P)}, filter_active={n}, has_new={b}, valid_new={list(o)[:3]}, filter_just_changed={K}");p=_B;q=_B
		if D:logger.debug('[TREE_NAV] SKIPPING: read-only mode')
		elif K and not b:logger.debug('[TREE_NAV] SKIPPING: filter_just_changed (tree re-rendering)')
		elif Z:logger.debug('[TREE_NAV] SKIPPING: spurious_db_schema')
		elif V and not(n and b):logger.debug('[TREE_NAV] SKIPPING: expected_selections_missing (no filter or new selections)')
		else:logger.debug('[TREE_NAV] PROCESSING selections via _process_tree_selections');p=_process_tree_selections(T,O,F)
		q=_sync_metadata_with_selections(T);R=len(st.session_state.selected_objects);S=len(st.session_state.views_metadata)
		if R!=S:st.warning(f"⚠️ State mismatch: {R} selected, {S} loaded");logger.warning(f"[EXEC:{B}][STATE_DESYNC] selected_objects={R}, views_metadata={S}")
		else:logger.debug(f"[EXEC:{B}][STATE_OK] selected_objects={R}, views_metadata={S}")
		if q:logger.debug(f"[EXEC:{B}][RERUN] Full rerun - metadata changed");st.rerun()
		elif k or p:logger.debug(f"[EXEC:{B}][RERUN] Rerun for lazy loading or selection state");st.rerun()
	A()
def main():
	Ab='Cancel';Aa='One to Many';AZ='One to One';AY='Many to One';AX='Many to Many (*:*)';AW='One to Many (1:*)';AV='One to One (1:1)';AU='Many to One (*:1)';AT='To Column';AS='To Table';AR='From Column';AQ='From Table';AP='snowpark_session';AO='reset_app';AN='is_local';AM='warehouse';AL='server';AK='SnowflakeSemanticViewsConnector.msi';AJ='assets';A7='editing_rel_id';v='1';u='*';t='← Back to Review';s=', ';r='unknown';k='primary';R='stretch';E='many';C='one'
	if _G not in st.session_state:st.session_state._exec_id=0
	st.session_state._exec_id+=1;Ac=st.session_state._exec_id;logger.debug(f"[EXEC:{Ac}] === NEW RENDER CYCLE ===");init_session_state();sync_from_legacy();A8=Path(__file__).parent/_P/'snowflake.svg';st.set_page_config(page_title='Power BI Semantic Model Generator',page_icon=str(A8)if A8.exists()else'❄️',layout='wide');inject_custom_css();Ad=get_svg_icon('snowflake',size=48);A9=Path(__file__).parent/AJ/AK;Ae=A9.exists();Af,Ag=st.columns([6,1])
	with Af:st.markdown(f'''
            <div style="display: flex; align-items: center; gap: 16px; margin-bottom: 4px;">
                {Ad}
                <div style="flex: 1;">
                    <h1 style="margin: 0; padding: 0;">Power BI Semantic Model Generator</h1>
                    <p style="margin: 0; color: #6c757d; font-size: 0.875rem;">
                        Create Power BI semantic models from Snowflake tables and semantic views
                    </p>
                </div>
            </div>
        ''',unsafe_allow_html=_A)
	with Ag:
		st.markdown('<div style="height: 8px;"></div>',unsafe_allow_html=_A)
		if Ae:Ah=A9.read_bytes();st.download_button(label='Get Connector',data=Ah,file_name=AK,mime='application/x-msi',help='Download the Power BI connector (.msi) - required to query Snowflake Semantic Views',key='header_msi_download')
	show_progress_indicator()
	try:M=get_snowflake_session();st.session_state.snowpark_session=M;logger.info('Snowflake session established successfully')
	except FileNotFoundError as I:handle_error(I,operation='Snowflake Configuration',show_in_ui=_A,suggestion='Create ~/.snowflake/connections.toml with your Snowflake credentials, or deploy this app to Streamlit in Snowflake');return
	except ImportError as I:handle_error(I,operation='Loading Dependencies',show_in_ui=_A,details='pip install snowflake-snowpark-python cryptography',suggestion='Install the required packages using pip');return
	except Exception as I:handle_error(I,operation='Snowflake Connection',show_in_ui=_A);return
	try:N=get_session_info(M)
	except Exception as I:st.warning(f"Could not get connection info: {I}");N={AL:r,AM:'XSMALL',AN:_A}
	st.session_state.conn_info=N
	try:AA=get_databases(M);logger.debug(f"Loaded {len(AA)} databases")
	except Exception as I:logger.error(f"Error fetching databases: {I}",exc_info=_A);handle_error(I,operation='Loading Databases',show_in_ui=_A);return
	with st.sidebar:
		Ai,Aj=st.columns([.55,.45],gap='small',vertical_alignment='center')
		with Ai:
			AB=Path(__file__).parent/AJ/'logo_snowflake_blue.png'
			if AB.exists():st.image(str(AB),width=140)
		with Aj:Ak=st.button('Reset',key=AO,type='secondary',icon=':material/refresh:',use_container_width=_A)
		if Ak:
			Al=st.session_state.get(_V,0);Am={'conn_info'};An=[A for A in st.session_state.keys()if A not in Am]
			for Ao in An:del st.session_state[Ao]
			st.session_state.wizard_step=0;st.session_state.views_metadata=[];st.session_state.selected_objects=[];st.session_state.search_filter='';st.session_state.tree_reset_counter=Al+1;st.session_state._just_reset=_A;log_user_action(AO);st.rerun()
		st.divider();render_tree_navigation(M,AA);st.divider();st.markdown(f"### {icon_header('connected','Connection Info',size=24)}",unsafe_allow_html=_A);Ap='🏠 Local'if N.get(AN,_A)else f"{get_svg_icon('cloud',16)} Snowflake";st.markdown(f"**Environment:** {Ap}",unsafe_allow_html=_A);st.text(f"Server: {N.get(AL,r)}");st.text(f"Warehouse: {N.get(AM,r)}");st.text(f"User: {N.get('user',r)}")
		if'error'in N:st.error(f"Connection error: {N['error']}")
	S=get_wizard_step();logger.debug(f"Rendering wizard step {S}");Aq=get_app_state()
	if is_page_implemented(S):
		logger.debug(f"Using page system for step {S}")
		if render_current_step(M,Aq):return
	if S==0:
		st.markdown(f"## {icon_header('verified','Review Selected Objects',size=28)}",unsafe_allow_html=_A)
		if not st.session_state.views_metadata:st.info('👈 Use the **sidebar tree navigator** to select tables, views, and semantic views.')
		else:
			BJ=sum(len(A.columns)for A in st.session_state.views_metadata);w=any(A.object_type==_H for A in st.session_state.views_metadata);x=any(A.object_type in(_J,_M)for A in st.session_state.views_metadata)
			if w and x:st.info('**Mixed selection:** Semantic views use Custom Connector, standard tables use Native Snowflake Connector.')
			for H in st.session_state.views_metadata:
				Ar=get_object_icon_html(H.object_type,size=20);As=get_connector_badge_html(H.object_type);st.markdown(f"{Ar} **{H.full_name}** ({len(H.columns)} columns){As}",unsafe_allow_html=_A)
				if H.table_metadata and H.table_metadata.comment:st.caption(f"📝 {H.table_metadata.comment}")
				with st.expander('Show columns',expanded=_B):display_column_metadata(H)
			At={A.view for A in st.session_state.views_metadata};y=set()
			for H in st.session_state.views_metadata:
				if H.relationships:
					for A in H.relationships:
						if A.to_table not in At:y.add(A.to_table)
			if y:st.warning(f"**💡 Suggested tables:** {s.join(sorted(y))}")
			st.divider()
			if st.button('Next: Design Data Model ->',type=k,width=R,key='review_next_btn'):logger.debug('Button clicked - navigating to step 1');st.session_state.wizard_step=1;st.rerun()
	elif S==1:
		logger.debug(f"Rendering step 1, views_metadata count: {len(st.session_state.get(_I,[]))}");st.markdown(f"## {icon_header('data_engineering','Design Data Model',size=28)}",unsafe_allow_html=_A)
		if not st.session_state.views_metadata:
			st.warning('No objects selected.')
			if st.button(t):st.session_state.wizard_step=0;st.rerun()
		elif len(st.session_state.views_metadata)==1:
			st.info('Single object selected - no relationships to configure.')
			if FLOW_AVAILABLE:render_schema_visualizer(tables=st.session_state.views_metadata,relationships=[],key='single_object_graph_main')
			st.divider();Y,Z=st.columns(2)
			with Y:
				if st.button(t):st.session_state.wizard_step=0;st.rerun()
			with Z:
				if st.button('NEXT: DOWNLOAD PBI WORKBOOK ->',type=k,width=R):st.session_state.wizard_step=2;st.rerun()
		else:
			w=any(A.object_type==_H for A in st.session_state.views_metadata);x=any(A.object_type in(_J,_M)for A in st.session_state.views_metadata);D=collect_all_relationships(st.session_state.views_metadata,session=st.session_state.get(AP))
			if D:
				M=st.session_state.get(AP);O={A.view:A for A in st.session_state.views_metadata}
				for A in D:
					F=O.get(A.from_table);G=O.get(A.to_table)
					if F and G and M:enrich_relationship_with_cardinality(M,A,F,G)
			if w and x and D:
				AC={A.view:A.object_type for A in st.session_state.views_metadata};a=[]
				for A in D:
					Au=AC.get(A.from_table,_J);Av=AC.get(A.to_table,_J);Aw=Au==_H;Ax=Av==_H
					if Aw!=Ax:a.append(A)
				if a:st.warning(f"**⚠️ Cross-connector relationships detected ({len(a)})**\n\nRelationships between tables using different connectors may need to be created manually in Power BI Desktop.\n\nAffected: {s.join(f'{A.from_table}->{A.to_table}'for A in a[:3])}{'...'if len(a)>3 else''}")
			if _O not in st.session_state:st.session_state.selected_relationships={}
			if D:
				for A in D:
					if A.relationship_id not in st.session_state.selected_relationships:st.session_state.selected_relationships[A.relationship_id]=_A
				Ay={A.relationship_id for A in D};Az={A.relationship_id for A in st.session_state.get(_K,[])};st.session_state.selected_relationships={A:B for(A,B)in st.session_state.selected_relationships.items()if A in Ay or A in Az};AD=[A for A in D if st.session_state.selected_relationships.get(A.relationship_id,_A)];_,A_=detect_ambiguous_paths(AD);l={A.relationship_id for A in A_};T=st.session_state.get(_K,[]);U=D+T;BK=sum(1 for A in U if st.session_state.selected_relationships.get(A.relationship_id,_A));P=detect_role_playing_dimensions(AD)
				if P:
					if'duplicate_role_playing_dims'not in st.session_state:st.session_state.duplicate_role_playing_dims={A:_A for A in P}
					else:
						for AE in P:
							if AE not in st.session_state.duplicate_role_playing_dims:st.session_state.duplicate_role_playing_dims[AE]=_A
						st.session_state.duplicate_role_playing_dims={A:B for(A,B)in st.session_state.duplicate_role_playing_dims.items()if A in P}
			else:l=set();P={}
			T=st.session_state.get(_K,[]);U=D+T;B0,B1=st.columns([1,1])
			with B0:
				if'show_add_rel_form'not in st.session_state:st.session_state.show_add_rel_form=_B
				if st.button('+ Add Relationship',key='toggle_add_rel'):st.session_state.show_add_rel_form=not st.session_state.show_add_rel_form;st.rerun()
				if st.session_state.show_add_rel_form:
					J=[A.view for A in st.session_state.views_metadata];b={A.view:[A.name for A in A.columns]for A in st.session_state.views_metadata}
					with st.container(border=_A):
						st.markdown('**Add New Relationship**');Y,Z=st.columns(2)
						with Y:V=st.selectbox(AQ,options=J,key='add_rel_from_table');c=b.get(V,[]);z=st.selectbox(AR,options=c,key='add_rel_from_col')
						with Z:AF=[A for A in J if A!=V];d=st.selectbox(AS,options=AF if AF else J,key='add_rel_to_table');e=b.get(d,[]);A0=st.selectbox(AT,options=e,key='add_rel_to_col')
						st.markdown('**Cardinality**');A1=[AU,AV,AW,AX];A2=st.radio('Relationship type',options=A1,index=0,key='add_rel_cardinality',horizontal=_A,label_visibility='collapsed',help='Many to One is most common (e.g., Orders -> Customers)')
						if AY in A2:K,L=E,C
						elif AZ in A2:K,L=C,C
						elif Aa in A2:K,L=C,E
						else:K,L=E,E
						f,g=st.columns(2)
						with f:
							if st.button(Ab,key='cancel_add_rel',width=R):st.session_state.show_add_rel_form=_B;st.rerun()
						with g:
							if st.button('Add',key='confirm_add_rel',type=k,width=R):
								if V and z and d and A0:
									O={A.view:A for A in st.session_state.views_metadata};F=O.get(V);G=O.get(d);W=create_manual_relationship(from_table=V,from_columns=z,to_table=d,to_columns=A0,from_database=F.database if F else _C,from_schema=F.schema if F else _C,to_database=G.database if G else _C,to_schema=G.schema if G else _C,from_cardinality=K,to_cardinality=L)
									if _K not in st.session_state:st.session_state.manual_relationships=[]
									B2={A.relationship_id for A in st.session_state.manual_relationships}
									if W.relationship_id not in B2:st.session_state.manual_relationships.append(W);st.session_state.selected_relationships[W.relationship_id]=_A;log_user_action('add_manual_relationship',{'from':f"{V}.{z}",'to':f"{d}.{A0}"});st.session_state.show_add_rel_form=_B;st.rerun()
									else:st.warning('This relationship already exists.')
				if not D and not T:st.info("No foreign key constraints detected in Snowflake. Use 'Add Relationship' above to manually define relationships between tables.")
				st.markdown('---')
				if U:
					f,g=st.columns(2)
					with f:
						if st.button('Select All',key='select_all_rels',width=R):
							for A in U:B=A.relationship_id;st.session_state.selected_relationships[B]=_A;st.session_state[f"rel_{B}"]=_A
							st.rerun()
					with g:
						if st.button('Deselect All',key='deselect_all_rels',width=R):
							for A in U:B=A.relationship_id;st.session_state.selected_relationships[B]=_B;st.session_state[f"rel_{B}"]=_B
							st.rerun()
				if T:
					st.markdown('**✏️ Manual Relationships**')
					for A in T:
						B=A.relationship_id;h=B in l and st.session_state.selected_relationships.get(B,_A);K=getattr(A,'from_cardinality',E);L=getattr(A,'to_cardinality',C);m=f"({u if K==E else v}:{u if L==E else v})";Q=f"{A.from_table}.{A.from_column} -> {A.to_table}.{A.to_column} {m} `[Manual]`"
						if h:Q+=' ⚠️'
						X='User-created relationship'
						if h:X+=' (inactive - resolves ambiguous paths)'
						B3=st.session_state.get(A7)==B
						if B3:
							with st.container(border=_A):
								st.markdown('**Edit Relationship**');J=[A.view for A in st.session_state.views_metadata];b={A.view:[A.name for A in A.columns]for A in st.session_state.views_metadata};O={A.view:A for A in st.session_state.views_metadata};B4,B5=st.columns(2)
								with B4:B6=J.index(A.from_table)if A.from_table in J else 0;A3=st.selectbox(AQ,options=J,index=B6,key=f"edit_from_table_{B}");c=b.get(A3,[]);B7=c.index(A.from_column)if A.from_column in c else 0;B8=st.selectbox(AR,options=c,index=B7,key=f"edit_from_col_{B}")
								with B5:B9=J.index(A.to_table)if A.to_table in J else 0;A4=st.selectbox(AS,options=J,index=B9,key=f"edit_to_table_{B}");e=b.get(A4,[]);BA=e.index(A.to_column)if A.to_column in e else 0;BB=st.selectbox(AT,options=e,index=BA,key=f"edit_to_col_{B}")
								A1=[AU,AV,AW,AX]
								if K==E and L==C:n=0
								elif K==C and L==C:n=1
								elif K==C and L==E:n=2
								else:n=3
								A5=st.radio('Cardinality',options=A1,index=n,key=f"edit_card_{B}",horizontal=_A)
								if AY in A5:o,p=E,C
								elif AZ in A5:o,p=C,C
								elif Aa in A5:o,p=C,E
								else:o,p=E,E
								f,g=st.columns(2)
								with f:
									if st.button(Ab,key=f"cancel_edit_{B}"):del st.session_state[A7];st.rerun()
								with g:
									if st.button('Save',key=f"save_edit_{B}",type=k):st.session_state.manual_relationships=[A for A in st.session_state.manual_relationships if A.relationship_id!=B];st.session_state.selected_relationships.pop(B,_C);F=O.get(A3);G=O.get(A4);W=create_manual_relationship(from_table=A3,from_columns=B8,to_table=A4,to_columns=BB,from_database=F.database if F else _C,from_schema=F.schema if F else _C,to_database=G.database if G else _C,to_schema=G.schema if G else _C,from_cardinality=o,to_cardinality=p);st.session_state.manual_relationships.append(W);st.session_state.selected_relationships[W.relationship_id]=_A;del st.session_state[A7];st.rerun()
						else:
							BC,BD,BE=st.columns([.8,.1,.1])
							with BC:i=st.checkbox(Q,value=st.session_state.selected_relationships.get(B,_A),key=f"rel_{B}",help=X);st.session_state.selected_relationships[B]=i
							with BD:
								if st.button('✏️',key=f"edit_{B}",help='Edit this relationship'):st.session_state.editing_rel_id=B;st.rerun()
							with BE:
								if st.button('🗑️',key=f"del_{B}",help='Delete this relationship'):st.session_state.manual_relationships=[A for A in st.session_state.manual_relationships if A.relationship_id!=B];st.session_state.selected_relationships.pop(B,_C);st.rerun()
				if D:
					st.markdown(f"**{get_svg_icon('copy',16)} Detected Relationships**",unsafe_allow_html=_A)
					for A in D:
						B=A.relationship_id;h=B in l and st.session_state.selected_relationships.get(B,_A);q=A.from_table==A.to_table;m=''
						if hasattr(A,'cardinality')and A.cardinality:BF=v if A.cardinality.from_cardinality==C else u;BG=v if A.cardinality.to_cardinality==C else u;m=f" ({BF}:{BG})"
						Q=f"{A.from_table}.{A.from_column} -> {A.to_table}.{A.to_column}{m}"
						if A.name:Q+=f" ({A.name})"
						if q:Q+=' 🔄 `[Self-ref]`'
						elif h:Q+=' ⚠️'
						X=_C;AG=_B
						if q:X='Self-referential relationship - Power BI does not support this. Will NOT be exported.';AG=_A
						elif h:X='Inactive - resolves ambiguous paths'
						i=st.checkbox(Q,value=_B if q else st.session_state.selected_relationships.get(B,_A),key=f"rel_{B}",help=X,disabled=AG)
						if not q:st.session_state.selected_relationships[B]=i
					if l:st.caption('⚠️ = inactive relationship')
					if any(A.from_table==A.to_table for A in D):st.caption('🔄 = self-referential (not exported to Power BI)')
					if P:
						st.markdown('---');st.markdown('**Role-Playing Dimensions**');st.caption('Dimensions used by multiple tables - will be duplicated with role prefixes.')
						for(j,AH)in P.items():BH=[f"{A}_{j}"for A in AH];i=st.checkbox(f"{j} -> {s.join(BH)}",value=st.session_state.duplicate_role_playing_dims.get(j,_A),key=f"dup_{j}",help=f"Referenced by: {s.join(AH)}");st.session_state.duplicate_role_playing_dims[j]=i
			with B1:
				if len(st.session_state.views_metadata)>1 and FLOW_AVAILABLE:st.caption('Drag to rearrange, scroll to zoom');BI=[A for A in U if st.session_state.selected_relationships.get(A.relationship_id,_A)];render_schema_visualizer(tables=st.session_state.views_metadata,relationships=BI,key='main_schema_graph');show_graph_legend()
				else:st.info('Schema diagram available when 2+ tables selected')
			st.divider();Y,Z=st.columns(2)
			with Y:
				if st.button(t):st.session_state.wizard_step=0;st.rerun()
			with Z:
				if st.button('Next: Generate Output ->',type=k,width=R):st.session_state.wizard_step=2;st.rerun()
	elif S==2:
		st.markdown(f"## {icon_header('rocket','Generate Output',size=28)}",unsafe_allow_html=_A);A6=len(st.session_state.get(_U,[]));AI=len(st.session_state.get(_I,[]));logger.warning(f"[FALLBACK] Step 2 fallback rendering: selected_objects={A6}, views_metadata={AI}")
		if not st.session_state.get(_I):
			st.warning(f"No metadata loaded. ({A6} objects selected but metadata not loaded)");st.caption('This is a fallback page. The normal page system may have failed.')
			if A6>0:st.info("Selected objects exist but metadata wasn't loaded. Try going back and reselecting.")
			if st.button(t):st.session_state.wizard_step=0;st.rerun()
		else:
			st.info(f"Fallback mode: {AI} objects ready for generation.");st.caption('The normal page system may have failed. Please try refreshing.')
			if'_page_render_error'in st.session_state:st.error(f"Page error: {st.session_state._page_render_error}")
			if st.button('← Back to Design Data Model'):st.session_state.wizard_step=1;st.rerun()
	st.divider();st.markdown(f"*Written By Alex Ross, Principal Solution Engineer at Snowflake | © {datetime.now().year}*");st.caption('ℹ️ Provided as-is under [MIT License](https://opensource.org/licenses/MIT). Not officially supported by Snowflake.')
def _render_dax_solution(rel,to_meta,risk):
	B=to_meta;A=risk;st.caption('ℹ️ Query-time calculation in Power BI - no Snowflake objects needed');st.warning("⚠️ **DAX SUMX/VALUES pattern only works in Import mode.** In DirectQuery, this pattern fails when tables exceed 1 million rows due to Power BI's row limit for the `VALUES()` function.")
	if not B or not A or not A.affected_measures:st.warning('Table metadata not available');return
	C=[A for A in B.columns if A.is_primary_key];D=C[0].name if C else _C
	if D:
		st.markdown('**DAX measures to copy to Power BI:**')
		for(G,E)in enumerate(A.affected_measures[:3]):F=generate_dax_measure(measure_name=E,source_table=rel.to_table,measure_column=E,pk_column=D,aggregation='SUM');st.code(F,language='dax')
		if len(A.affected_measures)>3:st.caption(f"*...and {len(A.affected_measures)-3} more measures*")
		st.info('\n**📖 How to use DAX measures:**\n\n1. Open your Power BI report\n2. Select the table in the Data pane\n3. Click "New Measure" in the ribbon\n4. Paste the DAX code above\n\n**Why this works:**\n- `VALUES()` gets distinct primary keys\n- `SUMX()` iterates and aggregates at correct grain\n')
	else:st.warning('Cannot generate DAX - no primary key found in table')
if __name__=='__main__':main()