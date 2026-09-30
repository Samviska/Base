#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""启动后端服务：`python -m backend.server [--host 127.0.0.1] [--port 8765]`

开发期直接跑源码，不打包（见 docs/overview.md §6）。
"""
from __future__ import annotations

import argparse
import asyncio
import logging

from .app import DEFAULT_HOST, DEFAULT_PORT, serve_forever


def main() -> int:
    parser = argparse.ArgumentParser(description="嵌入式数据绘图后端（WebSocket 服务）")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"默认 {DEFAULT_HOST}")
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"默认 {DEFAULT_PORT}；被占用时换一个",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        asyncio.run(serve_forever(args.host, args.port))
    except KeyboardInterrupt:
        print("已停止")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
