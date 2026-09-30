# -*- coding: utf-8 -*-
"""聚合：全量数据 + 视口 + 目标分辨率 → 绘制数据。

策略是像素列 min/max（见 pixel_columns.py）。**禁止抽样**：替换策略时必须保持不丢极值。
硬规则与坑见 docs/modules/aggregate.md 与同目录 AGENTS.md。
"""
from __future__ import annotations

from .pixel_columns import aggregate_range

__all__ = ["aggregate_range"]
