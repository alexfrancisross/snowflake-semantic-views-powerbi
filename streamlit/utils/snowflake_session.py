_J=False
_I='role'
_H='schema'
_G='database'
_F='warehouse'
_E='user'
_D='account'
_C='default'
_B=True
_A=None
import os,sys
from pathlib import Path
from typing import Optional
import streamlit as st
from.logging_config import get_logger
logger=get_logger(__name__)
try:from snowflake.snowpark import Session;from snowflake.snowpark.context import get_active_session;SNOWPARK_AVAILABLE=_B
except ImportError:SNOWPARK_AVAILABLE=_J;Session=_A;get_active_session=_A
def is_running_in_snowflake():
	if os.environ.get('SNOWFLAKE_ACCOUNT'):return _B
	if os.environ.get('SNOWFLAKE_HOST'):return _B
	if os.path.exists('/snowflake'):return _B
	if os.path.exists('/home/udf'):return _B
	if SNOWPARK_AVAILABLE and get_active_session is not _A:
		try:
			A=get_active_session()
			if A is not _A:return _B
		except Exception:pass
	return _J
def _is_local_session_created():return st.session_state.get('_local_session_created',_J)
def _set_local_session_created(value):st.session_state._local_session_created=value
def load_connections_toml(connection_name=_C):
	A=connection_name;import tomllib as D;B=Path.home()/'.snowflake'/'connections.toml'
	if not B.exists():raise FileNotFoundError(f"Snowflake connections file not found at {B}\nPlease create this file or set up Snowflake CLI.")
	with open(B,'rb')as E:C=D.load(E)
	if A not in C:F=list(C.keys());raise KeyError(f"Connection '{A}' not found in connections.toml. Available connections: {F}")
	return C[A]
def load_private_key(private_key_path):
	B=private_key_path;from cryptography.hazmat.backends import default_backend as D;from cryptography.hazmat.primitives import serialization as A;C=Path(B)
	if not C.exists():raise FileNotFoundError(f"Private key file not found: {B}")
	with open(C,'rb')as E:F=A.load_pem_private_key(E.read(),password=_A,backend=D())
	G=F.private_bytes(encoding=A.Encoding.DER,format=A.PrivateFormat.PKCS8,encryption_algorithm=A.NoEncryption());return G
def _create_local_session_impl(connection_name=_C):
	D='private_key_path';C='password'
	if not SNOWPARK_AVAILABLE:raise ImportError('snowflake-snowpark-python is not installed. Install it with: pip install snowflake-snowpark-python')
	A=load_connections_toml(connection_name);B={_D:A.get(_D),_E:A.get(_E),_F:A.get(_F),_G:A.get(_G),_H:A.get(_H),_I:A.get(_I)};E=A.get('authenticator','').upper()
	if E=='SNOWFLAKE_JWT'and D in A:F=load_private_key(A[D]);B['private_key']=F
	elif C in A:B[C]=A[C]
	else:raise ValueError("No valid authentication method found in connection config. Provide either 'private_key_path' with 'authenticator=SNOWFLAKE_JWT' or 'password'.")
	B={B:A for(B,A)in B.items()if A is not _A};G=Session.builder.configs(B).create();_set_local_session_created(_B);return G
@st.cache_resource
def create_local_session(connection_name=_C):return _create_local_session_impl(connection_name)
def get_snowflake_session(connection_name=_C):
	if is_running_in_snowflake():
		A=get_active_session()
		if A is _A:raise RuntimeError('Could not get active Snowflake session')
		return A
	else:return create_local_session(connection_name)
def get_session_info(session):
	J='ACCOUNT';H=session;E='unknown';C='server';I=_is_local_session_created()or not is_running_in_snowflake();A={_D:E,_E:E,_F:'XSMALL',_G:_A,_H:_A,_I:_A,C:E,'is_local':I}
	try:
		try:
			K=H.sql("\n                SELECT CURRENT_ORGANIZATION_NAME() || '-' || CURRENT_ACCOUNT_NAME() AS full_account\n            ").collect()[0];G=K['FULL_ACCOUNT']
			if G and G!='-':A[C]=f"{G}.snowflakecomputing.com"
		except Exception as D:logger.debug(f"Could not get org/account name, using fallback: {D}")
		B=H.sql('\n            SELECT\n                CURRENT_ACCOUNT() as account,\n                CURRENT_USER() as user,\n                CURRENT_WAREHOUSE() as warehouse,\n                CURRENT_DATABASE() as database,\n                CURRENT_SCHEMA() as schema,\n                CURRENT_ROLE() as role\n        ').collect()[0];A[_D]=B[J];A[_E]=B['USER'];A[_F]=B['WAREHOUSE'];A[_G]=B['DATABASE'];A[_H]=B['SCHEMA'];A[_I]=B['ROLE']
		if A[C]==E:
			if I:
				try:
					L=load_connections_toml(_C);F=L.get(_D,'')
					if F:
						if'.snowflakecomputing.com'in F:A[C]=F
						else:A[C]=f"{F}.snowflakecomputing.com"
				except Exception as D:logger.debug(f"Could not read server from connections.toml: {D}")
			if A[C]==E:A[C]=f"{B[J]}.snowflakecomputing.com"
		return A
	except Exception as D:A['error']=str(D);return A
IN_SNOWFLAKE=is_running_in_snowflake()