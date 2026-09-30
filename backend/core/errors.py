#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""领域错误与错误码。

错误码是**契约的一部分**（[messages.md](../../docs/messages.md) §2 的清单），
所以集中在这里定义：业务代码里不写裸字符串，改码时只需改这一处。
"""
from __future__ import annotations

INVALID_REQUEST = "INVALID_REQUEST"
UNKNOWN_TYPE = "UNKNOWN_TYPE"
FILE_NOT_FOUND = "FILE_NOT_FOUND"
PLUGIN_NOT_FOUND = "PLUGIN_NOT_FOUND"
PLUGIN_FAILED = "PLUGIN_FAILED"
CONTRACT_VIOLATION = "CONTRACT_VIOLATION"
INTERNAL = "INTERNAL"


class CoreError(Exception):
    """能被翻译成失败响应的错误：`{code, message, detail}`。

    `detail` 能定位问题时必须给（契约违规要给字段路径），
    只回一句"出错了"等于没回。
    """

    def __init__(self, code: str, message: str, detail: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail or {}

    def as_error(self) -> dict:
        return {"code": self.code, "message": self.message, "detail": self.detail}
