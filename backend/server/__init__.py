# -*- coding: utf-8 -*-
"""通信服务：WebSocket 服务端。

不做业务逻辑（那是核心的事），不依赖任何具体插件与界面。
硬规则与坑见 docs/modules/server.md。
"""
from __future__ import annotations

from .app import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    PROTOCOL_VERSION,
    backend_version,
    handler,
    serve_forever,
)

__all__ = [
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "PROTOCOL_VERSION",
    "backend_version",
    "handler",
    "serve_forever",
]
