"""
Session helper for Streamlit in Snowflake.

Provides get_active_session() wrapper with error handling for SiS deployment.
For local development, use utils.get_snowflake_session() which handles both modes.
"""
from snowflake.snowpark.context import get_active_session
from snowflake.snowpark import Session
import streamlit as st


@st.cache_resource
def get_session() -> Session:
    """
    Get the active Snowflake session for Streamlit in Snowflake.

    This function is specifically for SiS deployment where the session
    is automatically provided by the Snowflake environment.

    Returns:
        Session: The active Snowpark session

    Raises:
        RuntimeError: If no active session is found
    """
    try:
        session = get_active_session()
        if session is None:
            raise RuntimeError("No active Snowflake session found")
        return session
    except Exception as e:
        st.error(f"Failed to get Snowflake session: {e}")
        raise
