# -*- coding: utf-8 -*-
"""后端核心：编排、会话状态、缓存失效、命令分发。

只依赖契约与各插件的**接口**，不认识任何具体插件。
硬规则与坑见 docs/modules/core.md 与同目录 AGENTS.md。
"""
from __future__ import annotations

from .dispatch import handle
from .errors import CoreError
from .session import Session

__all__ = ["CoreError", "Session", "handle"]
