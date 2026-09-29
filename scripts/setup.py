#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""首次使用的一次性环境配置。

为什么需要它：`core.hooksPath` 属于**本地 git 配置**，不会随仓库分发。
新克隆的仓库若没跑过本脚本，pre-commit 钩子根本不执行——所有检查形同虚设，
而且没有任何提示。这是整机制里最容易被忽略的一环。

用法：python scripts/setup.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

ROOT = Path(__file__).resolve().parent.parent
HOOKS_DIR = ".githooks"


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )


def main() -> int:
    if not (ROOT / ".git").exists():
        print("当前目录不是 git 仓库，无法配置钩子")
        return 1

    if not (ROOT / HOOKS_DIR / "pre-commit").exists():
        print(f"找不到钩子文件：{HOOKS_DIR}/pre-commit")
        return 1

    result = git("config", "core.hooksPath", HOOKS_DIR)
    if result.returncode != 0:
        print("设置 core.hooksPath 失败：" + result.stderr.strip())
        return 1

    print(f"已启用 git 钩子：core.hooksPath = {HOOKS_DIR}")
    print("自检：python scripts/check_docs.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
