_Y='editing_rel_id'
_X='show_add_rel_form'
_W='tree_reset_counter'
_V='reset_counter'
_U='config'
_T='selection'
_S='dark_mode'
_R='pbi_mode'
_Q='ui'
_P='duplicate_role_playing_dims'
_O='manual_relationships'
_N='selected_relationships'
_M='expanded_nodes'
_L='loaded_objects'
_K='loaded_schemas'
_J='tree'
_I='views_metadata'
_H='selected_objects'
_G='wizard_step'
_F='active_relationship_choices'
_E='bridge_relationships'
_D='model'
_C=False
_B=True
_A=None
from dataclasses import dataclass,field
from typing import Any,Optional
import streamlit as st
from.config import CONFIG
@dataclass
class SelectionState:
	selected_objects:list[tuple[str,str,str,str]]=field(default_factory=list);views_metadata:list[Any]=field(default_factory=list)
	def add_object(A,database,schema,name,object_type):
		B=database,schema,name,object_type
		if B not in A.selected_objects:A.selected_objects.append(B);return _B
		return _C
	def remove_object(A,database,schema,name,object_type):
		B=database,schema,name,object_type
		if B in A.selected_objects:A.selected_objects.remove(B);return _B
		return _C
	def clear(A):A.selected_objects.clear();A.views_metadata.clear()
	@property
	def count(self):return len(self.selected_objects)
	@property
	def has_selection(self):return len(self.selected_objects)>0
@dataclass
class TreeNavigationState:
	loaded_schemas:dict[str,list[str]]=field(default_factory=dict);loaded_objects:dict[tuple[str,str],list[Any]]=field(default_factory=dict);expanded_nodes:list[str]=field(default_factory=list);reset_counter:int=0
	def get_schemas(A,database):return A.loaded_schemas.get(database)
	def set_schemas(A,database,schemas):A.loaded_schemas[database]=schemas
	def get_objects(A,database,schema):return A.loaded_objects.get((database,schema))
	def set_objects(A,database,schema,objects):A.loaded_objects[database,schema]=objects
	def is_expanded(A,node_id):return node_id in A.expanded_nodes
	def toggle_expanded(A,node_id):
		B=node_id
		if B in A.expanded_nodes:A.expanded_nodes.remove(B);return _C
		else:A.expanded_nodes.append(B);return _B
	def force_reset(A):A.reset_counter+=1
	def clear_cache(A):A.loaded_schemas.clear();A.loaded_objects.clear()
@dataclass
class DataModelState:
	selected_relationships:dict[str,bool]=field(default_factory=dict);column_zones:dict[str,dict[str,str]]=field(default_factory=dict);measure_config:dict[str,dict[str,Any]]=field(default_factory=dict);manual_relationships:list[Any]=field(default_factory=list);bridge_relationships:list[Any]=field(default_factory=list);active_relationship_choices:dict[str,str]=field(default_factory=dict);duplicate_role_playing_dims:dict[str,Any]=field(default_factory=dict)
	def is_relationship_enabled(A,rel_id,default=_B):return A.selected_relationships.get(rel_id,default)
	def set_relationship_enabled(A,rel_id,enabled):A.selected_relationships[rel_id]=enabled
	def get_column_zone(A,table,column):return A.column_zones.get(table,{}).get(column)
	def set_column_zone(A,table,column,zone):
		B=table
		if B not in A.column_zones:A.column_zones[B]={}
		A.column_zones[B][column]=zone
	def add_manual_relationship(A,relationship):
		B=relationship;C=B.relationship_id;D={A.relationship_id for A in A.manual_relationships}
		if C not in D:A.manual_relationships.append(B);A.selected_relationships[C]=_B;return _B
		return _C
	def remove_manual_relationship(A,rel_id):
		B=rel_id
		for(C,D)in enumerate(A.manual_relationships):
			if D.relationship_id==B:A.manual_relationships.pop(C);A.selected_relationships.pop(B,_A);return _B
		return _C
	def clear(A):A.selected_relationships.clear();A.column_zones.clear();A.measure_config.clear();A.manual_relationships.clear();A.bridge_relationships.clear();A.active_relationship_choices.clear();A.duplicate_role_playing_dims.clear()
@dataclass
class UIState:show_add_rel_form:bool=_C;editing_rel_id:Optional[str]=_A;just_reset:bool=_C
@dataclass
class ConfigurationState:
	pbi_mode:str=field(default_factory=lambda:CONFIG.DEFAULT_PBI_MODE);dark_mode:bool=_C;output_format:str='PBIT'
	def toggle_dark_mode(A):A.dark_mode=not A.dark_mode;return A.dark_mode
