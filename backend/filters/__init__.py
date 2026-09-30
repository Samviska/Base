# -*- coding: utf-8 -*-
"""滤波：全量数据 → 全量数据，且**必须在聚合之前**。

顺序颠倒结果直接是错的（不是慢）：聚合已经丢了点，再滤波就是在残缺数据上算。
硬规则与坑见 docs/modules/filter.md 与同目录 AGENTS.md。
"""
from __future__ import annotations

from . import moving_average
from .chain import FilterPlugin, apply_chain, chain_key, get_plugin, list_plugins, register

# 内置插件在此显式登记；"目录即插件"的扫描机制留待插件机制批次
register(moving_average.PLUGIN)

__all__ = [
    "FilterPlugin",
    "apply_chain",
    "chain_key",
    "get_plugin",
    "list_plugins",
    "register",
]
