_L='Technical Details'
_K='object_type'
_J='unknown'
_I='permission'
_H='authentication'
_G='connection'
_F='object'
_E='schema'
_D='database'
_C=False
_B=True
_A=None
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import Any,Callable,Optional,TypeVar
import traceback,streamlit as st
from.logging_config import get_logger,log_error
logger=get_logger(__name__)
T=TypeVar('T')
class ErrorCategory(Enum):CONNECTION=_G;AUTHENTICATION=_H;PERMISSION=_I;NOT_FOUND='not_found';VALIDATION='validation';GENERATION='generation';SNOWFLAKE='snowflake';POWER_BI='power_bi';INTERNAL='internal';UNKNOWN=_J
@dataclass
class ErrorContext:operation:str;details:dict[str,Any]=_A;suggestion:str=_A;docs_url:str=_A
class AppError(Exception):
	def __init__(A,message,category=ErrorCategory.UNKNOWN,context=_A,cause=_A):B=message;super().__init__(B);A.message=B;A.category=category;A.context=context;A.cause=cause
	def __str__(A):return A.message
class SnowflakeConnectionError(AppError):
	def __init__(A,message,context=_A,cause=_A):super().__init__(message,category=ErrorCategory.CONNECTION,context=context or ErrorContext(operation='Snowflake Connection',suggestion='Check your connection settings in ~/.snowflake/connections.toml'),cause=cause)
class SnowflakeAuthenticationError(AppError):
	def __init__(A,message,context=_A,cause=_A):super().__init__(message,category=ErrorCategory.AUTHENTICATION,context=context or ErrorContext(operation='Snowflake Authentication',suggestion='Verify your username, password, or private key configuration'),cause=cause)
class SnowflakePermissionError(AppError):
	def __init__(B,message,resource=_A,cause=_A):A=resource;super().__init__(message,category=ErrorCategory.PERMISSION,context=ErrorContext(operation='Snowflake Access',details={'resource':A}if A else _A,suggestion='Contact your Snowflake administrator to grant necessary permissions'),cause=cause)
class ObjectNotFoundError(AppError):
	def __init__(C,object_type,object_name,cause=_A):B=object_name;A=object_type;super().__init__(f"{A} '{B}' not found",category=ErrorCategory.NOT_FOUND,context=ErrorContext(operation=f"Fetch {A}",details={_K:A,'object_name':B},suggestion=f"Verify the {A.lower()} exists and you have access to it"),cause=cause)
class MetadataFetchError(AppError):
	def __init__(E,message,database=_A,schema=_A,object_name=_A,cause=_A):
		D=object_name;C=schema;B=database;A={}
		if B:A[_D]=B
		if C:A[_E]=C
		if D:A[_F]=D
		super().__init__(message,category=ErrorCategory.SNOWFLAKE,context=ErrorContext(operation='Fetch Metadata',details=A if A else _A,suggestion='Check that the object exists and you have SELECT permissions'),cause=cause)
class ValidationError(AppError):
	def __init__(D,message,field=_A,value=_A,cause=_A):
		C=value;B=field;A={}
		if B:A['field']=B
		if C is not _A:A['value']=str(C)[:50]
		super().__init__(message,category=ErrorCategory.VALIDATION,context=ErrorContext(operation='Input Validation',details=A if A else _A),cause=cause)
class GenerationError(AppError):
	def __init__(B,message,output_type=_A,cause=_A):A=output_type;super().__init__(message,category=ErrorCategory.GENERATION,context=ErrorContext(operation=f"Generate {A or'Output'}",details={'output_type':A}if A else _A,suggestion='Try generating a different format or check the error details'),cause=cause)
class PowerBIError(AppError):
	def __init__(A,message,cause=_A):super().__init__(message,category=ErrorCategory.POWER_BI,context=ErrorContext(operation='Power BI Operation',suggestion='Ensure Power BI Desktop is installed and accessible'),cause=cause)
