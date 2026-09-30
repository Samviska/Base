#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""契约校验器：判定数据是否合规，并指出违规字段路径与原因。

两步走：先按 contract/schema/dataset.schema.json 做结构校验，
schema 通过后才跑跨字段规则——一条结构错误不该派生出一串无关报错。

规则只来自 contract/（语言中立的权威定义），本模块**不新增约束**：
新增约束属于契约变更，要走 docs/guides/contract-change.md 的流程。
"""
from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

# 契约定义与 backend/ 平级，位于仓库根
_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2] / "contract" / "schema" / "dataset.schema.json"
)

# Violation.keyword 的两个非 schema 取值：跨字段规则、JSON 解析失败
CROSS_FIELD = "contract"
JSON_ERROR = "json"

# jsonschema 的原生消息是英文、且夹带内部关键字名，而原因最终会显示给使用者。
# 故按关键字重述为中文，并保留原文——原文带具体取值，排查时更好检索。
_SCHEMA_REASONS = {
    "required": "缺少必填字段",
    "type": "类型不符",
    "minLength": "至少需要 1 个字符",
    "minItems": "数组不能为空",
    "enum": "取值不在允许范围内",
    "const": "取值必须是固定值",
    "pattern": "格式不符合要求",
    "minimum": "小于允许的最小值",
}


@dataclass(frozen=True)
class Violation:
    path: str  # "series[0].unit"；空串表示问题出在整份文档上
    reason: str
    keyword: str  # schema 关键字，或 CROSS_FIELD / JSON_ERROR

    def describe(self) -> str:
        return f"{self.path}: {self.reason}" if self.path else self.reason


@dataclass(frozen=True)
class ValidationResult:
    violations: tuple[Violation, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.violations

    def error_detail(self) -> dict[str, str]:
        """M 消息 CONTRACT_VIOLATION 所需的 detail：{"path":..., "reason":...}。"""
        if not self.violations:
            return {}
        first = self.violations[0]
        return {"path": first.path, "reason": first.reason}

    def describe(self) -> list[str]:
        return [v.describe() for v in self.violations]


def validate(data: object) -> ValidationResult:
    """校验任意数据。不修改入参。"""
    violations = [_from_schema_error(e) for e in _validator().iter_errors(data)]
    if violations:
        return ValidationResult(tuple(violations))
    return ValidationResult(tuple(_check_cross_fields(data)))


def validate_file(path: str | Path) -> ValidationResult:
    """读 UTF-8 JSON 文件再校验。

    JSON 解析失败作为一条违规返回（不是异常）：插件自检要能直接把它呈现出来。
    """
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        return ValidationResult((Violation("", f"文件无法读取：{exc}", JSON_ERROR),))
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return ValidationResult(
            (
                Violation(
                    "",
                    f"JSON 解析失败：第 {exc.lineno} 行第 {exc.colno} 列 {exc.msg}",
                    JSON_ERROR,
                ),
            )
        )
    return validate(data)


@lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    # schema 读不到或不是合法 JSON 说明仓库损坏：属校验器故障，不能伪装成数据违规
    try:
        return Draft202012Validator(json.loads(_SCHEMA_PATH.read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"契约 schema 无法加载：{_SCHEMA_PATH} -> {exc}") from exc


def _from_schema_error(error: ValidationError) -> Violation:
    keyword = str(error.validator or "")
    reason = error.message
    if keyword in _SCHEMA_REASONS:
        reason = f"{_SCHEMA_REASONS[keyword]}（{error.message}）"
    return Violation(path=_format_path(error.absolute_path), reason=reason, keyword=keyword)


def _format_path(parts: Iterable[Any]) -> str:
    out = ""
    for part in parts:
        if isinstance(part, int):
            out += f"[{part}]"
        else:
            out += f".{part}" if out else str(part)
    return out


def _check_cross_fields(data: object) -> list[Violation]:
    """schema 表达不了的跨字段规则。目前只有一条：x 与 y 必须等长。"""
    if not isinstance(data, dict):
        return []
    series_list = data.get("series")
    if not isinstance(series_list, list):
        return []

    violations: list[Violation] = []
    for index, series in enumerate(series_list):
        if not isinstance(series, dict):
            continue
        x, y = series.get("x"), series.get("y")
        if not isinstance(x, dict) or not isinstance(y, dict):
            continue
        x_data, y_data = x.get("data"), y.get("data")
        if isinstance(x_data, list) and isinstance(y_data, list) and len(x_data) != len(y_data):
            violations.append(
                Violation(
                    path=f"series[{index}].y.data",
                    reason=f"长度 {len(y_data)} 与 x.data 的长度 {len(x_data)} 不一致（契约要求等长）",
                    keyword=CROSS_FIELD,
                )
            )
    return violations
