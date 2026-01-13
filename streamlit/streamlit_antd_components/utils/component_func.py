#!/usr/bin/env python
# _*_coding:utf-8_*_

"""
@Time     : 2023/6/7 11:50
@Author   : ji hao ran
@File     : component_func.py
@Project  : StreamlitAntdComponents
@Software : PyCharm
"""
import json
import os
import streamlit.components.v1 as components
import streamlit as st
from dataclasses import is_dataclass
from .. import _RELEASE

def _get_build_dir():
    """Get the frontend build directory, handling both local and SiS environments."""
    try:
        # Standard path resolution
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        build_dir = os.path.join(parent_dir, "frontend/build")
        if os.path.exists(build_dir):
            return build_dir
    except (TypeError, OSError):
        pass

    # Fallback for SiS - try common locations
    possible_paths = [
        "/tmp/streamlit_antd_components/frontend/build",
        "streamlit_antd_components/frontend/build",
        "./streamlit_antd_components/frontend/build",
    ]

    # Also try relative to current working directory
    cwd = os.getcwd()
    possible_paths.append(os.path.join(cwd, "streamlit_antd_components/frontend/build"))

    for path in possible_paths:
        if os.path.exists(path):
            return path

    # Last resort - return the standard computed path even if it doesn't exist
    try:
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(parent_dir, "frontend/build")
    except (TypeError, OSError):
        return "streamlit_antd_components/frontend/build"

if not _RELEASE:
    component_func = components.declare_component(
        "sac",
        url="http://localhost:3000",
    )
else:
    build_dir = _get_build_dir()
    component_func = components.declare_component("sac", path=build_dir)


def convert_session_value(id, value, kv: dict, return_index: bool):
    if value is not None:
        # Handle new TreeResult dict format {'selected': ..., 'expanded': ...}
        if isinstance(value, dict) and 'selected' in value and 'expanded' in value:
            # For tree component with expanded keys - pass through as-is
            # Also filter out None values from selected list
            if isinstance(value.get('selected'), list):
                value['selected'] = [v for v in value['selected'] if v is not None]
            if isinstance(value.get('expanded'), list):
                value['expanded'] = [v for v in value['expanded'] if v is not None]
            return value

        list_value = value if isinstance(value, list) else [value]

        # Filter out None values to prevent ValueError
        list_value = [v for v in list_value if v is not None]

        if len(list_value) == 0:
            return
        if kv is not None:
            # index list
            r = [k for k, v in kv.items() if (k if return_index else v) in list_value]
            if len(r) == 0:
                # Instead of raising error, just return None (no valid selection)
                # This can happen after tree items change and old selections are invalid
                return None
            return r if isinstance(value, list) else r[0]
        else:
            return value


class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if is_dataclass(obj):
            return obj.__dict__
        return super().default(obj)


def component(id, kw, default=None, key=None):
    # repair component session init value
    if key is not None and key not in st.session_state:
        st.session_state[key] = default
    # pass component session state value to frontend
    if key is not None:
        # convert value
        st_value = convert_session_value(id, st.session_state[key], kw.get('kv'), kw.get('return_index'))
        kw.update({"stValue": st_value})
    else:
        kw.update({"stValue": None})
    return component_func(id=id, kw=json.loads(json.dumps(kw, cls=CustomEncoder)), default=default, key=key)