@dataclass
class AppState:
	wizard_step:int=0;selection:SelectionState=field(default_factory=SelectionState);tree:TreeNavigationState=field(default_factory=TreeNavigationState);model:DataModelState=field(default_factory=DataModelState);config:ConfigurationState=field(default_factory=ConfigurationState);ui:UIState=field(default_factory=UIState)
	def can_proceed_to_step(A,target_step):
		B=target_step
		if B<A.wizard_step:return _B
		if B>=1 and not A.selection.has_selection:return _C
		if B>=2 and len(A.selection.views_metadata)==0:return _C
		return _B
	def go_to_step(B,step):
		A=step
		if 0<=A<CONFIG.WIZARD_TOTAL_STEPS:
			if B.can_proceed_to_step(A):B.wizard_step=A;return _B
		return _C
	def next_step(A):return A.go_to_step(A.wizard_step+1)
	def prev_step(A):return A.go_to_step(A.wizard_step-1)
	def reset(A):A.wizard_step=0;A.selection=SelectionState();A.tree=TreeNavigationState();A.model=DataModelState()
_STATE_KEY='_app_state'
_STATE_VERSION=2
def _is_state_outdated(state):
	A=state
	if not hasattr(A,'_version'):return _B
	if not hasattr(A,_Q):return _B
	if hasattr(A,_D):
		if not hasattr(A.model,_E):return _B
		if not hasattr(A.model,_F):return _B
	return _C
def get_app_state():
	if _STATE_KEY in st.session_state:
		B=st.session_state[_STATE_KEY]
		if not _is_state_outdated(B):return B
		A=_migrate_outdated_state(B);st.session_state[_STATE_KEY]=A;return A
	A=AppState();A._version=_STATE_VERSION;st.session_state[_STATE_KEY]=A;return A
def _migrate_outdated_state(old_state):
	C=old_state;A=AppState();A._version=_STATE_VERSION
	if hasattr(C,_G):A.wizard_step=C.wizard_step
	if hasattr(C,_T):
		F=C.selection
		if hasattr(F,_H):A.selection.selected_objects=list(F.selected_objects)
		if hasattr(F,_I):A.selection.views_metadata=list(F.views_metadata)
	if hasattr(C,_J):
		D=C.tree
		if hasattr(D,_K):A.tree.loaded_schemas=dict(D.loaded_schemas)
		if hasattr(D,_L):A.tree.loaded_objects=dict(D.loaded_objects)
		if hasattr(D,_M):A.tree.expanded_nodes=list(D.expanded_nodes)
		if hasattr(D,_V):A.tree.reset_counter=D.reset_counter
	if hasattr(C,_D):
		B=C.model
		if hasattr(B,_N):A.model.selected_relationships=dict(B.selected_relationships)
		if hasattr(B,_O):A.model.manual_relationships=list(B.manual_relationships)
		if hasattr(B,'column_zones'):A.model.column_zones=dict(B.column_zones)
		if hasattr(B,'measure_config'):A.model.measure_config=dict(B.measure_config)
		if hasattr(B,_E):A.model.bridge_relationships=list(B.bridge_relationships)
		if hasattr(B,_F):A.model.active_relationship_choices=dict(B.active_relationship_choices)
		if hasattr(B,_P):A.model.duplicate_role_playing_dims=dict(B.duplicate_role_playing_dims)
	if hasattr(C,_U):
		E=C.config
		if hasattr(E,_R):A.config.pbi_mode=E.pbi_mode
		if hasattr(E,_S):A.config.dark_mode=E.dark_mode
		if hasattr(E,'output_format'):A.config.output_format=E.output_format
	return A
