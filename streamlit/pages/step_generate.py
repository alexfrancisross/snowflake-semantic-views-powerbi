_F='duplicate_role_playing_dims'
_E='active_relationship_choices'
_D='selected_relationships'
_C='views_metadata'
_B=None
_A=True
import hashlib,streamlit as st
from pages import BasePage,PageContext,register_page
from utils.logging_config import get_logger,log_user_action
from utils.error_handling import show_error
from utils.snowflake_theme import icon_header
from utils.pbit_generator import create_pbit_file,collect_all_relationships
from utils.tmdl_generator import generate_multi_view_tmdl_project
from utils.zip_packager import create_zip_with_connector
from utils.tooltips import snowflake_spinner
from utils.ui_helpers import generate_project_name
logger=get_logger(__name__)
class PBIMode:DIRECT_QUERY='directQuery';IMPORT='import'
@register_page(2)
class GeneratePage(BasePage):
	def __init__(A,step_index=2):super().__init__(step_index)
	def render(D,context):
		H='collapsed';G='Connection type:';C='Live Connection (DirectQuery)';st.markdown(f"## {icon_header('rocket','Generate Output',size=28)}",unsafe_allow_html=_A);A=st.session_state.get(_C,[]);E=st.session_state.get('selected_objects',[]);logger.info(f"[GENERATE] selected_objects={len(E)}, views_metadata={len(A)}")
		if not A:
			st.warning(f"No metadata loaded. ({len(E)} objects selected but metadata not loaded)");st.caption('Go back to Step 1 to load object metadata.')
			if st.button('← Back to Review'):st.session_state.wizard_step=0;st.rerun()
			return
		I=D._get_connection_info(context);J=generate_project_name(A);K=st.text_input('Project Name',value=J,help='Name for the generated Power BI project');st.markdown('**How should Power BI connect to Snowflake?**');L=any(A.object_type=='SEMANTIC_VIEW'for A in A)
		if L:st.radio(G,options=[C],horizontal=_A,key='pbi_mode_radio_semantic',label_visibility=H,disabled=_A);B=PBIMode.DIRECT_QUERY;st.info('Semantic views require DirectQuery mode.')
		else:M=st.radio(G,options=[C,'Cached Data (Import)'],horizontal=_A,key='pbi_mode_radio_standard',label_visibility=H,index=0);B=PBIMode.DIRECT_QUERY if M==C else PBIMode.IMPORT
		st.session_state.pbi_mode=B;N=st.radio('Output Format',['PBIT (Recommended)','PBIP (ZIP)'],index=0,horizontal=_A,help='PBIT: Template file. PBIP: Project folder (requires Developer Mode).',key='output_format_radio');F,O,P=D._get_cached_file(N,A,I,K,B)
		if F:st.download_button(label='Download Power BI File',data=F,file_name=O,mime=P,type='primary',width='stretch')
		st.divider()
		if st.button('← Back to Design Data Model'):log_user_action('navigate_step',{'from':2,'to':1});st.session_state.wizard_step=1;st.rerun()
	def _get_connection_info(C,context):
		if'conn_info'in st.session_state:return st.session_state.conn_info
		try:from utils import get_session_info as A;return A(context.session)
		except Exception as B:logger.error(f"Could not get connection info: {B}",exc_info=_A);return
	def _compute_cache_key(H,output_format,views_metadata,conn_info,project_name,pbi_mode):A='|'.join(f"{A.database}.{A.schema}.{A.view}"for A in sorted(views_metadata,key=lambda x:x.view));B=st.session_state.get(_D,{});C=str(sorted(B.items()));D=st.session_state.get(_E,{});E=str(sorted(D.items()));F=st.session_state.get(_F);G=f"{output_format}|{A}|{conn_info}|{project_name}|{pbi_mode}|{C}|{E}|{F}";return hashlib.md5(G.encode()).hexdigest()
	def _get_cached_file(D,output_format,views_metadata,conn_info,project_name,pbi_mode):
		P='mime';O='name';N='data';M='key';L='_generated_file_cache';H=pbi_mode;G=project_name;F=views_metadata;E=output_format;B=conn_info
		if B is _B:st.error('Unable to retrieve Snowflake connection information. Please check your connection and try again.');return _B,_B,_B
		I=D._compute_cache_key(E,F,B,G,H);A=st.session_state.get(L,{})
		if A.get(M)==I:return A[N],A[O],A[P]
		with snowflake_spinner('Generating Power BI file...'):C,J,K=D._generate_file(E,F,B,G,H)
		if C:st.session_state[L]={M:I,N:C,O:J,P:K}
		return C,J,K
	def _generate_file(I,output_format,views_metadata,conn_info,project_name,pbi_mode):
		H='warehouse';G='server';E=pbi_mode;C=views_metadata;B=project_name;A=conn_info;J=I._get_selected_relationships(C);K=st.session_state.get(_F);L=st.session_state.get(_E,{})
		try:
			if output_format.startswith('PBIT'):D=create_pbit_file(C,A.get(G,''),A.get(H,''),B,selected_relationships=J,duplicate_role_playing_dims=K,mode=E,user_active_choices=L);return D,f"{B}.pbit",'application/octet-stream'
			else:M=generate_multi_view_tmdl_project(C,A.get(G,''),A.get(H,''),B,mode=E);D=create_zip_with_connector(M);return D,f"{B}_PowerBI.zip",'application/zip'
		except Exception as F:logger.error(f"Error generating file: {F}",exc_info=_A);st.error(f"Error generating file: {F}");return _B,_B,_B
	def _get_selected_relationships(F,views_metadata):
		C=collect_all_relationships(views_metadata);D=st.session_state.get('bridge_relationships',[]);E=st.session_state.get('manual_relationships',[]);A=list(C)+D
		for B in E:
			if hasattr(B,'to_relationship_metadata'):A.append(B.to_relationship_metadata())
			else:A.append(B)
		if A and _D in st.session_state:return[A for A in A if st.session_state.selected_relationships.get(A.relationship_id,_A)]
		return _B if not A else A
	def validate(B,context):A=st.session_state.get(_C,[]);return len(A)>0