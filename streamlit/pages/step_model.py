_O='views_metadata'
_N='collapsed'
_M='cardinality'
_L='active_relationship_choices'
_K='TABLE'
_J='SEMANTIC_VIEW'
_I='primary'
_H='to'
_G='from'
_F='manual_relationships'
_E=False
_D='stretch'
_C=None
_B='one'
_A=True
import streamlit as st
from pages import BasePage,PageContext,register_page
from utils.logging_config import get_logger,log_user_action
from utils.error_handling import show_error
from utils.snowflake_theme import icon_header,get_svg_icon
from utils.pbit_generator import collect_all_relationships,detect_ambiguous_paths,detect_conflict_pairs,detect_role_playing_dimensions
from utils.schema_visualizer import render_schema_visualizer,show_graph_legend,FLOW_AVAILABLE
from utils.relationship_suggester import create_manual_relationship
logger=get_logger(__name__)
def init_relationship_state(all_relationships):
	A=all_relationships
	if'selected_relationships'not in st.session_state:st.session_state.selected_relationships={A.relationship_id:_A for A in A}
	else:
		for B in A:
			if B.relationship_id not in st.session_state.selected_relationships:st.session_state.selected_relationships[B.relationship_id]=_A
		C={A.relationship_id for A in A};st.session_state.selected_relationships={A:B for(A,B)in st.session_state.selected_relationships.items()if A in C}
	if _L not in st.session_state:st.session_state.active_relationship_choices={}
def render_relationship_checkboxes(relationships,inactive_ids):
	for A in relationships:
		B=A.relationship_id;D=B in inactive_ids and st.session_state.selected_relationships.get(B,_A);E=''
		if hasattr(A,_M)and A.cardinality:G='1'if A.cardinality.from_cardinality==_B else'*';H='1'if A.cardinality.to_cardinality==_B else'*';E=f" ({G}:{H})"
		C=f"{A.from_table}.{A.from_column} -> {A.to_table}.{A.to_column}{E}"
		if A.name:C+=f" ({A.name})"
		if D:C+=' ⚠️'
		F=_C
		if D:F="Secondary path - won't filter automatically (use USERELATIONSHIP in DAX)"
		I=st.checkbox(C,value=st.session_state.selected_relationships.get(B,_A),key=f"rel_{B}",help=F);st.session_state.selected_relationships[B]=I
def render_manual_relationship_checkboxes(manual_relationships,inactive_ids):
	for A in manual_relationships:
		B=A.relationship_id;C=B in inactive_ids and st.session_state.selected_relationships.get(B,_A);D=''
		if hasattr(A,'from_cardinality')and A.from_cardinality and hasattr(A,'to_cardinality')and A.to_cardinality:G='1'if A.from_cardinality==_B else'*';H='1'if A.to_cardinality==_B else'*';D=f" ({G}:{H})"
		E=f"{A.from_table}.{A.from_column} -> {A.to_table}.{A.to_column}{D} `[Manual]`"
		if C:E+=' ⚠️'
		F='User-created relationship'
		if C:F+=" (secondary path - won't filter automatically)"
		I,J=st.columns([.9,.1])
		with I:K=st.checkbox(E,value=st.session_state.selected_relationships.get(B,_A),key=f"rel_{B}",help=F);st.session_state.selected_relationships[B]=K
		with J:
			if st.button('🗑️',key=f"del_{B}",help='Delete this relationship'):
				if _F in st.session_state:st.session_state.manual_relationships=[A for A in st.session_state.manual_relationships if A.relationship_id!=B]
				st.session_state.selected_relationships.pop(B,_C);st.rerun()
