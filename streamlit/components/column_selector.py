_M='description'
_L='analytics'
_K='is_primary_key'
_J='NUMBER'
_I='SUM'
_H='collapsed'
_G='METRIC'
_F='VARCHAR'
_E='data_type'
_D=None
_C='DIMENSION'
_B=True
_A=False
from dataclasses import dataclass,field
from typing import Any
import streamlit as st
from tooltips import dimensions_label,metrics_label,facts_label
from snowflake_theme import get_svg_icon
from snowflake_ddl_generator import SemanticColumnConfig,SNOWFLAKE_AGGREGATIONS
from logging_config import get_logger
logger=get_logger(__name__)
@dataclass
class ColumnZoneConfig:disable_metrics:bool=_A;disable_facts:bool=_A;is_base_table:bool=_B;affected_measures:list[str]=field(default_factory=list);show_descriptions:bool=_B;show_aggregations:bool=_B
def is_numeric_type(data_type):
	A=data_type
	if not A:return _A
	B=A.upper();return any(A in B for A in[_J,'DECIMAL','FLOAT','DOUBLE','INT','NUMERIC'])
def is_date_type(data_type):
	A=data_type
	if not A:return _A
	B=A.upper();return'DATE'in B or'TIME'in B
def is_string_type(data_type):
	A=data_type
	if not A:return _A
	B=A.upper();return any(A in B for A in[_F,'CHAR','STRING','TEXT'])
def is_key_column(column_name,is_primary_key=_A):
	if is_primary_key:return _B
	A=column_name.upper();return'KEY'in A or A.endswith('_ID')
def classify_column(column,is_base_table=_B,disable_metrics=_A):
	A=column;C=getattr(A,_K,_A)
	if is_key_column(A.name,C):return _C
	B=getattr(A,_E,_D)
	if is_numeric_type(B):
		if is_base_table and not disable_metrics:return _G
		return _C
	if is_date_type(B):return _C
	if is_string_type(B):return _C
	return _C
@dataclass
class ColumnZoneState:
	dimensions:list[str]=field(default_factory=list);metrics:list[str]=field(default_factory=list);facts:list[str]=field(default_factory=list);aggregations:dict[str,str]=field(default_factory=dict);descriptions:dict[str,str]=field(default_factory=dict)
	@property
	def all_selected(self):A=self;return A.dimensions+A.metrics+A.facts
	@property
	def count(self):return len(self.all_selected)
