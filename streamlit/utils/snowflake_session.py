"""
Utility functions for Snowflake session management.

Supports both:
- Local development: Uses ~/.snowflake/connections.toml with key-pair auth
- Streamlit in Snowflake: Uses get_active_session()

Performance: Uses @st.cache_resource for session caching.
"""

import os
import sys
from pathlib import Path
from typing import Optional
import streamlit as st

from .logging_config import get_logger
from .host_builder import resolve_server_host

logger = get_logger(__name__)

# Try to import Snowpark
try:
    from snowflake.snowpark import Session
    from snowflake.snowpark.context import get_active_session
    SNOWPARK_AVAILABLE = True
except ImportError:
    SNOWPARK_AVAILABLE = False
    Session = None
    get_active_session = None


def is_running_in_snowflake() -> bool:
    """
    Detect if code is running in Streamlit in Snowflake environment.

    Returns:
        True if running in Snowflake, False if running locally
    """
    # Check for Snowflake-specific environment indicators
    if os.environ.get("SNOWFLAKE_ACCOUNT"):
        return True

    if os.environ.get("SNOWFLAKE_HOST"):
        return True

    # Check if we're in a Snowflake container environment
    if os.path.exists("/snowflake"):
        return True

    # Check for SiS-specific paths
    if os.path.exists("/home/udf"):
        return True

    # Try to get active session - most reliable detection for SiS
    if SNOWPARK_AVAILABLE and get_active_session is not None:
        try:
            session = get_active_session()
            if session is not None:
                return True
        except Exception:
            pass

    return False


def _is_local_session_created() -> bool:
    """Check if a local session was created (uses session state instead of global)."""
    return st.session_state.get("_local_session_created", False)


def _set_local_session_created(value: bool) -> None:
    """Set whether a local session was created (uses session state instead of global)."""
    st.session_state._local_session_created = value


def load_connections_toml(connection_name: str = "default") -> dict:
    """
    Load connection parameters from ~/.snowflake/connections.toml

    Args:
        connection_name: Name of the connection section in TOML file

    Returns:
        Dictionary with connection parameters
    """
    import tomllib

    # Standard location for connections.toml
    connections_path = Path.home() / ".snowflake" / "connections.toml"

    if not connections_path.exists():
        raise FileNotFoundError(
            f"Snowflake connections file not found at {connections_path}\n"
            "Please create this file or set up Snowflake CLI."
        )

    with open(connections_path, "rb") as f:
        config = tomllib.load(f)

    if connection_name not in config:
        available = list(config.keys())
        raise KeyError(
            f"Connection '{connection_name}' not found in connections.toml. "
            f"Available connections: {available}"
        )

    return config[connection_name]


def list_available_connections() -> list[str]:
    """
    List connection names available in ~/.snowflake/connections.toml.

    Returns an empty list if the file doesn't exist or can't be parsed -
    callers should treat that the same as "no connections available".
    """
    import tomllib

    connections_path = Path.home() / ".snowflake" / "connections.toml"
    if not connections_path.exists():
        return []

    try:
        with open(connections_path, "rb") as f:
            config = tomllib.load(f)
        return list(config.keys())
    except Exception as e:
        logger.debug(f"Could not list connections.toml connections: {e}")
        return []


def load_private_key(private_key_path: str) -> bytes:
    """
    Load private key from file for key-pair authentication.

    Args:
        private_key_path: Path to the private key file (.p8)

    Returns:
        Private key bytes
    """
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import serialization

    key_path = Path(private_key_path)
    if not key_path.exists():
        raise FileNotFoundError(f"Private key file not found: {private_key_path}")

    with open(key_path, "rb") as key_file:
        private_key = serialization.load_pem_private_key(
            key_file.read(),
            password=None,  # Add password parameter if key is encrypted
            backend=default_backend()
        )

    # Convert to bytes format expected by Snowflake
    private_key_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

    return private_key_bytes


def _build_connection_params(config: dict) -> dict:
    """
    Build Snowpark connection parameters (incl. auth) from a connections.toml
    section or an equivalent dict from the manual connection form.

    Supports password, key-pair (private_key_path), and externalbrowser
    (SSO) authentication.
    """
    connection_params = {
        "account": config.get("account"),
        "user": config.get("user"),
        "warehouse": config.get("warehouse"),
        "database": config.get("database"),
        "schema": config.get("schema"),
        "role": config.get("role"),
    }

    authenticator = (config.get("authenticator") or "").upper()

    if authenticator == "EXTERNALBROWSER":
        # SSO - no password/private key needed, browser handles auth.
        connection_params["authenticator"] = "externalbrowser"
    elif authenticator == "SNOWFLAKE_JWT" and "private_key_path" in config:
        # Key-pair authentication
        connection_params["private_key"] = load_private_key(config["private_key_path"])
    elif "password" in config:
        # Password authentication
        connection_params["password"] = config["password"]
    else:
        raise ValueError(
            "No valid authentication method found in connection config. "
            "Provide 'authenticator=externalbrowser', 'private_key_path' with "
            "'authenticator=SNOWFLAKE_JWT', or 'password'."
        )

    # Remove None values
    return {k: v for k, v in connection_params.items() if v is not None}


