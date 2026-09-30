# -*- coding: utf-8 -*-
"""契约：数据长什么样，以及校验。

对外只暴露本文件导出的内容。契约位于依赖图的根，**不依赖任何业务模块**。
字段定义见 docs/contract.md，规则与坑见 docs/modules/contract.md。
"""
from __future__ import annotations

from .validator import (
    CROSS_FIELD,
    JSON_ERROR,
    ValidationResult,
    Violation,
    validate,
    validate_file,
)

__all__ = [
    "CROSS_FIELD",
    "JSON_ERROR",
    "ValidationResult",
    "Violation",
    "validate",
    "validate_file",
]
