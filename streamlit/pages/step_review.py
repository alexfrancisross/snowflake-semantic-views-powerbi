_A='views_metadata'
import streamlit as st
from pages import BasePage,PageContext,register_page
from utils.logging_config import get_logger,log_user_action
from utils.snowflake_theme import icon_header
from utils.ui_helpers import get_object_icon_key,get_object_icon_html,get_connector_badge_html,display_column_metadata
logger=get_logger(__name__)
@register_page(0)
class ReviewPage(BasePage):
	def __init__(A,step_index=0):super().__init__(step_index)
	def render(K,context):
		st.markdown(f"## {icon_header('verified','Review Selected Objects',size=28)}",unsafe_allow_html=True);B=st.session_state.get(_A,[])
		if not B:st.info('👈 Use the **sidebar tree navigator** to select tables, views, and semantic views.');return
		E=sum(len(A.columns)for A in B);F=any(A.object_type=='SEMANTIC_VIEW'for A in B);G=any(A.object_type in('TABLE','VIEW')for A in B)
		if F and G:st.info('**Mixed selection:** Semantic views use Custom Connector, standard tables use Native Snowflake Connector.')
		for A in B:
			H=get_object_icon_html(A.object_type,size=20);I=get_connector_badge_html(A.object_type);st.markdown(f"{H} **{A.full_name}** ({len(A.columns)} columns){I}",unsafe_allow_html=True)
			if A.table_metadata and A.table_metadata.comment:st.caption(f"📝 {A.table_metadata.comment}")
			with st.expander('Show columns',expanded=False):display_column_metadata(A)
		J={A.view for A in B};C=set()
		for A in B:
			if A.relationships:
				for D in A.relationships:
					if D.to_table not in J:C.add(D.to_table)
		if C:st.warning(f"**Suggested tables:** {', '.join(sorted(C))}")
		st.divider()
		if st.button('Next: Design Data Model ->',type='primary',width='stretch'):log_user_action('navigate_step',{'from':0,'to':1,'objects_count':len(B),'total_columns':E});st.session_state.wizard_step=1;st.rerun()
	def validate(B,context):A=st.session_state.get(_A,[]);return len(A)>0