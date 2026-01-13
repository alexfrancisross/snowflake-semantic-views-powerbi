_K='selected_objects'
_J='expanded_nodes'
_I='loaded_objects'
_H='loaded_schemas'
_G='SEMANTIC_VIEW'
_F='object'
_E='schema'
_D='database'
_C=False
_B=True
_A=None
from dataclasses import dataclass,field
from typing import Any,Callable,Optional
import streamlit as st,streamlit_antd_components as sac
from config import CONFIG,OBJECT_TYPES,get_object_type_config
from logging_config import get_logger,log_user_action
from error_handling import error_boundary,MetadataFetchError
logger=get_logger(__name__)
@dataclass
class TreeConfig:on_selection_change:Optional[Callable[[list],_A]]=_A;show_search:bool=_B;show_selection_count:bool=_B;auto_load_metadata:bool=_B;checkbox_mode:bool=_B;cascade_selection:bool=_C;tree_color:str='#29B5E8'
def get_object_icon(object_type):C='table';B=object_type;A=get_object_type_config(B);D={_G:('box',A.color_primary),'VIEW':('eye',A.color_primary),'TABLE':(C,A.color_primary)};E,F=D.get(B,(C,'#75CDD7'));return sac.BsIcon(name=E,color=F)
def get_object_tag(object_type):B='cyan';A='Table';C={_G:('Semantic','purple'),'VIEW':('View','orange'),'TABLE':(A,B)};D,E=C.get(object_type,(A,B));return sac.Tag(D,color=E)
def matches_search(search_term,db,schema=_A,name=_A):
	C=schema;B=search_term
	if not B:return _B
	A=db.upper()
	if C:A+='.'+C.upper()
	if name:A+='.'+name.upper()
	return B in A
class TreeState:
	@staticmethod
	def get_loaded_schemas():return st.session_state.get(_H,{})
	@staticmethod
	def set_schemas(database,schemas):
		if _H not in st.session_state:st.session_state.loaded_schemas={}
		st.session_state.loaded_schemas[database]=schemas
	@staticmethod
	def get_loaded_objects():return st.session_state.get(_I,{})
	@staticmethod
	def set_objects(database,schema,objects):
		if _I not in st.session_state:st.session_state.loaded_objects={}
		st.session_state.loaded_objects[database,schema]=objects
	@staticmethod
	def get_expanded_nodes():return st.session_state.get(_J,[])
	@staticmethod
	def set_expanded_nodes(nodes):st.session_state.expanded_nodes=[A for A in nodes if A is not _A]
	@staticmethod
	def get_selected_objects():return st.session_state.get(_K,[])
	@staticmethod
	def set_selected_objects(objects):st.session_state.selected_objects=objects
	@staticmethod
	def get_reset_counter():return st.session_state.get('tree_reset_counter',0)
	@staticmethod
	def increment_reset_counter():st.session_state.tree_reset_counter=TreeState.get_reset_counter()+1
	@staticmethod
	def cleanup_state():
		if _K in st.session_state:
			D=[]
			for A in st.session_state.selected_objects:
				if A is not _A and isinstance(A,(list,tuple))and len(A)>=4:
					if all(A is not _A for A in A[:4]):D.append(tuple(A[:4]))
			st.session_state.selected_objects=D
		if _J in st.session_state:st.session_state.expanded_nodes=[A for A in st.session_state.expanded_nodes if A is not _A and isinstance(A,str)]
		E=[]
		for B in list(st.session_state.keys()):
			if B.startswith('object_tree_'):
				C=st.session_state[B]
				if C is _A or isinstance(C,list)and any(A is _A for A in C):E.append(B)
		for B in E:del st.session_state[B]