def render_add_relationship_form(views_metadata):
	H=views_metadata;G='many'
	if'show_add_rel_form'not in st.session_state:st.session_state.show_add_rel_form=_E
	if st.button('+ Add Relationship',key='toggle_add_rel'):st.session_state.show_add_rel_form=not st.session_state.show_add_rel_form;st.rerun()
	if not st.session_state.show_add_rel_form:return
	I=[A.view for A in H];N={A.view:[A.name for A in A.columns]for A in H};O={A.view:A for A in H}
	with st.container(border=_A):
		st.markdown('**Add New Relationship**');Q,R=st.columns(2)
		with Q:A=st.selectbox('From Table',options=I,key='add_rel_from_table');S=N.get(A,[]);J=st.selectbox('From Column',options=S,key='add_rel_from_col')
		with R:P=[B for B in I if B!=A];B=st.selectbox('To Table',options=P if P else I,key='add_rel_to_table');T=N.get(B,[]);K=st.selectbox('To Column',options=T,key='add_rel_to_col')
		st.markdown('**Cardinality**');U=['Many to One (*:1)','One to One (1:1)','One to Many (1:*)','Many to Many (*:*)'];L=st.radio('Relationship type',options=U,index=0,key='add_rel_cardinality',horizontal=_A,label_visibility=_N,help='Many to One is most common (e.g., Orders -> Customers)')
		if'Many to One'in L:C,D=G,_B
		elif'One to One'in L:C,D=_B,_B
		elif'One to Many'in L:C,D=_B,G
		else:C,D=G,G
		V,W=st.columns(2)
		with V:
			if st.button('Cancel',key='cancel_add_rel',width=_D):st.session_state.show_add_rel_form=_E;st.rerun()
		with W:
			if st.button('Add',key='confirm_add_rel',type=_I,width=_D):
				if A and J and B and K:
					E=O.get(A);F=O.get(B);M=create_manual_relationship(from_table=A,from_columns=J,to_table=B,to_columns=K,from_database=E.database if E else _C,from_schema=E.schema if E else _C,to_database=F.database if F else _C,to_schema=F.schema if F else _C,from_cardinality=C,to_cardinality=D)
					if _F not in st.session_state:st.session_state.manual_relationships=[]
					X={A.relationship_id for A in st.session_state.manual_relationships}
					if M.relationship_id not in X:st.session_state.manual_relationships.append(M);st.session_state.selected_relationships[M.relationship_id]=_A;log_user_action('add_manual_relationship',{_G:f"{A}.{J}",_H:f"{B}.{K}"});st.session_state.show_add_rel_form=_E;st.rerun()
					else:st.warning('This relationship already exists.')
def render_conflict_pair_group(pair,pair_index):
	C=pair_index;A,D,I=pair;E=f"conflict_{C}";J=st.session_state.active_relationship_choices.get(E,A.relationship_id)
	def F(rel):
		A=rel;B=''
		if hasattr(A,_M)and A.cardinality:C='1'if A.cardinality.from_cardinality==_B else'*';D='1'if A.cardinality.to_cardinality==_B else'*';B=f" ({C}:{D})"
		E=A.from_column if hasattr(A,'from_column')else A.from_columns;F=A.to_column if hasattr(A,'to_column')else A.to_columns;return f"{A.from_table}.{E} -> {A.to_table}.{F}{B}"
	B=F(A);G=F(D);H={B:A.relationship_id,G:D.relationship_id};K=B if J==A.relationship_id else G
	with st.container(border=_A):st.markdown(f"**Multiple paths to {I}** - choose primary:");L=st.radio('Select primary path',options=list(H.keys()),index=0 if K==B else 1,key=f"conflict_radio_{C}",label_visibility=_N);M=H[L];st.session_state.active_relationship_choices[E]=M;st.caption("Secondary path won't filter automatically (use USERELATIONSHIP in DAX)")
