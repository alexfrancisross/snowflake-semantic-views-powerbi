import streamlit as st
from pages import BasePage,PageContext,register_page
from utils.logging_config import get_logger,log_user_action
from utils.error_handling import show_error
from utils.snowflake_theme import icon_header
from utils.pbit_generator import collect_all_relationships
from utils.metadata_fetcher import detect_all_relationships,detect_schema_type,identify_base_table
logger=get_logger(__name__)
class SemanticPage(BasePage):
	def __init__(A,step_index=2):super().__init__(step_index)
	def render(D,context):
		C='from';B='navigate_step';st.markdown(f"## {icon_header('cloud','Create Snowflake Semantic View (Optional)',size=28)}",unsafe_allow_html=True);E=st.session_state.get('views_metadata',[]);A=[A for A in E if A.object_type!='SEMANTIC_VIEW']
		if len(A)>=2:D._render_multi_table_ui(context.session,A)
		else:st.info('Select 2+ tables to create a semantic view combining them.')
		st.divider();F,G=st.columns(2)
		with F:
			if st.button('← Back to Design Data Model'):log_user_action(B,{C:2,'to':1});st.session_state.wizard_step=1;st.rerun()
		with G:
			if st.button('Next: Download PBI Workbook ->',type='primary',width='stretch'):log_user_action(B,{C:2,'to':3});st.session_state.wizard_step=3;st.rerun()
	def _render_multi_table_ui(K,session,non_semantic_tables):
		C=session;A=non_semantic_tables
		try:
			from streamlit_app import _render_n_table_semantic_view_ui as F;G=collect_all_relationships(st.session_state.views_metadata)
			if G:
				try:
					B=detect_all_relationships(C,A)
					if B:
						H=detect_schema_type(A,B);D=identify_base_table(A,B)
						if D:I=A[0].database;J=A[0].schema;F(tables=A,relationships=B,base_table=D,schema_type=H,db_name=I,schema_name=J,session=C)
						else:st.warning('Could not determine base table.')
					else:st.warning('No relationships detected between selected tables.')
				except Exception as E:logger.error(f"Error detecting relationships: {E}",exc_info=True);show_error('Error detecting relationships',details=str(E),suggestion='Check that tables have foreign key constraints defined')
			else:st.info('Select 2+ tables with relationships to create a semantic view.')
		except ImportError:st.info('Semantic view creation is available when tables with relationships are selected. This feature allows you to combine multiple tables into a single semantic view.')
	def validate(A,context):return True