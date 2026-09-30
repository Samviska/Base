#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""会话状态与三层缓存。

一次连接一个会话。缓存按 [ARCHITECTURE.md](../../docs/ARCHITECTURE.md) §2.3 分三层，
失效**单向**：换数据源让滤波与聚合都失效；改滤波链只让聚合失效；反向都不成立。

会话只持有**引用与参数**，数据本身留在原文件——会话保存时不能把数据写进去。
"""
from __future__ import annotations

from collections import OrderedDict

from backend.aggregate import aggregate_range
from backend.filters import apply_chain, chain_key

from .errors import INVALID_REQUEST, CoreError

# 拖拽缩放会不断产生新的（范围, 分辨率）组合，聚合缓存必须有上限
_AGG_CACHE_SIZE = 32

# 分类轴没有可比的值，横轴按索引理解（与聚合模块同一约定）
_INDEX_AXIS_KINDS = ("categorical",)


class Session:
    def __init__(self) -> None:
        self.dataset: dict | None = None
        self.source: dict | None = None
        self.chain: list[dict] = []
        self._filtered: dict | None = None
        self._filtered_key: str | None = None
        self._aggregated: OrderedDict[tuple, dict] = OrderedDict()

    # ---- 提取层 ----

    def open(self, dataset: dict, source: dict) -> None:
        """打开数据源：滤波与聚合缓存立即失效。

        滤波链的**配置**保留：换一个文件通常还想用同一套滤波，重设一遍纯属折腾。
        """
        self.dataset = dataset
        self.source = source
        self._invalidate()

    def close(self) -> None:
        """关闭数据源：数据与全部缓存都清掉。"""
        self.dataset = None
        self.source = None
        self._invalidate()

    def require_dataset(self) -> dict:
        if self.dataset is None:
            raise CoreError(INVALID_REQUEST, "尚未打开数据源：先发 open_file")
        return self.dataset

    # ---- 滤波层 ----

    def set_chain(self, chain: list[dict]) -> None:
        """改滤波链（顺序、开关、参数任一项）：滤波与聚合缓存都失效。

        少失效一层，界面就会出现"拖了滑块图没变"。
        """
        self.chain = [dict(step) for step in chain]
        self._invalidate()

    def filtered(self) -> dict:
        """滤波后的全量数据。链路全禁用时返回提取结果本身（同一对象）。"""
        dataset = self.require_dataset()
        key = chain_key(self.chain)
        if self._filtered is None or self._filtered_key != key:
            self._filtered = apply_chain(dataset, self.chain)
            self._filtered_key = key
        return self._filtered

    # ---- 聚合层 ----

    def query(self, *, series: list[str] | None, x0: float, x1: float, resolution: int) -> dict:
        """按（序列集合, 范围, 分辨率）缓存聚合结果。

        视口变化产生新键，旧键留在缓存里直到被挤出去——这正是微缩放的加速来源。
        """
        key = (tuple(series) if series else None, x0, x1, resolution)
        cached = self._aggregated.get(key)
        if cached is not None:
            self._aggregated.move_to_end(key)
            return cached

        result = aggregate_range(self.filtered(), x0=x0, x1=x1, resolution=resolution, names=series)
        self._aggregated[key] = result
        self._aggregated.move_to_end(key)
        while len(self._aggregated) > _AGG_CACHE_SIZE:
            self._aggregated.popitem(last=False)
        return result

    # ---- 摘要：M3 open_file 的响应，只给形状不给数据 ----

    def summary(self) -> dict:
        dataset = self.require_dataset()
        return {
            "meta": dataset.get("meta") or {},
            "series": [_series_summary(s) for s in dataset.get("series") or []],
        }

    def _invalidate(self) -> None:
        self._filtered = None
        self._filtered_key = None
        self._aggregated.clear()


def _series_summary(series: dict) -> dict:
    x_axis = series.get("x") or {}
    data = x_axis.get("data") or []
    return {
        "name": series.get("name"),
        "unit": series.get("unit"),
        # 轴描述里去掉 data：前端拿到的是形状，不是数据
        "axis": {key: value for key, value in x_axis.items() if key != "data"},
        "point_count": len(data),
        "x_range": _axis_range(x_axis, data),
    }


def _axis_range(x_axis: dict, data: list) -> list | None:
    if not data:
        return None
    if x_axis.get("kind") in _INDEX_AXIS_KINDS:
        return [0, len(data) - 1]
    values = [v for v in data if isinstance(v, (int, float)) and not isinstance(v, bool)]
    return [min(values), max(values)] if values else None