@register_page(1)
class ModelPage(BasePage):
	def __init__(A,step_index=1):super().__init__(step_index)
	def render(F,context):
		E='navigate_step';D='← Back to Review';st.markdown(f"## {icon_header('data_engineering','Design Data Model',size=28)}",unsafe_allow_html=_A);A=st.session_state.get(_O,[]);logger.debug(f"ModelPage.render: views_metadata has {len(A)} items");logger.debug(f"ModelPage.render: table names = {[A.view for A in A]}")
		if not A:
			st.warning('No objects selected. Please go back and select objects.')
			if st.button(D):st.session_state.wizard_step=0;st.rerun()
			return
		if len(A)==1:
			st.info('Single object selected - no relationships to configure.')
			if FLOW_AVAILABLE:render_schema_visualizer(tables=A,relationships=[],key='single_object_graph')
			st.divider();B,C=st.columns(2)
			with B:
				if st.button(D):st.session_state.wizard_step=0;st.rerun()
			with C:
				if st.button('NEXT: DOWNLOAD PBI WORKBOOK ->',type=_I,width=_D):log_user_action(E,{_G:1,_H:2,'skip_semantic':_A});st.session_state.wizard_step=2;st.rerun()
			return
		F._render_relationship_config(A);st.divider();B,C=st.columns(2)
		with B:
			if st.button(D):log_user_action(E,{_G:1,_H:0});st.session_state.wizard_step=0;st.rerun()
		with C:
			if st.button('Next: Generate Output ->',type=_I,width=_D):log_user_action(E,{_G:1,_H:2});st.session_state.wizard_step=2;st.rerun()
	def _render_relationship_config(D,views_metadata):
		H='Try refreshing the page or re-selecting your objects';B=views_metadata;logger.debug(f"_render_relationship_config called with {len(B)} objects");I=any(A.object_type==_J for A in B);J=any(A.object_type in(_K,'VIEW')for A in B);K=st.session_state.get('snowpark_session');A=collect_all_relationships(B,session=K);logger.debug(f"Found {len(A)} FK relationships")
		if I and J and A:D._render_cross_connector_warning(B,A)
		init_relationship_state(A);L=detect_conflict_pairs(A);F=[A for A in A if st.session_state.selected_relationships.get(A.relationship_id,_A)];M=st.session_state.get(_L,{});S,N=detect_ambiguous_paths(F,user_active_choices=M);O={A.relationship_id for A in N};P=st.session_state.get(_F,[]);G=A+P;E=detect_role_playing_dimensions(F)
		if E:D._init_role_playing_state(E)
		Q,R=st.columns([1,1])
		with Q:
			try:D._render_left_column(A,G,O,E,B,L)
			except Exception as C:logger.error(f"Error in _render_left_column: {C}",exc_info=_A);show_error('Error rendering relationships',details=str(C),suggestion=H)
		with R:
			try:D._render_schema_diagram(B,G)
			except Exception as C:logger.error(f"Error in _render_schema_diagram: {C}",exc_info=_A);show_error('Error rendering diagram',details=str(C),suggestion=H)
	def _render_cross_connector_warning(H,views_metadata,all_relationships):
		C={A.view:A.object_type for A in views_metadata};A=[]
		for B in all_relationships:
			D=C.get(B.from_table,_K);E=C.get(B.to_table,_K);F=D==_J;G=E==_J
			if F!=G:A.append(B)
		if A:st.warning(f"**Cross-connector relationships detected ({len(A)})**\n\nRelationships between tables using different connectors may need to be created manually in Power BI Desktop.\n\nAffected: {', '.join(f'{A.from_table}->{A.to_table}'for A in A[:3])}{'...'if len(A)>3 else''}")
	def _init_role_playing_state(C,role_playing_dims):
		A=role_playing_dims
		if'duplicate_role_playing_dims'not in st.session_state:st.session_state.duplicate_role_playing_dims={A:_A for A in A}
		else:
			for B in A:
				if B not in st.session_state.duplicate_role_playing_dims:st.session_state.duplicate_role_playing_dims[B]=_A
			st.session_state.duplicate_role_playing_dims={B:C for(B,C)in st.session_state.duplicate_role_playing_dims.items()if B in A}
	def _render_left_column(W,all_relationships,all_rels,inactive_ids,role_playing_dims,views_metadata=_C,conflict_pairs=_C):
		O='---';K=views_metadata;J=role_playing_dims;I=inactive_ids;F=all_rels;E=all_relationships;C=conflict_pairs;D=st.session_state.get(_F,[]);C=C or[]
		if K:render_add_relationship_form(K);st.markdown(O)
		if F:
			P,Q=st.columns(2)
			with P:
				if st.button('Select All',key='select_all_rels',width=_D):
					for G in F:A=G.relationship_id;st.session_state.selected_relationships[A]=_A;st.session_state[f"rel_{A}"]=_A
					st.rerun()
			with Q:
				if st.button('Deselect All',key='deselect_all_rels',width=_D):
					for G in F:A=G.relationship_id;st.session_state.selected_relationships[A]=_E;st.session_state[f"rel_{A}"]=_E
					st.rerun()
		if D:st.markdown('**✏️ Manual Relationships**');render_manual_relationship_checkboxes(D,I)
		if C:
			st.markdown('**Path Choices** (select one per group)');H=set()
			for(R,L)in enumerate(C):S,T,X=L;H.add(S.relationship_id);H.add(T.relationship_id);render_conflict_pair_group(L,R)
			M=[A for A in E if A.relationship_id not in H]
			if M:st.markdown('**Other Relationships**');render_relationship_checkboxes(M,set())
		elif E:
			if D:st.markdown(f"**{get_svg_icon('copy',16)} Detected Relationships**",unsafe_allow_html=_A)
			render_relationship_checkboxes(E,I)
		elif not D:st.info('No FK constraints detected. Use **+ Add Relationship** above to define your data model.')
		if J:
			st.markdown(O);st.markdown('**Role-Playing Dimensions**');st.caption('Dimensions used by multiple tables - will be duplicated with role prefixes.')
			for(B,N)in J.items():U=[f"{A}_{B}"for A in N];V=st.checkbox(f"{B} -> {', '.join(U)}",value=st.session_state.duplicate_role_playing_dims.get(B,_A),key=f"dup_{B}",help=f"Referenced by: {', '.join(N)}");st.session_state.duplicate_role_playing_dims[B]=V
	def _render_schema_diagram(C,views_metadata,all_rels):
		A=views_metadata
		if len(A)>1 and FLOW_AVAILABLE:st.caption('Drag to rearrange, scroll to zoom');B=[A for A in all_rels if st.session_state.selected_relationships.get(A.relationship_id,_A)];render_schema_visualizer(tables=A,relationships=B,key='main_schema_graph');show_graph_legend()
		else:st.info('Schema diagram available when 2+ tables selected')
	def validate(B,context):A=st.session_state.get(_O,[]);return len(A)>0