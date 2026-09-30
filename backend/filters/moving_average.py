#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""示例滤波插件：滑动平均。

窗口以当前点为中心；**边界处窗口收缩到可用范围**，而不是把窗口右移。
这正是"滤波必须拿全量数据"的原因：只喂视口内的点，视口边缘的平均值就会失真。

窗口内只要有缺失值，结果就是缺失值：宁可留空，也不拿周围的点凑一个假值出来。
"""
from __future__ import annotations

from .chain import FilterPlugin

ID = "moving-average"
_MIN_WINDOW = 1
_MAX_WINDOW = 1000

_PARAMS = [
    {
        "name": "window",
        "type": "int",
        "min": _MIN_WINDOW,
        "max": _MAX_WINDOW,
        "default": 5,
        "display_name": "窗口大小",
    },
]


def declare_params() -> list[dict]:
    # 返回副本：调用方（界面）改到它不该改到模块常量
    return [dict(decl) for decl in _PARAMS]


def apply(data: dict, params: dict) -> dict:
    window = int(params.get("window", 5))
    if not _MIN_WINDOW <= window <= _MAX_WINDOW:
        raise ValueError(f"window 必须在 {_MIN_WINDOW}–{_MAX_WINDOW} 之间，收到 {window}")
    return {
        **data,  # 契约里的未知字段（meta.notes、extensions 等）原样保留
        "series": [_apply_series(s, window) for s in data.get("series") or []],
    }


def _apply_series(series: dict, window: int) -> dict:
    y = series.get("y") or {}
    values = y.get("data") or []
    # x 不变，所以注解的 x 坐标依然对齐：滤波不需要动 annotations
    return {**series, "y": {**y, "data": _moving_average(values, window)}}


def _moving_average(values: list, window: int) -> list:
    """前缀和实现：耗时与窗口大小无关。

    实测 100 万点、窗口 101 时朴素逐窗口求和要 5 秒——拖一次滑块卡一次。
    缺失值既不参与求和、也不能被跨过去：用"窗口内最后一个 null 的位置"来判定。
    """
    count = len(values)
    half = window // 2
    prefix = [0.0] * (count + 1)
    last_null = [-1] * count
    for i, value in enumerate(values):
        prefix[i + 1] = prefix[i] + (0.0 if value is None else value)
        if value is None:
            last_null[i] = i
        elif i:
            last_null[i] = last_null[i - 1]

    out: list = []
    for i in range(count):
        left = max(0, i - half)
        right = min(count - 1, i - half + window - 1)
        if last_null[right] >= left:
            out.append(None)
        else:
            out.append((prefix[right + 1] - prefix[left]) / (right - left + 1))
    return out


PLUGIN = FilterPlugin(
    id=ID,
    display_name="滑动平均",
    version="1.0.0",
    apply=apply,
    declare_params=declare_params,
    needs_full_data=True,
)
