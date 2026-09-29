#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""首次使用的一次性环境配置：建虚拟环境 → 装依赖 → 启用 git 钩子。

为什么必须跑它：

- `core.hooksPath` 是**本地 git 配置**，不随仓库分发。新克隆的仓库若没跑过本脚本，
  pre-commit 钩子根本不执行——所有检查形同虚设，而且没有任何提示。
- 依赖装在项目自己的 `.venv` 里，别人 clone 后不会自带。

用法：python scripts/setup.py
"""
from __future__ import annotations

import os
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
VENV_PYTHON = Path(".venv") / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )


def ensure_venv() -> Path | None:
    exe = ROOT / VENV_PYTHON
    if exe.exists():
        print(f"[1/3] 虚拟环境已存在：{VENV_PYTHON}")
        return exe
    print(f"[1/3] 创建虚拟环境 {VENV_PYTHON.parent.parent} ...")
    result = subprocess.run([sys.executable, "-m", "venv", ".venv"], cwd=ROOT)
    if result.returncode != 0 or not exe.exists():
        print("  创建失败")
        return None
    print("  完成")
    return exe


def install_requirements(exe: Path) -> bool:
    req = ROOT / "requirements.txt"
    if not req.exists():
        print("[2/3] 没有 requirements.txt，跳过依赖安装")
        return True
    print("[2/3] 安装依赖 ...")
    result = subprocess.run(
        [str(exe), "-m", "pip", "install", "-q", "-r", "requirements.txt"], cwd=ROOT
    )
    if result.returncode != 0:
        print("  安装失败")
        return False
    print("  完成")
    return True


def enable_hooks() -> bool:
    print("[3/3] 启用 git 钩子 ...")
    if not (ROOT / HOOKS_DIR / "pre-commit").exists():
        print(f"  找不到钩子文件：{HOOKS_DIR}/pre-commit")
        return False
    result = git("config", "core.hooksPath", HOOKS_DIR)
    if result.returncode != 0:
        print("  设置失败：" + result.stderr.strip())
        return False
    print(f"  完成（core.hooksPath = {HOOKS_DIR}）")
    return True


def main() -> int:
    if not (ROOT / ".git").exists():
        print("当前目录不是 git 仓库")
        return 1

    exe = ensure_venv()
    if exe is None or not install_requirements(exe) or not enable_hooks():
        return 1

    print("\n环境就绪。自检：")
    print(f"  {VENV_PYTHON} scripts/check_docs.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
