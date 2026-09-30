#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""像素列 min/max 聚合：把全量序列降维成"每个像素列一个 min/max 对"。

**禁止抽样**（等间隔取点、取均值、随机取点）——尖峰就是要发现的问题，抽样会把它抹掉。
本策略保证列内极值必然出现，因此换策略时必须保持"不丢极值"这一性质。

输出结构即 M 消息 `query_range` 的响应 payload（见 docs/messages.md M6）：
聚合与否结构一致，前端无需为数据量分支写代码。
"""
from __future__ import annotations

from typing import Any

# 分类轴的视口与列按**索引**解释：分类在界面上等宽分布，没有"值"可比
_INDEX_AXIS_KINDS = ("categorical",)


def aggregate_range(
    dataset: dict,
    *,
    x0: float,
    x1: float,
    resolution: int,
    names: list[str] | None = None,
) -> dict:
    """按视口与目标分辨率降维契约数据。

    - `x0` / `x1`：视口范围（闭区间）。`x1 <= x0` 视为空视口，返回空数组
    - `resolution`：目标分辨率，由前端给出画布像素宽度
    - `names`：只要这些序列；省略或空 = 全部。未知序列名被忽略
    """
    if resolution < 1:
        raise ValueError(f"resolution 必须是 >= 1 的整数，收到 {resolution!r}")

    aggregated = False
    out: list[dict] = []
    for series in _select(dataset, names):
        xs, ys = _axis_and_values(series)
        cols = _aggregate_one(xs, ys, x0, x1, resolution)
        aggregated = aggregated or cols["aggregated"]
        out.append({"name": series["name"], **cols})
    return {"aggregated": aggregated, "series": out}


def _select(dataset: dict, names: list[str] | None) -> list[dict]:
    series_list = dataset.get("series") if isinstance(dataset, dict) else None
    if not isinstance(series_list, list):
        raise ValueError("契约数据缺少 series 数组，请先过契约校验器")
    if not names:
        return series_list
    wanted = set(names)
    return [s for s in series_list if s.get("name") in wanted]


def _axis_and_values(series: dict) -> tuple[list, list]:
    x_axis = series.get("x") or {}
    xs = x_axis.get("data") or []
    ys = (series.get("y") or {}).get("data") or []
    if x_axis.get("kind") in _INDEX_AXIS_KINDS:
        xs = list(range(len(xs)))
    # 长度不等是契约违规（契约校验器会拦）。这里不静默截断：截断会画出一条错的曲线
    if len(xs) != len(ys):
        raise ValueError(
            f"序列 {series.get('name')!r} 的 x 与 y 长度不一致（{len(xs)} != {len(ys)}）"
        )
    return xs, ys


def _aggregate_one(xs: list, ys: list, x0: float, x1: float, resolution: int) -> dict:
    if x1 <= x0:
        return {"x": [], "ymin": [], "ymax": [], "aggregated": False}

    # 逐点判定而不是二分：契约的 monotonic 只是性能提示，数据未必单调，
    # 而 min/max 本来就要扫一遍视口内的点，裁剪与聚合合并成一次遍历
    inside = [i for i, x in enumerate(xs) if x is not None and x0 <= x <= x1]

    if len(inside) <= resolution:
        points = [xs[i] for i in inside]
        values = [ys[i] for i in inside]
        return {
            "x": points,
            "ymin": list(values),
            "ymax": list(values),
            "aggregated": False,
        }

    width = (x1 - x0) / resolution
    ymin: list[Any] = [None] * resolution
    ymax: list[Any] = [None] * resolution
    for i in inside:
        y = ys[i]
        if y is None:
            continue  # 缺失值不参与 min/max，否则会造出假的极值
        # 列是半开区间 [x0 + c*width, x0 + (c+1)*width)；右端点 x1 归最后一列
        col = int((xs[i] - x0) / width)
        col = min(col, resolution - 1)
        if ymin[col] is None or y < ymin[col]:
            ymin[col] = y
        if ymax[col] is None or y > ymax[col]:
            ymax[col] = y

    # 每条线段落在所属像素列的中心，避免整体偏左半列
    centers = [x0 + (c + 0.5) * width for c in range(resolution)]
    return {"x": centers, "ymin": ymin, "ymax": ymax, "aggregated": True}
