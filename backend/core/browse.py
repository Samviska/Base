#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""列目录：给界面一个"选文件"的入口。

浏览器拿不到本机文件系统路径，所以浏览目录必须由后端提供（本地应用场景）。
**只列名字与大小，不读内容**——读内容是数据源插件的活。
"""
from __future__ import annotations

from pathlib import Path

from .errors import INVALID_REQUEST, CoreError

# 一个目录最多列这么多条：几万个文件的目录会把界面和消息都拖住
MAX_ENTRIES = 2000


def list_directory(path: str | None) -> dict:
    target = Path(path).expanduser() if path else Path.home()
    if not target.is_dir():
        # 传进来的是文件（或不存在）时退到它所在的目录，别让一次误点断掉浏览
        target = target.parent if target.parent.is_dir() else Path.home()

    try:
        children = sorted(target.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))
    except OSError as exc:
        raise CoreError(INVALID_REQUEST, f"目录无法读取：{target}（{exc.strerror or exc}）") from exc

    entries = []
    for child in children[:MAX_ENTRIES]:
        try:
            is_dir = child.is_dir()
            size = None if is_dir else child.stat().st_size
        except OSError:
            continue  # 权限不足或失效链接：跳过这一条，不让整次浏览失败
        entries.append(
            {
                "name": child.name,
                "path": str(child),
                "type": "dir" if is_dir else "file",
                "size": size,
            }
        )

    parent = target.parent
    return {
        "path": str(target),
        "parent": str(parent) if parent != target else None,
        "entries": entries,
        "truncated": len(children) > MAX_ENTRIES,
    }
