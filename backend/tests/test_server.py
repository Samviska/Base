#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""端到端用例：起真服务、用真 WebSocket 客户端跑通「打开文件 → 请求视口数据」。

这是第 4 批的完成标志，所以用真连接测而不是桩：信封、id 配对、错误响应
这些恰恰是"看起来对、一联调就错"的地方。

在仓库根运行：python -m unittest discover -s backend/tests -t . -v
"""
from __future__ import annotations

import asyncio
import json
import unittest
from pathlib import Path

from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

from backend.server import PROTOCOL_VERSION, backend_version, handler

EXAMPLES = Path(__file__).resolve().parents[2] / "contract" / "examples"
BASIC = str(EXAMPLES / "example-basic.json")
TIMEOUT = 10


class ServerTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._cm = serve(handler, "127.0.0.1", 0)
        self._server = await self._cm.__aenter__()
        self.port = self._server.sockets[0].getsockname()[1]
        self.url = f"ws://127.0.0.1:{self.port}"

    async def asyncTearDown(self):
        await self._cm.__aexit__(None, None, None)

    async def call(self, websocket, msg_type: str, payload: dict | None = None, msg_id: int = 1) -> dict:
        """发一条请求并取回**同 id** 的响应；无 id 的事件（hello）跳过。"""
        await websocket.send(json.dumps({"id": msg_id, "type": msg_type, "payload": payload or {}}))
        while True:
            message = json.loads(await asyncio.wait_for(websocket.recv(), TIMEOUT))
            if message.get("id") == msg_id:
                return message

    async def drain_hello(self, websocket) -> None:
        await asyncio.wait_for(websocket.recv(), TIMEOUT)

    async def test_hello_is_an_event_without_id(self):
        async with connect(self.url) as websocket:
            hello = json.loads(await asyncio.wait_for(websocket.recv(), TIMEOUT))

        self.assertNotIn("id", hello)
        self.assertEqual("hello", hello["type"])
        self.assertEqual(PROTOCOL_VERSION, hello["payload"]["protocol_version"])
        self.assertEqual(backend_version(), hello["payload"]["backend_version"])

    async def test_open_then_query_round_trip(self):
        async with connect(self.url) as websocket:
            await self.drain_hello(websocket)
            opened = await self.call(websocket, "open_file", {"path": BASIC})
            self.assertTrue(opened["ok"], opened)
            self.assertEqual(["温度", "状态计数"], [s["name"] for s in opened["payload"]["series"]])

            queried = await self.call(
                websocket, "query_range", {"x0": 0, "x1": 400, "resolution": 2}, msg_id=2
            )

        payload = queried["payload"]
        self.assertTrue(payload["aggregated"])
        self.assertEqual([25.1, 26.0], payload["series"][0]["ymin"])
        self.assertEqual([25.3, 26.2], payload["series"][0]["ymax"])

    async def test_error_response_keeps_the_same_id(self):
        async with connect(self.url) as websocket:
            await self.drain_hello(websocket)
            response = await self.call(websocket, "made_up_type", msg_id=7)

        self.assertEqual(7, response["id"])
        self.assertFalse(response["ok"])
        self.assertEqual("UNKNOWN_TYPE", response["error"]["code"])

    async def test_connections_have_separate_sessions(self):
        async with connect(self.url) as first, connect(self.url) as second:
            await self.drain_hello(first)
            await self.drain_hello(second)

            self.assertTrue((await self.call(first, "open_file", {"path": BASIC}))["ok"])
            response = await self.call(
                second, "query_range", {"x0": 0, "x1": 400, "resolution": 10}, msg_id=5
            )

        self.assertEqual("INVALID_REQUEST", response["error"]["code"])

    async def test_broken_message_does_not_kill_the_connection(self):
        async with connect(self.url) as websocket:
            await self.drain_hello(websocket)
            await websocket.send("{ 这不是 JSON")
            response = await self.call(websocket, "list_plugins", msg_id=9)

        self.assertTrue(response["ok"])
        self.assertIn("moving-average", [p["id"] for p in response["payload"]["plugins"]])

    async def test_filter_chain_command_changes_query_result(self):
        async with connect(self.url) as websocket:
            await self.drain_hello(websocket)
            await self.call(websocket, "open_file", {"path": BASIC})
            before = await self.call(websocket, "query_range", {"x0": 0, "x1": 400, "resolution": 2}, msg_id=2)

            applied = await self.call(
                websocket,
                "set_filter_chain",
                {"chain": [{"plugin": "moving-average", "enabled": True, "params": {"window": 3}}]},
                msg_id=3,
            )
            after = await self.call(websocket, "query_range", {"x0": 0, "x1": 400, "resolution": 2}, msg_id=4)

        self.assertTrue(applied["payload"]["applied"])
        self.assertEqual([25.1, 26.0], before["payload"]["series"][0]["ymin"])
        # 滑动平均的结果带浮点残差（25.200000000000003），不比精确值
        self.assertAlmostEqual(25.2, after["payload"]["series"][0]["ymin"][0])
        self.assertAlmostEqual(26.1, after["payload"]["series"][0]["ymin"][1])


if __name__ == "__main__":
    unittest.main()
