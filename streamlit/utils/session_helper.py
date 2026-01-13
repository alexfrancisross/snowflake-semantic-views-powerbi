from snowflake.snowpark.context import get_active_session
from snowflake.snowpark import Session
import streamlit as st
@st.cache_resource
def get_session():
	try:
		A=get_active_session()
		if A is None:raise RuntimeError('No active Snowflake session found')
		return A
	except Exception as B:st.error(f"Failed to get Snowflake session: {B}");raise