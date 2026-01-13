_B=False
_A=True
from abc import ABC,abstractmethod
from dataclasses import dataclass
from typing import Any,TYPE_CHECKING
import streamlit as st
from utils.config import CONFIG,WIZARD_STEPS,get_wizard_step_by_index
from utils.logging_config import get_logger
from utils.error_handling import show_error
if TYPE_CHECKING:from session_manager import AppState
logger=get_logger(__name__)
@dataclass
class PageContext:session:Any;app_state:'AppState';step_index:int
class BasePage(ABC):
	def __init__(A,step_index):B=step_index;A.step_index=B;A.step_config=get_wizard_step_by_index(B)
	@property
	def name(self):A=self;return A.step_config.name if A.step_config else f"Step {A.step_index}"
	@property
	def description(self):return self.step_config.description if self.step_config else''
	@property
	def icon(self):return self.step_config.icon if self.step_config else'info'
	def render_header(A):
		st.subheader(f"{A.name}")
		if A.description:st.caption(A.description)
	def render_navigation_buttons(A,can_go_back=_A,can_go_next=_A,back_label='Back',next_label='Next',next_disabled=_B):
		D='stretch';E,G,F=st.columns([1,4,1]);B=_B;C=_B
		with E:
			if can_go_back and A.step_index>0:
				if st.button(f"← {back_label}",width=D):B=_A;A._go_to_step(A.step_index-1)
		with F:
			if can_go_next and A.step_index<CONFIG.WIZARD_TOTAL_STEPS-1:
				if st.button(f"{next_label} ->",type='primary',width=D,disabled=next_disabled):C=_A;A._go_to_step(A.step_index+1)
		return B,C
	def _go_to_step(A,step):st.session_state.wizard_step=step;st.rerun()
	@abstractmethod
	def render(self,context):0
	def validate(A,context):return _A
_page_registry={}
def register_page(step_index):
	def A(cls):_page_registry[step_index]=cls;return cls
	return A
def get_page_by_step(step_index):
	A=step_index;B=_page_registry.get(A)
	if B:return B(A)
def is_page_implemented(step_index):return step_index in _page_registry
def render_current_step(session,app_state):
	B=app_state;import streamlit.components.v1 as E;E.html("<script>\n        window.parent.document.querySelector('section.main').scrollTo(0, 0);\n        </script>",height=0)
	if'wizard_step'in st.session_state:B.wizard_step=st.session_state.wizard_step
	A=B.wizard_step;C=get_page_by_step(A);logger.info(f"[PAGE_SYSTEM] current_step={A}, page={C}, registry_keys={list(_page_registry.keys())}")
	if C is None:logger.error(f"[PAGE_SYSTEM] No page registered for step {A}! Registry has: {list(_page_registry.keys())}");return _B
	F=PageContext(session=session,app_state=B,step_index=A)
	try:C.render(F);return _A
	except Exception as D:logger.error(f"Error rendering page {A}: {D}",exc_info=_A);st.session_state._page_render_error=str(D);show_error(f"Error rendering wizard step",details=str(D),suggestion='Try refreshing the page or starting over');return _B
try:from pages import step_review;logger.debug('[PAGE_SYSTEM] Successfully imported step_review')
except Exception as e:logger.error(f"[PAGE_SYSTEM] Failed to import step_review: {e}",exc_info=_A)
try:from pages import step_model;logger.debug('[PAGE_SYSTEM] Successfully imported step_model')
except Exception as e:logger.error(f"[PAGE_SYSTEM] Failed to import step_model: {e}",exc_info=_A)
try:from pages import step_generate;logger.debug('[PAGE_SYSTEM] Successfully imported step_generate')
except Exception as e:logger.error(f"[PAGE_SYSTEM] Failed to import step_generate: {e}",exc_info=_A)
logger.info(f"[PAGE_SYSTEM] Final registry after imports: {list(_page_registry.keys())}")
__all__=['BasePage','PageContext','register_page','get_page_by_step','is_page_implemented','render_current_step']