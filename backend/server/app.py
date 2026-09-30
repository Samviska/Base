#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""WebSocket 服务端：建连、信封收发、按 `id` 配对请求与响应。

本模块不做业务逻辑；消息类型必须已在 [messages.md](../../docs/messages.md) 登记。

磁盘 IO 与 CPU 密集的命令（打开文件、聚合）放到工作线程执行：
接收循环一旦被堵住，将来的实时数据就会在缓冲区里丢掉。
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from websockets.asyncio.server import serve

from backend.core import Session, handle

# 协议版本随 M1 hello 下发，前端据此校对；改消息形状时一起改
PROTOCOL_VERSION = "1.0"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765

_VERSION_FILE = Path(__file__).resolve().parents[2] / "VERSION"

log = logging.getLogger("backend.server")


def backend_version() -> str:
    return _VERSION_FILE.read_text(encoding="utf-8").strip()


async def handler(websocket) -> None:
    """一条连接一个会话：会话状态不跨连接共享。"""
    session = Session()
    await _send(
        websocket,
        {
            "type": "hello",
            "payload": {"protocol_version": PROTOCOL_VERSION, "backend_version": backend_version()},
        },
    )

    async for raw in websocket:
        try:
            message = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            # 结构都不对，连 id 都没有，回不了响应，只能记日志
            log.warning("收到无法解析的消息，已忽略：%s", exc)
            continue

        response = await asyncio.to_thread(handle, session, message)
        if response is None:
            log.warning("收到没有 id 的消息，已忽略：%.200r", message)
            continue
        await _send(websocket, response)


async def serve_forever(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    try:
        async with serve(handler, host, port):
            log.info("WebSocket 服务已就绪：ws://%s:%d（Ctrl+C 停止）", host, port)
            await asyncio.Event().wait()
    except OSError as exc:
        raise SystemExit(
            f"端口 {port} 绑定失败（多半已被占用）：{exc}\n"
            f"  换个端口：python -m backend.server --port {port + 1}"
        ) from exc


async def _send(websocket, message: dict) -> None:
    # ensure_ascii=False：日志与抓包要能直接读出中文，否则全是转义序列
    await websocket.send(json.dumps(message, ensure_ascii=False))
