#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""处理链：按顺序对**全量数据**施加滤波，前一级输出作为后一级输入。

链的顺序有意义，因此缓存键不排序链本身（只排序每个步骤内部的对象键）。
滤波是纯函数：任何一步都不得修改它拿到的数据，否则关掉滤波后数据无法恢复。
"""
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class FilterPlugin:
    """一个滤波插件对外的全部信息。

    `needs_full_data`：算法是否需要前后文（滑动平均一类有状态算法必须为真）。
    它不影响调用方式——滤波一律拿全量数据——只用于给使用者解释"为什么不能只喂视口"。
    """

    id: str
    display_name: str
    version: str
    apply: Callable[[dict, dict], dict]
    declare_params: Callable[[], list[dict]]
    needs_full_data: bool = True


_PLUGINS: dict[str, FilterPlugin] = {}


def register(plugin: FilterPlugin) -> None:
    if plugin.id in _PLUGINS:
        raise ValueError(f"滤波插件 id 重复：{plugin.id}")
    _PLUGINS[plugin.id] = plugin


def get_plugin(plugin_id: str) -> FilterPlugin:
    try:
        return _PLUGINS[plugin_id]
    except KeyError:
        known = ", ".join(sorted(_PLUGINS)) or "（未注册任何插件）"
        raise ValueError(f"未知的滤波插件 {plugin_id!r}；已注册：{known}") from None


def list_plugins() -> list[FilterPlugin]:
    return [_PLUGINS[key] for key in sorted(_PLUGINS)]


def apply_chain(data: dict, chain: list[dict] | None) -> dict:
    """按链顺序处理全量数据。

    所有步骤都未启用时**原样返回入参**：没有变更就不必复制，
    核心层据此可以按对象身份判断"结果未变"。
    """
    result = data
    for step in chain or []:
        if not step.get("enabled", True):
            continue
        plugin = get_plugin(str(step.get("plugin", "")))
        result = plugin.apply(result, _with_defaults(plugin, step.get("params")))
    return result


def chain_key(chain: list[dict] | None) -> str:
    """滤波缓存的键：链的顺序、每一步的开关与参数都在内。

    少算任何一项都会导致"拖了滑块图没变"——改参数必须让缓存失效。
    """
    return json.dumps(chain or [], sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _with_defaults(plugin: FilterPlugin, params: dict | None) -> dict:
    # 只补声明里有的默认值；声明外的参数原样传给插件（由插件自己忽略）
    given = dict(params or {})
    for decl in plugin.declare_params():
        given.setdefault(decl["name"], decl.get("default"))
    return given