def reset_app_state():A=AppState();A._version=_STATE_VERSION;st.session_state[_STATE_KEY]=A;return A
def has_app_state():return _STATE_KEY in st.session_state
def migrate_legacy_state():
	B=get_app_state()
	if _H in st.session_state:
		A=st.session_state.selected_objects
		if A and not B.selection.selected_objects:B.selection.selected_objects=list(A)
	if _I in st.session_state:
		A=st.session_state.views_metadata
		if A and not B.selection.views_metadata:B.selection.views_metadata=list(A)
	if _G in st.session_state:
		A=st.session_state.wizard_step
		if isinstance(A,int)and B.wizard_step==0:B.wizard_step=A
	if _K in st.session_state:
		A=st.session_state.loaded_schemas
		if A and not B.tree.loaded_schemas:B.tree.loaded_schemas=dict(A)
	if _L in st.session_state:
		A=st.session_state.loaded_objects
		if A and not B.tree.loaded_objects:B.tree.loaded_objects=dict(A)
	if _M in st.session_state:
		A=st.session_state.expanded_nodes
		if A and not B.tree.expanded_nodes:B.tree.expanded_nodes=list(A)
	if _R in st.session_state:
		A=st.session_state.pbi_mode
		if A and B.config.pbi_mode==CONFIG.DEFAULT_PBI_MODE:B.config.pbi_mode=A
	if _S in st.session_state:
		A=st.session_state.dark_mode
		if isinstance(A,bool):B.config.dark_mode=A
	if _O in st.session_state:
		A=st.session_state.manual_relationships
		if A and not B.model.manual_relationships:B.model.manual_relationships=list(A)
	if _E in st.session_state:
		A=st.session_state.bridge_relationships
		if A and not B.model.bridge_relationships:B.model.bridge_relationships=list(A)
	if _F in st.session_state:
		A=st.session_state.active_relationship_choices
		if A and not B.model.active_relationship_choices:B.model.active_relationship_choices=dict(A)
	if _P in st.session_state:
		A=st.session_state.duplicate_role_playing_dims
		if A and not B.model.duplicate_role_playing_dims:B.model.duplicate_role_playing_dims=dict(A)
	if _N in st.session_state:
		A=st.session_state.selected_relationships
		if A and not B.model.selected_relationships:B.model.selected_relationships=dict(A)
_LEGACY_KEY_MAP={_G:(_G,_A),_H:(_T,_H),_I:(_T,_I),_K:(_J,_K),_L:(_J,_L),_M:(_J,_M),_W:(_J,_V),_N:(_D,_N),_O:(_D,_O),_E:(_D,_E),_F:(_D,_F),_P:(_D,_P),_R:(_U,_R),_S:(_U,_S),_X:(_Q,_X),_Y:(_Q,_Y),'_just_reset':(_Q,'just_reset')}
def sync_to_legacy():
	B=get_app_state()
	for(F,(C,D))in _LEGACY_KEY_MAP.items():
		try:
			if D is _A:A=getattr(B,C,_A)
			else:
				E=getattr(B,C,_A)
				if E is _A:continue
				A=getattr(E,D,_A)
				if A is _A:continue
			st.session_state[F]=A
		except AttributeError:pass
def sync_from_legacy():
	A=get_app_state()
	for(B,(C,D))in _LEGACY_KEY_MAP.items():
		if B not in st.session_state:continue
		E=st.session_state[B]
		if D is _A:setattr(A,C,E)
		else:F=getattr(A,C);setattr(F,D,E)
def _init_legacy_keys_if_missing():
	C=get_app_state()
	for(A,(D,E))in _LEGACY_KEY_MAP.items():
		if A in st.session_state:continue
		try:
			if E is _A:B=getattr(C,D,_A)
			else:
				F=getattr(C,D,_A)
				if F is _A:continue
				B=getattr(F,E,_A)
			if B is not _A:st.session_state[A]=B
			elif A in(_H,_I,_M):st.session_state[A]=[]
			elif A in(_K,_L,_N,_O,_E,_F,_P):st.session_state[A]={}
			elif A==_G:st.session_state[A]=0
			elif A==_W:st.session_state[A]=0
		except AttributeError:pass
def init_session_state():A=get_app_state();migrate_legacy_state();_init_legacy_keys_if_missing();return A
def get_state_value(key,default=_A):
	B=key;A=default
	if B not in _LEGACY_KEY_MAP:return st.session_state.get(B,A)
	C=get_app_state();D,E=_LEGACY_KEY_MAP[B]
	if E is _A:return getattr(C,D,A)
	else:
		F=getattr(C,D,_A)
		if F is _A:return A
		return getattr(F,E,A)
def set_state_value(key,value):
	B=value;A=key
	if A not in _LEGACY_KEY_MAP:st.session_state[A]=B;return
	C=get_app_state();D,E=_LEGACY_KEY_MAP[A]
	if E is _A:setattr(C,D,B)
	else:F=getattr(C,D);setattr(F,E,B)
	st.session_state[A]=B