def create_session_from_params(connection_params: dict) -> "Session":
    """
    Create a Snowpark session directly from a connection parameters dict
    (already resolved - no further auth-method lookup performed here).

    Used both by the connections.toml path and the interactive connection
    form fallback (issue #3).
    """
    if not SNOWPARK_AVAILABLE:
        raise ImportError(
            "snowflake-snowpark-python is not installed. "
            "Install it with: pip install snowflake-snowpark-python"
        )

    session = Session.builder.configs(connection_params).create()
    _set_local_session_created(True)
    return session


def _create_local_session_impl(connection_name: str = "default") -> "Session":
    """
    Internal implementation to create a Snowpark session for local development.

    Args:
        connection_name: Name of the connection in connections.toml

    Returns:
        Snowpark Session object
    """
    if not SNOWPARK_AVAILABLE:
        raise ImportError(
            "snowflake-snowpark-python is not installed. "
            "Install it with: pip install snowflake-snowpark-python"
        )

    config = load_connections_toml(connection_name)
    connection_params = _build_connection_params(config)
    return create_session_from_params(connection_params)


def _session_is_alive(session: "Session") -> bool:
    """Check whether a cached session can still execute queries."""
    try:
        session.sql("SELECT 1").collect()
        return True
    except Exception:
        return False


def get_or_create_local_session(connection_name: str = "default") -> "Session":
    """
    Get a cached local Snowpark session, or create one if missing/dead.

    Replaces the previous @st.cache_resource-based caching, which never
    invalidated a cached-but-dead session (issue #3) - a session that went
    stale (e.g. after a long idle period) would keep being reused and every
    query against it would fail. Caching here is keyed on session state so
    a "Reconnect" action can force recreation.

    Args:
        connection_name: Name of the connection in connections.toml

    Returns:
        Snowpark Session object (cached in session state)
    """
    cache_key = f"_snowpark_session::{connection_name}"
    cached = st.session_state.get(cache_key)

    if cached is not None and _session_is_alive(cached):
        return cached

    session = _create_local_session_impl(connection_name)
    st.session_state[cache_key] = session
    return session


def reconnect_local_session(connection_name: str = "default") -> "Session":
    """Force-drop any cached session and create a fresh one (explicit "Reconnect")."""
    cache_key = f"_snowpark_session::{connection_name}"
    st.session_state.pop(cache_key, None)
    return get_or_create_local_session(connection_name)


def render_connection_form() -> Optional["Session"]:
    """
    Render a manual Snowflake connection form and return a live session on
    successful submission, or None otherwise.

    Fallback UI for issue #3: when connections.toml is missing or doesn't
    have the requested connection, the app used to dead-end with a static
    text suggestion. This renders an actual form (account/user + password,
    key-pair file, or externalbrowser SSO) so the app is usable without any
    local file setup.
    """
    st.subheader("Connect to Snowflake")
    st.caption(
        "No usable `~/.snowflake/connections.toml` connection was found. "
        "Enter your connection details below, or create/fix that file and "
        "reload the page."
    )

    with st.form("manual_connection_form"):
        account = st.text_input("Account identifier", help="e.g. myorg-myaccount or xy12345.us-east-1")
        user = st.text_input("Username")
        auth_method = st.radio(
            "Authentication method",
            ["Password", "Key-pair file", "Browser (SSO)"],
            horizontal=True,
        )

        password = None
        private_key_path = None
        if auth_method == "Password":
            password = st.text_input("Password", type="password")
        elif auth_method == "Key-pair file":
            private_key_path = st.text_input("Private key file path (.p8)")

        col1, col2, col3 = st.columns(3)
        warehouse = col1.text_input("Warehouse (optional)")
        database = col2.text_input("Database (optional)")
        role = col3.text_input("Role (optional)")

        submitted = st.form_submit_button("Connect", type="primary")

    if not submitted:
        return None

    if not account or not user:
        st.error("Account identifier and username are required.")
        return None

    connection_params = {
        "account": account,
        "user": user,
        "warehouse": warehouse or None,
        "database": database or None,
        "role": role or None,
    }

    if auth_method == "Browser (SSO)":
        connection_params["authenticator"] = "externalbrowser"
    elif auth_method == "Key-pair file":
        if not private_key_path:
            st.error("Private key file path is required for key-pair authentication.")
            return None
        try:
            connection_params["private_key"] = load_private_key(private_key_path)
        except Exception as e:
            st.error(f"Could not load private key: {e}")
            return None
    else:
        if not password:
            st.error("Password is required.")
            return None
        connection_params["password"] = password

    connection_params = {k: v for k, v in connection_params.items() if v is not None}

    try:
        session = create_session_from_params(connection_params)
    except Exception as e:
        st.error(f"Could not connect: {e}")
        return None

    st.session_state["_snowpark_session::manual"] = session
    st.success("Connected successfully.")
    return session


