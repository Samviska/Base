#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""命令分发：把一条请求消息变成一条响应消息。

只做三件事：校验入参、调对应模块、把异常翻译成失败响应。
业务逻辑不写在这里——那属于各模块。

**每条请求都必须回响应，异常路径也一样**：不回的话前端会永远停在加载中（server.md §6）。
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from backend.filters import get_plugin, list_plugins

from .errors import (
    INTERNAL,
    INVALID_REQUEST,
    PLUGIN_NOT_FOUND,
    UNKNOWN_TYPE,
    CoreError,
)
from .session import Session
from .source import load

# 已登记但尚未实现的消息：标注与会话持久化属第 6 批。
# 用 INTERNAL + 明确文案，而不是谎报 UNKNOWN_TYPE——它们确实登记在 messages.md 里
_PENDING = (
    "list_annotations",
    "add_annotation",
    "update_annotation",
    "remove_annotation",
    "save_session",
    "load_session",
)


def handle(session: Session, message: Any) -> dict | None:
    """处理一条请求，返回响应信封。

    返回 `None` 表示这不是一条可配对的请求（缺 `id` 或结构不对），由调用方记日志。
    """
    if not isinstance(message, dict):
        return None
    msg_id = message.get("id")
    msg_type = message.get("type")
    if msg_id is None or not isinstance(msg_type, str):
        return None

    payload = message.get("payload")
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        return _failure(msg_id, msg_type, CoreError(INVALID_REQUEST, "payload 必须是对象"))

    command = _COMMANDS.get(msg_type)
    if command is None:
        if msg_type in _PENDING:
            return _failure(msg_id, msg_type, CoreError(INTERNAL, f"{msg_type} 尚未实现（第 6 批）"))
        return _failure(msg_id, msg_type, CoreError(UNKNOWN_TYPE, f"未登记的消息类型：{msg_type}"))

    try:
        result = command(session, payload)
    except CoreError as exc:
        return _failure(msg_id, msg_type, exc)
    except Exception as exc:  # 兜底：任何未预期异常也要有响应，不能让前端干等
        return _failure(msg_id, msg_type, CoreError(INTERNAL, f"{type(exc).__name__}: {exc}"))
    return {"id": msg_id, "type": msg_type, "ok": True, "payload": result}


def _list_plugins(session: Session, payload: dict) -> dict:
    # 数据源与渲染两类插件分属第 2 批与第 5 批：现在如实为空数组，而不是省略字段或伪造一条
    return {
        "plugins": [
            {
                "id": plugin.id,
                "type": "filter",
                "version": plugin.version,
                "display_name": plugin.display_name,
                "params": plugin.declare_params(),
            }
            for plugin in list_plugins()
        ]
    }


def _open_file(session: Session, payload: dict) -> dict:
    path = payload.get("path")
    if not isinstance(path, str) or not path:
        raise CoreError(INVALID_REQUEST, "open_file 需要字符串 path")

    plugin = payload.get("source_plugin")
    if plugin:
        raise CoreError(
            PLUGIN_NOT_FOUND,
            f"数据源插件机制尚未落地（第 2 批）：当前只能直接打开契约 JSON，收到 {plugin!r}",
        )

    session.open(load(path), {"path": path, "plugin": None})
    return session.summary()


def _close_source(session: Session, payload: dict) -> dict:
    session.close()
    return {"closed": True}


def _list_storage_formats(session: Session, payload: dict) -> dict:
    # 存储实现属第 2 批：当前一个格式都没有，就回空数组
    return {"formats": []}


def _query_range(session: Session, payload: dict) -> dict:
    x0 = _number(payload.get("x0"), "x0")
    x1 = _number(payload.get("x1"), "x1")
    resolution = payload.get("resolution")
    if isinstance(resolution, bool) or not isinstance(resolution, int) or resolution < 1:
        raise CoreError(INVALID_REQUEST, "resolution 必须是 >= 1 的整数")

    series = payload.get("series")
    if series is not None:
        if not isinstance(series, list) or any(not isinstance(name, str) for name in series):
            raise CoreError(INVALID_REQUEST, "series 必须是字符串数组")

    return session.query(series=series or None, x0=x0, x1=x1, resolution=resolution)


def _get_filter_chain(session: Session, payload: dict) -> dict:
    return {"chain": session.chain}


def _set_filter_chain(session: Session, payload: dict) -> dict:
    session.set_chain(_validate_chain(payload.get("chain")))
    return {"applied": True}


def _validate_chain(chain: Any) -> list[dict]:
    if not isinstance(chain, list):
        raise CoreError(INVALID_REQUEST, "chain 必须是数组")
    for step in chain:
        if not isinstance(step, dict) or not isinstance(step.get("plugin"), str) or not step["plugin"]:
            raise CoreError(INVALID_REQUEST, "chain 的每一项都必须带非空 plugin 字段")
        params = step.get("params")
        if params is not None and not isinstance(params, dict):
            raise CoreError(INVALID_REQUEST, "chain 的 params 必须是对象")
        try:
            get_plugin(step["plugin"])
        except ValueError as exc:
            # 插件不存在属于"请求指定的东西不存在"，比笼统的 INVALID_REQUEST 更准
            raise CoreError(PLUGIN_NOT_FOUND, str(exc)) from exc
    return chain


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CoreError(INVALID_REQUEST, f"{field} 必须是数值")
    return float(value)


def _failure(msg_id: Any, msg_type: str, error: CoreError) -> dict:
    return {"id": msg_id, "type": msg_type, "ok": False, "error": error.as_error()}


_COMMANDS: dict[str, Callable[[Session, dict], dict]] = {
    "list_plugins": _list_plugins,
    "open_file": _open_file,
    "close_source": _close_source,
    "list_storage_formats": _list_storage_formats,
    "query_range": _query_range,
    "get_filter_chain": _get_filter_chain,
    "set_filter_chain": _set_filter_chain,
}
