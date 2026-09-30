#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""内置数据源：直接读契约 JSON 文件。

它不解析任何日志格式，只把"已经是契约数据"的文件读进来——
手工造的数据、调试用的小样本、以及别人直接给的契约文件都靠它。
真正的日志解析属于 `plugins/sources/` 下的插件。
"""
from __future__ import annotations

import json
from pathlib import Path

from .registry import SourcePlugin

ID = "contract-json"


def declare_params() -> list[dict]:
    return []


def extract(path: str, options: dict) -> dict:
    file = Path(path)
    if not file.is_file():
        # 由核心翻译成 FILE_NOT_FOUND
        raise FileNotFoundError(f"文件不存在：{path}")
    try:
        return json.loads(file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{file.name} 不是合法 JSON：第 {exc.lineno} 行第 {exc.colno} 列 {exc.msg}") from exc


PLUGIN = SourcePlugin(
    id=ID,
    display_name="契约 JSON 文件",
    version="1.0.0",
    extract=extract,
    declare_params=declare_params,
    origin="内置",
    notes="不解析日志格式，直接读取已符合契约的 JSON",
)
