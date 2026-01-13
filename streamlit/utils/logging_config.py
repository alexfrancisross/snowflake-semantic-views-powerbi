_E='performance'
_D='WARNING'
_C='pbi_generator'
_B=' | '
_A=None
import logging,os,sys
from datetime import datetime
from functools import wraps
from typing import Any,Callable,Optional
import streamlit as st
from.config import CONFIG
LOG_FORMAT='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
LOG_DATE_FORMAT='%Y-%m-%d %H:%M:%S'
LOG_LEVEL_MAP={'DEBUG':logging.DEBUG,'INFO':logging.INFO,_D:logging.WARNING,'ERROR':logging.ERROR,'CRITICAL':logging.CRITICAL}
def get_log_level():A=os.environ.get('LOG_LEVEL',_D).upper();return LOG_LEVEL_MAP.get(A,logging.WARNING)
DEFAULT_LOG_LEVEL=get_log_level()
def setup_logging(level=DEFAULT_LOG_LEVEL,log_to_console=True,log_to_file=False,log_file_path=_A):
	E=log_file_path;B=level;F=logging.Formatter(LOG_FORMAT,datefmt=LOG_DATE_FORMAT);A=logging.getLogger(_C);A.setLevel(B);A.handlers.clear()
	if log_to_console:C=logging.StreamHandler(sys.stderr);C.setLevel(B);C.setFormatter(F);A.addHandler(C)
	if log_to_file and E:D=logging.FileHandler(E,encoding='utf-8');D.setLevel(B);D.setFormatter(F);A.addHandler(D)
	return A
def get_logger(name):
	A=name
	if not A.startswith(_C):A=f"pbi_generator.{A}"
	return logging.getLogger(A)
_root_logger=setup_logging()
def log_user_action(action,details=_A,logger=_A):
	B=details;A=logger
	if A is _A:A=get_logger('user_actions')
	C=''
	if B:C=_B+_B.join(f"{A}={B}"for(A,B)in B.items())
	A.info(f"ACTION: {action}{C}")
def log_performance(operation,duration_ms,details=_A,logger=_A):
	B=details;A=logger
	if A is _A:A=get_logger(_E)
	C=''
	if B:C=_B+_B.join(f"{A}={B}"for(A,B)in B.items())
	A.info(f"PERF: {operation} | {duration_ms:.2f}ms{C}")
def log_error(message,error=_A,details=_A,logger=_A,exc_info=False):
	C=details;B=logger;A=error
	if B is _A:B=get_logger('errors')
	D=''
	if C:D=_B+_B.join(f"{A}={B}"for(A,B)in C.items())
	E=''
	if A:E=f" | error_type={type(A).__name__} | error_msg={str(A)}"
	B.error(f"ERROR: {message}{E}{D}",exc_info=exc_info)
def log_function_call(logger=_A):
	A=logger
	def B(func):
		B=func;nonlocal A
		if A is _A:A=get_logger(B.__module__)
		@wraps(B)
		def C(*D,**E):
			C=B.__name__;A.debug(f"ENTER: {C}")
			try:F=B(*D,**E);A.debug(f"EXIT: {C}");return F
			except Exception as G:A.error(f"EXCEPTION in {C}: {G}",exc_info=True);raise
		return C
	return B
def timed(logger=_A):
	A=logger
	def B(func):
		B=func;nonlocal A
		if A is _A:A=get_logger(_E)
		@wraps(B)
		def C(*D,**E):
			import time as C;F=C.perf_counter()
			try:return B(*D,**E)
			finally:G=(C.perf_counter()-F)*1000;log_performance(B.__name__,G,logger=A)
		return C
	return B
class StreamlitLogHandler(logging.Handler):
	def emit(B,record):
		A=record
		try:
			C=B.format(A)
			if A.levelno>=logging.ERROR:st.error(f"Error: {A.getMessage()}")
			elif A.levelno>=logging.WARNING:st.warning(f"Warning: {A.getMessage()}")
		except Exception:B.handleError(A)
def enable_streamlit_logging(level=logging.WARNING):A=StreamlitLogHandler();A.setLevel(level);B=logging.getLogger(_C);B.addHandler(A)
def log_session_state(logger=_A):
	A=logger
	if A is _A:A=get_logger('debug')
	A.debug('=== SESSION STATE ===')
	for(C,D)in st.session_state.items():
		B=str(D)
		if len(B)>100:B=B[:100]+'...'
		A.debug(f"  {C}: {B}")
	A.debug('=====================')
def log_app_state(logger=_A):
	A=logger
	if A is _A:A=get_logger('debug')
	try:from session_manager import get_app_state as C;B=C();A.debug('=== APP STATE ===');A.debug(f"  wizard_step: {B.wizard_step}");A.debug(f"  selection.count: {B.selection.count}");A.debug(f"  tree.loaded_schemas: {len(B.tree.loaded_schemas)} databases");A.debug(f"  model.relationships: {len(B.model.selected_relationships)} tracked");A.debug(f"  config.pbi_mode: {B.config.pbi_mode}");A.debug(f"  config.dark_mode: {B.config.dark_mode}");A.debug('=================')
	except Exception as D:A.debug(f"Could not log app state: {D}")