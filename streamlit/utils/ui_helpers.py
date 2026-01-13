_H='Native Connector'
_G='Custom Connector'
_F='native'
_E='custom'
_D='label'
_C='text_color'
_B='bg_color'
_A='SEMANTIC_VIEW'
from datetime import datetime
from typing import TYPE_CHECKING
import pandas as pd,streamlit as st
from.snowflake_theme import get_svg_icon
if TYPE_CHECKING:from.metadata_fetcher import SemanticViewMetadata
OBJECT_TYPE_ICONS={_A:'cube','VIEW':'view','TABLE':'table'}
def get_object_icon_key(object_type):return OBJECT_TYPE_ICONS.get(object_type,'table')
def get_object_icon_html(object_type,size=18):A=get_object_icon_key(object_type);return get_svg_icon(A,size)
CONNECTOR_BADGE_STYLES={_E:{_B:'#D4EDDA',_C:'#155724',_D:_G},_F:{_B:'#D1ECF1',_C:'#0C5460',_D:_H}}
def get_connector_badge_html(object_type):A=CONNECTOR_BADGE_STYLES[_E]if object_type==_A else CONNECTOR_BADGE_STYLES[_F];return f'<span style="background-color: {A[_B]}; color: {A[_C]}; padding: 2px 8px; border-radius: 8px; font-size: 0.75em; font-weight: 600; margin-left: 8px;">{A[_D]}</span>'
def get_connector_badge(object_type):
	if object_type==_A:return _G
	return _H
def generate_project_name(views_metadata):
	A=views_metadata;B=datetime.now().strftime('%Y%m%d')
	if not A:return f"SnowflakePowerBI_{B}"
	C=A[0];D=C.database;E=C.schema;F=C.view
	if len(A)==1:return f"{D}.{E}.{F}_{B}"
	else:G=len(A);return f"{D}.{E}.{G}_OBJECTS_{B}"
def display_column_metadata(metadata):
	A=metadata;C=[]
	for B in A.columns:
		D={'Column':B.name,'Type':B.data_type}
		if A.object_type==_A:D['Kind']=B.kind
		D['Description']=B.description or'-';C.append(D)
	if C:E=pd.DataFrame(C);st.dataframe(E,width='stretch',hide_index=True)
	else:F='semantic view'if A.object_type==_A else A.object_type.lower();st.info(f"No columns found in this {F}.")