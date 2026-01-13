#!/usr/bin/env python
# _*_coding:utf-8_*_

"""
@Time     : 2023/6/6 16:50
@Author   : ji hao ran
@File     : tree.py
@Project  : StreamlitAntdComponents
@Software : PyCharm

Modified to return expanded keys along with selected items.
"""

from ..utils import *
from typing import NamedTuple, Optional


class TreeResult(NamedTuple):
    """Result from tree component containing selected and expanded items."""
    selected: List[Union[str, int]]
    expanded: List[Union[str, int]]


def tree(
        items: List[Union[str, dict, TreeItem]] = None,
        index: Union[int, List[int]] = None,
        format_func: Union[Formatter, Callable] = None,
        label: str = None,
        description: str = None,
        icon: Union[str, BsIcon, AntIcon] = None,
        align: Align = 'start',
        size: Union[MantineSize, int] = 'sm',
        color: Union[MantineColor, str] = None,
        width: int = None,
        height: int = None,
        open_index: List[int] = None,
        open_all: bool = False,
        checkbox: bool = False,
        checkbox_strict: bool = False,
        show_line: bool = True,
        return_index: bool = False,
        on_change: Callable = None,
        args: Tuple[Any, ...] = None,
        kwargs: Dict[str, Any] = None,
        key=None
) -> TreeResult:
    """antd design tree  https://ant.design/components/tree

    :param items: tree data
    :param index: default selected tree item index
    :param format_func: label formatter function,receive str and return str
    :param label: tree label,support str and markdown str
    :param description: tree description,support str and markdown str
    :param icon: tree item icon
    :param align: tree align
    :param size: tree size,support mantine size and int in px
    :param color: tree color,default streamlit primary color,support mantine color, hex and rgb color
    :param width: tree width
    :param height: tree height
    :param open_index: default opened indexes.if none,tree will open default index's parent nodes.
    :param open_all: open all items.priority[open_all>open_index]
    :param checkbox: show checkbox to allow multiple select
    :param checkbox_strict: parent item and children item are not associated
    :param show_line: show line
    :param return_index: if True,return tree item index,default return label
    :param on_change: item change callback
    :param args: callback args
    :param kwargs: callback kwargs
    :param key: component unique identifier
    :return: TreeResult with selected items and expanded items
    """
    if isinstance(index, list) and len(index) > 1 and not checkbox:
        raise ValueError(f'length of index ({len(index)}) should =1  when checkbox=False')
    # register callback
    register(key, on_change, args, kwargs)
    # parse items
    items, kv = ParseItems(items, format_func).multi()
    # parse index
    if index is None and checkbox:
        index = []
    if isinstance(index, int) and checkbox:
        index = [index]
    if isinstance(index, list) and not checkbox:
        index = index[0]
    # component params
    kw = update_kw(locals(), items=items, icon=parse_icon(icon))
    # component default
    default = get_default(index, return_index, kv)
    # pass component id and params to frontend
    result = component(id=get_func_name(), kw=kw, default=default, key=key)

    # Handle the new return format {selected: ..., expanded: [...]}
    if isinstance(result, dict) and 'selected' in result and 'expanded' in result:
        selected = result['selected']
        expanded = result['expanded']
        # Ensure selected is a list for checkbox mode
        if checkbox and not isinstance(selected, list):
            selected = [selected] if selected is not None else []
        elif not checkbox and isinstance(selected, list):
            selected = selected[0] if selected else None
        return TreeResult(selected=selected, expanded=expanded or [])

    # Fallback for backward compatibility (if component returns old format)
    if checkbox:
        return TreeResult(selected=result if isinstance(result, list) else [], expanded=[])
    else:
        return TreeResult(selected=result, expanded=[])
