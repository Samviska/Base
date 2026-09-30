#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""列目录：给界面一个"选文件"的入口。

浏览器拿不到本机文件系统路径，所以浏览目录必须由后端提供（本地应用场景）。
**只列名字与大小，不读内容**——读内容是数据源插件的活。

响应里带 `roots` 与 `shortcuts`：整块硬盘都要能去，不能只在项目目录里打转。
"""
from __future__ import annotations

import os
import string
from pathlib import Path

from .errors import INVALID_REQUEST, CoreError

# 一个目录最多列这么多条：几万个文件的目录会把界面和消息都拖住
MAX_ENTRIES = 2000

_SHORTCUT_NAMES = {"Desktop": "桌面", "Documents": "文档", "Downloads": "下载"}


def list_directory(path: str | None) -> dict:
    target = _resolve(path)

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
        "roots": _roots(),
        "shortcuts": _shortcuts(),
    }


def _resolve(path: str | None) -> Path:
    """把入参变成一个真实存在的目录。

    相对路径按调用方的工作目录解析——界面给不出绝对路径时才走这条路；
    传文件（或不存在）时退到它所在目录，别让一次误点断掉浏览。
    """
    if not path:
        return Path.home()
    candidate = Path(path).expanduser()
    if candidate.is_dir():
        return candidate
    if candidate.parent.is_dir():
        return candidate.parent
    return Path.home()


def _roots() -> list[str]:
    if os.name != "nt":
        return ["/"]
    return [f"{letter}:\\" for letter in string.ascii_uppercase if Path(f"{letter}:/").is_dir()]


def _shortcuts() -> list[dict]:
    home = Path.home()
    items = [{"name": "主目录", "path": str(home)}]
    for folder, label in _SHORTCUT_NAMES.items():
        candidate = home / folder
        if candidate.is_dir():
            items.append({"name": label, "path": str(candidate)})
    return items
