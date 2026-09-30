# -*- coding: utf-8 -*-
"""数据源：任意格式的输入 → 契约数据。

插件只依赖契约；核心只认识本包暴露的接口，不认识任何具体插件。
硬规则与坑见 docs/modules/source.md 与同目录 AGENTS.md。
"""
from __future__ import annotations

from . import contract_json
from .registry import (
    PLUGIN_ROOT,
    SourcePlugin,
    get_plugin,
    list_plugins,
    load_directory,
    load_warnings,
    register,
)

# 内置插件在此显式登记；外部插件由 load_directory() 在启动时扫描
register(contract_json.PLUGIN)

__all__ = [
    "PLUGIN_ROOT",
    "SourcePlugin",
    "get_plugin",
    "list_plugins",
    "load_directory",
    "load_warnings",
    "register",
]