def get_snowflake_session(connection_name: str = "default") -> "Session":
    """
    Get a Snowflake Snowpark session, automatically detecting environment.

    In Streamlit in Snowflake: Uses get_active_session()
    In local environment: Creates (or reuses a cached, live) session from
    connections.toml

    Args:
        connection_name: Name of connection in connections.toml (for local dev)

    Returns:
        Snowpark Session object
    """
    if is_running_in_snowflake():
        # Running in Snowflake - use active session
        session = get_active_session()
        if session is None:
            raise RuntimeError("Could not get active Snowflake session")
        return session
    else:
        # Running locally - create/reuse session from config
        return get_or_create_local_session(connection_name)


def get_session_info(session: "Session") -> dict:
    """
    Get information about the current session.

    Args:
        session: Snowpark Session object

    Returns:
        Dictionary with session info including properly formatted server URL
    """
    # Determine if running locally based on how session was created
    is_local = _is_local_session_created() or not is_running_in_snowflake()

    # Default values in case queries fail
    info = {
        "account": "unknown",
        "user": "unknown",
        "warehouse": "XSMALL",
        "warehouse_missing": False,
        "database": None,
        "schema": None,
        "role": None,
        "server": "unknown",
        "is_local": is_local
    }

    try:
        # First try to get org/account name for proper server URL
        # Uses concatenation in SQL to avoid column name issues
        org_account_name = None
        try:
            org_result = session.sql("""
                SELECT CURRENT_ORGANIZATION_NAME() || '-' || CURRENT_ACCOUNT_NAME() AS full_account
            """).collect()[0]
            org_account_name = org_result["FULL_ACCOUNT"]
        except Exception as e:
            # Organization functions may not be available - will use fallback
            logger.debug(f"Could not get org/account name, using fallback: {e}")

        # Get basic context info, including CURRENT_REGION() so legacy
        # locator accounts keep their region segment (issue #2) instead of
        # being reduced to "{locator}.snowflakecomputing.com".
        result = session.sql("""
            SELECT
                CURRENT_ACCOUNT() as account,
                CURRENT_USER() as user,
                CURRENT_WAREHOUSE() as warehouse,
                CURRENT_DATABASE() as database,
                CURRENT_SCHEMA() as schema,
                CURRENT_ROLE() as role,
                CURRENT_REGION() as region
        """).collect()[0]

        info["account"] = result["ACCOUNT"]
        info["user"] = result["USER"]
        # NOTE: CURRENT_WAREHOUSE() can return NULL when no warehouse is
        # active for the session. Don't silently mask that with the
        # "XSMALL" default above - callers must check warehouse_missing
        # and prompt the user to pick a warehouse before generating M code.
        info["warehouse"] = result["WAREHOUSE"]
        info["warehouse_missing"] = result["WAREHOUSE"] is None
        info["database"] = result["DATABASE"]
        info["schema"] = result["SCHEMA"]
        info["role"] = result["ROLE"]

        # Read connections.toml account (may already be a full host,
        # including PrivateLink) if running locally.
        connections_toml_account = None
        if is_local:
            try:
                config = load_connections_toml("default")
                connections_toml_account = config.get("account", "")
            except Exception as e:
                logger.debug(f"Could not read server from connections.toml: {e}")

        info["server"] = resolve_server_host(
            org_account_name=org_account_name,
            connections_toml_account=connections_toml_account,
            current_account=result["ACCOUNT"],
            current_region=result["REGION"],
        )

        return info

    except Exception as e:
        info["error"] = str(e)
        return info


# For convenience, expose environment detection
IN_SNOWFLAKE = is_running_in_snowflake()