class TreeNavigator:
	def __init__(A,session,config=_A):A.session=session;A.config=config or TreeConfig();A._label_map={}
	def build_tree_items(B,databases,search_term=''):
		C=search_term;D=[];B._label_map={};E=TreeState.get_loaded_schemas();F=TreeState.get_loaded_objects()
		for A in databases:
			if C:
				G=C in A.upper();H=B._has_matching_children(A,C,E,F)
				if not G and not H:continue
			B._label_map[A]=_D,A,_A,_A,_A;I=B._build_schema_items(A,C,E,F);D.append(sac.TreeItem(A,icon=_D,children=I))
		return D
	def _has_matching_children(H,database,search_term,loaded_schemas,loaded_objects):
		E=loaded_objects;D=loaded_schemas;C=search_term;A=database
		if A not in D:return _C
		for B in D[A]:
			if matches_search(C,A,B):return _B
			F=A,B
			if F in E:
				for G in E[F]:
					if matches_search(C,A,B,G.name):return _B
		return _C
	def _build_schema_items(F,database,search_term,loaded_schemas,loaded_objects):
		G=loaded_schemas;D=loaded_objects;C=search_term;A=database
		if A not in G:return[sac.TreeItem('Loading schemas...',disabled=_B)]
		E=[]
		for B in G[A]:
			if C:
				J=matches_search(C,A,B);H=A,B;I=_C
				if H in D:
					for K in D[H]:
						if matches_search(C,A,B,K.name):I=_B;break
				if not J and not I:continue
			F._label_map[B]=_E,A,B,_A,_A;L=F._build_object_items(A,B,C,D);E.append(sac.TreeItem(B,icon='folder2-open',children=L))
		return E if E else[sac.TreeItem('No schemas found',disabled=_B)]
	def _build_object_items(H,database,schema,search_term,loaded_objects):
		F=loaded_objects;E=search_term;C=schema;B=database;G=B,C
		if G not in F:return[sac.TreeItem('Loading objects...',disabled=_B)]
		D=[]
		for A in F[G]:
			if E and not matches_search(E,B,C,A.name):continue
			H._label_map[A.name]=_F,B,C,A.name,A.object_type;D.append(sac.TreeItem(A.name,icon=get_object_icon(A.object_type),tag=get_object_tag(A.object_type)))
		return D if D else[sac.TreeItem('No objects found',disabled=_B)]
	def _handle_expansions(D,expanded):
		L='count';from metadata_fetcher import get_schemas as M,get_all_objects as N;from tooltips import snowflake_spinner as G;F=_C
		for H in expanded:
			if H not in D._label_map:continue
			E=D._label_map[H];I=E[0]
			if I==_D:
				A=E[1];O=TreeState.get_loaded_schemas()
				if A not in O:
					with G(f"Loading schemas for {A}..."):
						try:J=M(D.session,A);TreeState.set_schemas(A,J);F=_B;log_user_action('load_schemas',{_D:A,L:len(J)})
						except Exception as C:logger.error(f"Failed to load schemas for {A}: {C}");st.error(f"Error loading schemas: {C}")
			elif I==_E:
				A,B=E[1],E[2];P=TreeState.get_loaded_objects()
				if(A,B)not in P:
					with G(f"Loading objects for {B}..."):
						try:K=N(D.session,A,B);TreeState.set_objects(A,B,K);F=_B;log_user_action('load_objects',{_D:A,_E:B,L:len(K)})
						except Exception as C:logger.error(f"Failed to load objects for {A}.{B}: {C}");st.error(f"Error loading objects: {C}")
		return F
	def _ensure_parents_expanded(E,selections,expanded):
		D=expanded;A=set(D)if D else set()
		for(B,C,F,G)in selections:
			if B and B not in A:A.add(B)
			if C and C not in A:A.add(C)
		return list(A)
	def _handle_selections(F,selected):
		G=selected;N=TreeState.get_selected_objects();H=set()
		for(B,C)in F._label_map.items():
			if C[0]==_F:H.add(B)
		logger.debug(f"[_handle_selections] selected from tree: {G}");logger.debug(f"[_handle_selections] existing_selections: {N}");logger.debug(f"[_handle_selections] visible_object_labels count: {len(H)}");Q=set(G);I=[]
		for(D,E,A,J)in N:
			if A not in H:I.append((D,E,A,J));logger.debug(f"[_handle_selections] PRESERVING (not visible): {A}")
		K=[]
		for B in G:
			if B not in F._label_map:logger.debug(f"[_handle_selections] label not in _label_map: {B}");continue
			C=F._label_map[B]
			if C[0]==_F:R,D,E,A,J=C;K.append((D,E,A,J));logger.debug(f"[_handle_selections] NEW selection: {D}.{E}.{A}")
		P=I+K;O=set();L=[]
		for M in P:
			if M not in O:O.add(M);L.append(M)
		logger.debug(f"[_handle_selections] FINAL: preserved={len(I)}, new={len(K)}, unique={len(L)}");return L
	def render(A,databases):
		J=databases;from snowflake_theme import icon_header as Q,get_svg_icon as R;logger.info(f"[TREE] ========== RENDER START ==========");TreeState.cleanup_state();S=st.session_state.get('wizard_step',0);D=S>=2;st.markdown(f"### {Q('select','Select Objects',size=24)}",unsafe_allow_html=_B)
		if D:st.info(f"{R('lock',16)} Selection locked. Use **Reset App** to start over.")
		I=''
		if A.config.show_search and not D:I=st.text_input('Filter databases',placeholder='Type to filter...',key='search_filter').strip().upper()
		if not J:st.warning('No databases found.');return
		K=A.build_tree_items(J,I)
		if not K:st.info('No matching databases found.');return
		L=[B for(A,A,B,A)in TreeState.get_selected_objects()if B is not _A]or _A;logger.debug(f"[render] search_term: '{I}', pre_selected: {L}");M=TreeState.get_expanded_nodes();N=[A for A in M if A]if M else _A;T=f"object_tree_{TreeState.get_reset_counter()}";U='#CCCCCC'if D else A.config.tree_color;B=sac.tree(items=K,index=L,open_index=N,label='Select objects:'if not D else'Selected objects (locked):',icon='diagram-3',color=U,open_all=_C,checkbox=A.config.checkbox_mode,checkbox_strict=not A.config.cascade_selection,show_line=_B,return_index=_C,key=T)
		if hasattr(B,'selected')and hasattr(B,'expanded'):E=B.selected if isinstance(B.selected,list)else[B.selected]if B.selected else[];F=B.expanded or[]
		else:E=B if isinstance(B,list)else[B]if B else[];F=[]
		E=[A for A in E if A and not str(A).startswith('Loading')]
		if D:G=TreeState.get_selected_objects()
		else:G=A._handle_selections(E);TreeState.set_selected_objects(G)
		F=A._ensure_parents_expanded(G,F)
		if A.config.on_selection_change:A.config.on_selection_change(G)
		C=set(F or[]);O=set(TreeState.get_expanded_nodes()or[]);V=set(N or[])
		if C and C!=V:H=list(C)
		elif not C and O:H=list(O)
		else:H=list(C)if C else[]
		TreeState.set_expanded_nodes(H);W=A._handle_expansions(H)
		if W:st.rerun()
		if A.config.show_selection_count:
			P=len(TreeState.get_selected_objects())
			if P>0:st.success(f"**{P}** object(s) selected")
def render_tree_navigation(session,databases,config=_A):A=TreeNavigator(session,config);A.render(databases)