def show_error(message,details=_A,suggestion=_A,show_details=_B):
	B=suggestion;A=details;st.error(f"**Error:** {message}")
	if B:st.info(f"**Suggestion:** {B}")
	if A and show_details:
		with st.expander(_L,expanded=_C):st.code(A,language='text')
def show_error_with_help(error,show_traceback=_C):
	A=error;st.error(f"**{A.category.value.title()} Error:** {A.message}")
	if A.context:
		B=A.context
		if B.suggestion:st.info(f"**Suggestion:** {B.suggestion}")
		if B.details:
			with st.expander('Error Details',expanded=_C):
				for(C,D)in B.details.items():st.text(f"{C}: {D}")
		if B.docs_url:st.markdown(f"[View Documentation]({B.docs_url})")
	if A.cause and show_traceback:
		with st.expander(_L,expanded=_C):st.code(traceback.format_exception(type(A.cause),A.cause,A.cause.__traceback__))
def show_warning(message,details=_A):
	A=details;st.warning(f"**Warning:** {message}")
	if A:st.caption(A)
def show_recoverable_error(message,retry_label='Retry',on_retry=_A,suggestion=_A):
	B=suggestion;A=on_retry;st.error(f"**Error:** {message}")
	if B:st.info(f"**Suggestion:** {B}")
	C,D=st.columns([1,4])
	with C:
		if st.button(retry_label,type='primary'):
			if A:A()
			return _B
	return _C
def handle_error(error,operation=_A,show_in_ui=_B,reraise=_C,suggestion=_A,details=_A):
	A=error;log_error(message=operation or'Operation failed',error=A,exc_info=_B)
	if show_in_ui:
		if isinstance(A,AppError):show_error_with_help(A)
		else:show_error(message=str(A),details=details or traceback.format_exc(),suggestion=suggestion or'If this error persists, please contact support')
	if reraise:raise A
def safe_execute(func,*A,default=_A,operation=_A,show_error_ui=_B,**B):
	try:return func(*A,**B)
	except Exception as C:handle_error(C,operation=operation,show_in_ui=show_error_ui);return default
def error_boundary(operation=_A,default=_A,show_error_ui=_B):
	def A(func):
		A=func
		@wraps(A)
		def B(*B,**C):
			try:return A(*B,**C)
			except Exception as D:handle_error(D,operation=operation or A.__name__,show_in_ui=show_error_ui);return default
		return B
	return A
def convert_snowflake_error(error,context=_A):
	B=error;A=context;C=str(B).lower();A=A or{}
	if any(A in C for A in[_H,'password','login','credentials']):return SnowflakeAuthenticationError('Authentication failed. Please check your credentials.',cause=B)
	if any(A in C for A in[_I,'access denied','insufficient privileges','not authorized']):D=A.get(_F)or A.get(_E)or A.get(_D);return SnowflakePermissionError(f"Insufficient permissions to access the requested resource.",resource=D,cause=B)
	if any(A in C for A in['does not exist','not found',_J]):E=A.get(_K,'Object');F=A.get(_F)or A.get(_E)or A.get(_D)or'Unknown';return ObjectNotFoundError(E,F,cause=B)
	if any(A in C for A in[_G,'network','timeout','unreachable']):return SnowflakeConnectionError('Failed to connect to Snowflake. Check your network connection.',cause=B)
	return MetadataFetchError(str(B),database=A.get(_D),schema=A.get(_E),object_name=A.get(_F),cause=B)
class error_context:
	def __init__(A,operation,show_in_ui=_B,**B):A.operation=operation;A.show_in_ui=show_in_ui;A.context=B
	def __enter__(A):return A
	def __exit__(B,exc_type,exc_val,exc_tb):
		A=exc_val
		if A is not _A:
			if not isinstance(A,AppError):A=convert_snowflake_error(A,B.context)
			handle_error(A,operation=B.operation,show_in_ui=B.show_in_ui);return _B
		return _C