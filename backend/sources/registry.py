#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""数据源插件注册表：内置插件 + "目录即插件"的扫描。

插件是**外面送进来的代码**，所以加载与调用都必须假设它会出错：
任何异常都被捕获、记录、上报，**不向主流程传播**——一个坏插件既不该让应用起不来，
也不该连累其他插件（[ARCHITECTURE.md](../../docs/ARCHITECTURE.md) §6.3）。
"""
from __future__ import annotations

import importlib.util
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("backend.sources")

# 外部插件目录：仓库根下 plugins/sources/
PLUGIN_ROOT = Path(__file__).resolve().parents[2] / "plugins" / "sources"

# 入口模块必须提供的两样东西
_REQUIRED_ATTRS = ("extract", "declare_params")


@dataclass(frozen=True)
class SourcePlugin:
    """一个数据源插件对外的全部信息。

    `mode`：`oneshot`（读一个已存在的文件）或 `stream`（持续模式，本期只留字段）。
    `origin`：插件来自哪里（内置 / 目录路径），出错时要指得出来。
    """

    id: str
    display_name: str
    version: str
    extract: Callable[[str, dict], dict]
    declare_params: Callable[[], list[dict]]
    mode: str = "oneshot"
    origin: str = "内置"
    notes: str = ""


_PLUGINS: dict[str, SourcePlugin] = {}
_LOAD_WARNINGS: list[str] = []


def register(plugin: SourcePlugin) -> None:
    if plugin.id in _PLUGINS:
        raise ValueError(f"数据源插件 id 重复：{plugin.id}")
    _PLUGINS[plugin.id] = plugin


def get_plugin(plugin_id: str) -> SourcePlugin:
    try:
        return _PLUGINS[plugin_id]
    except KeyError:
        known = "、".join(sorted(_PLUGINS)) or "（未注册任何插件）"
        raise ValueError(f"未知的数据源插件 {plugin_id!r}；可用：{known}") from None


def list_plugins() -> list[SourcePlugin]:
    return [_PLUGINS[key] for key in sorted(_PLUGINS)]


def load_warnings() -> list[str]:
    """上次扫描产生的警告：供界面提示"哪些插件坏了"（S4）。"""
    return list(_LOAD_WARNINGS)


def load_directory(root: Path | str | None = None) -> list[str]:
    """扫描插件目录并注册。空目录、缺失目录都是合法状态。

    返回本次的警告列表（已经同时写进日志）。
    """
    directory = Path(root) if root else PLUGIN_ROOT
    _LOAD_WARNINGS.clear()
    if not directory.is_dir():
        return []

    for child in sorted(directory.iterdir()):
        # 下划线开头是模板与草稿，不该被加载
        if not child.is_dir() or child.name.startswith(("_", ".")):
            continue
        try:
            plugin = _load_one(child)
            existing = _PLUGINS.get(plugin.id)
            if existing is not None:
                # 同一目录被重复扫描（启动后又手动扫一次）不算问题，别刷警告
                if existing.origin != plugin.origin:
                    _warn(f"插件目录 {child.name} 的 id {plugin.id!r} 已被 {existing.origin} 占用，已跳过")
                continue
            _PLUGINS[plugin.id] = plugin
            log.info("已加载数据源插件：%s（%s，%s）", plugin.display_name, child.name, plugin.id)
        except Exception as exc:  # 坏插件只影响它自己
            _warn(f"插件目录 {child.name} 加载失败：{type(exc).__name__}: {exc}")
    return list(_LOAD_WARNINGS)


def _load_one(directory: Path) -> SourcePlugin:
    manifest_path = directory / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError("缺少 manifest.json")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"manifest.json 不是合法 JSON：{exc}") from exc
    if not isinstance(manifest, dict):
        raise ValueError("manifest.json 的内容必须是对象")

    for key in ("id", "display_name", "version", "entry"):
        if not manifest.get(key):
            raise ValueError(f"manifest 缺少字段 {key}")

    entry = directory / str(manifest["entry"])
    if not entry.is_file():
        raise ValueError(f"manifest 指定的入口文件不存在：{manifest['entry']}")

    module = _import_file(entry)
    missing = [name for name in _REQUIRED_ATTRS if not callable(getattr(module, name, None))]
    if missing:
        raise ValueError(f"入口模块缺少函数：{', '.join(missing)}")

    return SourcePlugin(
        id=str(manifest["id"]),
        display_name=str(manifest["display_name"]),
        version=str(manifest["version"]),
        extract=module.extract,
        declare_params=module.declare_params,
        mode=str(manifest.get("mode", "oneshot")),
        origin=str(directory),
        notes=str(manifest.get("notes", "")),
    )


def _import_file(path: Path):
    # 插件不要求是 Python 包，所以按文件路径导入；模块名带目录名以免互相覆盖
    spec = importlib.util.spec_from_file_location(f"dsh_source_{path.parent.name}", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"无法导入入口文件：{path.name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _warn(message: str) -> None:
    _LOAD_WARNINGS.append(message)
    log.warning("%s", message)
