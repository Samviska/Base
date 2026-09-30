#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""过渡数据源入口：把一个契约 JSON 文件读成合规的契约数据。

**这是过渡实现，不是数据源插件机制。** 第 4 批要让"打开文件 → 请求视口数据"跑通，
而插件机制（第 2 批）尚未落地：所以这里只做"读 UTF-8 JSON + 过契约校验器"，
不做任何格式推断，也不注册插件。插件机制就绪后本文件删除，
核心改调插件注册表——命令层的请求与响应形状不变。

日志格式五花八门，解析逻辑属于插件；本文件的存在时间应当尽可能短。
"""
from __future__ import annotations

import json
from pathlib import Path

from backend.contract import validate

from .errors import CONTRACT_VIOLATION, FILE_NOT_FOUND, CoreError


def load(path: str | Path) -> dict:
    """读契约数据。文件不存在抛 `FILE_NOT_FOUND`，数据不合规抛 `CONTRACT_VIOLATION`。"""
    file = Path(path)
    try:
        text = file.read_text(encoding="utf-8")
    except OSError as exc:
        raise CoreError(FILE_NOT_FOUND, f"文件无法读取：{file}（{exc.strerror or exc}）") from exc

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        reason = f"JSON 解析失败：第 {exc.lineno} 行第 {exc.colno} 列 {exc.msg}"
        raise CoreError(CONTRACT_VIOLATION, reason, {"path": "", "reason": reason}) from exc

    result = validate(data)
    if not result.ok:
        first = result.violations[0]
        raise CoreError(
            CONTRACT_VIOLATION,
            f"数据不符合契约：{first.describe()}",
            result.error_detail(),
        )
    return data