class ColumnSelector:
	def __init__(A,columns,key_prefix,config=_D):B=columns;A.columns=B;A.key_prefix=key_prefix;A.config=config or ColumnZoneConfig();A._column_names=[A.name for A in B];A._column_info={A.name:A for A in B};A._init_state()
	def _init_state(A):
		G=f"{A.key_prefix}_dimensions";H=f"{A.key_prefix}_metrics";I=f"{A.key_prefix}_facts"
		if G in st.session_state:return
		C=[];D=[];E=[]
		for B in A.columns:
			F=classify_column(B,is_base_table=A.config.is_base_table,disable_metrics=A.config.disable_metrics)
			if F==_C:C.append(B.name)
			elif F==_G:D.append(B.name)
			elif F=='FACT':E.append(B.name)
		st.session_state[G]=C;st.session_state[H]=D;st.session_state[I]=E;logger.debug(f"Initialized column zones for {A.key_prefix}: {len(C)} dims, {len(D)} metrics, {len(E)} facts")
	def _get_column_label(B,col):
		A=col.name
		if getattr(col,_K,_A):A+=' 🔑'
		return A
	def _render_dimensions_zone(A):B=f"{A.key_prefix}_dimensions";st.markdown(f"**{get_svg_icon(_L,16)} {dimensions_label()}**",unsafe_allow_html=_B);st.caption('Attributes to group by');C=st.multiselect('Dimensions',options=A._column_names,default=st.session_state.get(B,[]),key=f"{A.key_prefix}_dim_select",label_visibility=_H);st.session_state[B]=C;return C
	def _render_metrics_zone(A,selected_dims):
		C=f"{A.key_prefix}_metrics";st.markdown(f"**{get_svg_icon(_L,16)} {metrics_label()}**",unsafe_allow_html=_B);st.caption('Measures to aggregate')
		if A.config.disable_metrics:st.warning('⊘ Metrics disabled (dimension table)');return[]
		D=[A for A in A._column_names if A not in selected_dims];E=[A for A in st.session_state.get(C,[])if A in D];B=st.multiselect('Metrics',options=D,default=E,key=f"{A.key_prefix}_metric_select",label_visibility=_H)
		if B and A.config.show_aggregations:
			st.markdown('*Aggregations:*')
			for F in B:A._render_aggregation_dropdown(F)
		st.session_state[C]=B;return B
	def _render_aggregation_dropdown(C,metric_name):
		B=metric_name;A=f"{C.key_prefix}_agg_{B}"
		if A not in st.session_state:st.session_state[A]=_I
		D=st.session_state[A];E=SNOWFLAKE_AGGREGATIONS.index(D)if D in SNOWFLAKE_AGGREGATIONS else 0;F=st.selectbox(B,options=SNOWFLAKE_AGGREGATIONS,index=E,key=f"{C.key_prefix}_agg_select_{B}");st.session_state[A]=F
	def _render_facts_zone(A,selected_dims,selected_metrics):
		B=f"{A.key_prefix}_facts";st.markdown(f"**{get_svg_icon('docs',16)} {facts_label()}**",unsafe_allow_html=_B);st.caption('Detail-level data')
		if A.config.disable_facts:st.warning('⊘ Facts disabled (dimension table)');return[]
		C=[A for A in A._column_names if A not in selected_dims and A not in selected_metrics];E=[A for A in st.session_state.get(B,[])if A in C];D=st.multiselect('Facts',options=C,default=E,key=f"{A.key_prefix}_fact_select",label_visibility=_H);st.session_state[B]=D;return D
	def _render_descriptions(B,selected_dims,selected_metrics,selected_facts):
		G=selected_metrics;F=selected_dims;H=F+G+selected_facts
		if not H or not B.config.show_descriptions:return
		with st.expander('Column Descriptions',expanded=_A):
			st.caption('Override descriptions from Snowflake metadata')
			for A in H:
				D=B._column_info[A];I=''
				if hasattr(D,_M)and D.description:I=D.description
				C=f"{B.key_prefix}_desc_{A}"
				if C not in st.session_state:st.session_state[C]=I
				if A in F:E='📊'
				elif A in G:E='📈'
				else:E='📝'
				J=st.text_input(f"{E} {A}",value=st.session_state[C],placeholder=f"Description for {A}",key=f"{B.key_prefix}_desc_input_{A}");st.session_state[C]=J
	def _get_description(B,col_name):
		C=col_name;E=f"{B.key_prefix}_desc_{C}";D=st.session_state.get(E,'')
		if D:return D
		A=B._column_info.get(C)
		if A and hasattr(A,_M)and A.description:return A.description
	def _build_configs(B,selected_dims,selected_metrics,selected_facts):
		D=[]
		for A in selected_dims:C=B._column_info[A];D.append(SemanticColumnConfig(source_column=A,semantic_name=A.lower(),kind=_C,data_type=getattr(C,_E,_D)or _F,description=B._get_description(A)))
		for A in selected_metrics:
			C=B._column_info[A];H=f"{B.key_prefix}_agg_{A}";E=st.session_state.get(H,_I);I=f"{A.lower()}_{E.lower()}";F=B._get_description(A)
			if F:G=f"{E} of {F}"
			else:G=f"{E} of {A}"
			D.append(SemanticColumnConfig(source_column=A,semantic_name=I,kind=_G,data_type=getattr(C,_E,_D)or _J,aggregation=E,description=G))
		for A in selected_facts:C=B._column_info[A];D.append(SemanticColumnConfig(source_column=A,semantic_name=A.lower(),kind='FACT',data_type=getattr(C,_E,_D)or _F,description=B._get_description(A)))
		return D
	def render(A):
		E,F,G=st.columns(3)
		with E:B=A._render_dimensions_zone()
		with F:C=A._render_metrics_zone(B)
		with G:D=A._render_facts_zone(B,C)
		A._render_descriptions(B,C,D);return A._build_configs(B,C,D)
	def get_state(A):
		D=f"{A.key_prefix}_dimensions";B=f"{A.key_prefix}_metrics";E=f"{A.key_prefix}_facts";F={}
		for G in st.session_state.get(B,[]):J=f"{A.key_prefix}_agg_{G}";F[G]=st.session_state.get(J,_I)
		H={};K=st.session_state.get(D,[])+st.session_state.get(B,[])+st.session_state.get(E,[])
		for I in K:
			C=f"{A.key_prefix}_desc_{I}"
			if C in st.session_state and st.session_state[C]:H[I]=st.session_state[C]
		return ColumnZoneState(dimensions=st.session_state.get(D,[]),metrics=st.session_state.get(B,[]),facts=st.session_state.get(E,[]),aggregations=F,descriptions=H)
def render_column_zones(columns,key_prefix,affected_measures=_D,disable_metrics=_A,disable_facts=_A,is_base_table=_B):A=ColumnZoneConfig(disable_metrics=disable_metrics,disable_facts=disable_facts,is_base_table=is_base_table,affected_measures=affected_measures or[]);B=ColumnSelector(columns,key_prefix,A);return B.render()