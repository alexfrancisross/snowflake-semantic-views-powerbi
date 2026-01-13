_A='views_metadata'
import streamlit as st
from pages import BasePage,PageContext,register_page
from utils.logging_config import get_logger,log_user_action
from utils.snowflake_theme import icon_header
from utils.ui_helpers import get_object_icon_key,get_object_icon_html
logger=get_logger(__name__)
class SelectPage(BasePage):
	def __init__(A,step_index=0):super().__init__(step_index)
	def render(D,context):
		st.markdown(f"## {icon_header('select','Select Objects',size=28)}",unsafe_allow_html=True);st.info('👈 Use the **tree navigator in the sidebar** to select tables, views, and semantic views.');A=st.session_state.get(_A,[])
		if A:
			st.success(f"**{len(A)} objects selected**")
			for B in A:C=get_object_icon_html(B.object_type,size=16);st.markdown(f"{C} {B.full_name}",unsafe_allow_html=True)
			st.divider()
			if st.button('Next: Review Selection ->',type='primary',width='stretch'):log_user_action('navigate_step',{'from':0,'to':1,'objects_selected':len(A)});st.session_state.wizard_step=1;st.rerun()
		else:st.warning('Select at least one object to continue.')
	def validate(B,context):A=st.session_state.get(_A,[]);return len(A)>0