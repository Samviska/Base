#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""规格化提交：检查 → 递增版本号 → 提交（可选打标签与推送）。

用法：
  python scripts/commit.py -m "描述" [--bump=auto|major|minor|patch] [--tag] [--push]

存在的理由：项目要求"每次提交都伴随版本号递增"。手工改 VERSION 既容易忘，
也容易算错；交给脚本后，这条规则只需记住一个命令。
pre-commit 负责拦住绕过本脚本的直接提交。
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT / "VERSION"
SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
# 契约定义所在路径：这些地方有改动就认为契约变了
CONTRACT_PREFIXES = ("contract/schema/", "contract/examples/")
# 出现新增文件即视为"新能力"的目录
CODE_ROOTS = ("backend", "frontend", "plugins")


def git(*args: str) -> subprocess.CompletedProcess:
    # Windows 上 subprocess 默认按 locale(GBK) 解码，而 git 与钩子输出 UTF-8，必须显式指定
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )


def read_version() -> tuple[int, int, int]:
    raw = VERSION_FILE.read_text(encoding="utf-8").strip()
    m = SEMVER.match(raw)
    if not m:
        sys.exit(f"VERSION 内容不是 MAJOR.MINOR.PATCH 格式：{raw!r}")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def staged_status() -> list[tuple[str, str]]:
    """[(状态字母, 路径)]，状态：A 新增 / M 修改 / D 删除 / R 重命名。"""
    out = git("diff", "--cached", "--name-status")
    rows: list[tuple[str, str]] = []
    for line in out.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            rows.append((parts[0][:1], parts[-1].strip().replace("\\", "/")))
    return rows


def infer_bump(rows: list[tuple[str, str]]) -> str:
    paths = [p for _, p in rows]
    if any(p.startswith(CONTRACT_PREFIXES) for p in paths):
        return "minor"
    if any(st == "A" and p.split("/")[0] in CODE_ROOTS for st, p in rows):
        return "minor"
    return "patch"


def bump(version: tuple[int, int, int], level: str) -> tuple[int, int, int]:
    major, minor, patch = version
    if level == "major":
        return major + 1, 0, 0
    if level == "minor":
        return major, minor + 1, 0
    return major, minor, patch + 1


def main() -> int:
    parser = argparse.ArgumentParser(description="检查、递增版本号并提交")
    parser.add_argument("-m", "--message", required=True, help="提交描述（不要带版本号，脚本会加）")
    parser.add_argument("--bump", default="auto", choices=["auto", "major", "minor", "patch"])
    parser.add_argument("--tag", action="store_true", help="提交后打标签 vX.Y.Z（交付时用）")
    parser.add_argument("--push", action="store_true", help="提交后推送到远端")
    args = parser.parse_args()

    rows = staged_status()
    if not rows:
        sys.exit("暂存区为空。先 git add，再运行本脚本。")

    # 钩子是本地配置，新克隆的仓库可能没启用；不检查的话所有校验都会静默失效
    hooks = git("config", "core.hooksPath")
    if hooks.stdout.strip() != ".githooks":
        sys.exit(
            "git 钩子未启用（core.hooksPath 不是 .githooks），提交前的强制检查不会执行。\n"
            "  clone 仓库后必须运行一次：python scripts/setup.py"
        )

    # 预检跳过版本号检查：递增发生在其后。真正的强制由 git commit 触发的钩子完成
    check = subprocess.run(
        [sys.executable, "scripts/check_docs.py", "--staged", "--skip-version"], cwd=ROOT
    )
    if check.returncode != 0:
        sys.exit("检查未通过，已中止提交（未改动 VERSION）")

    current = read_version()
    level = infer_bump(rows) if args.bump == "auto" else args.bump
    new = bump(current, level)
    new_str = ".".join(str(n) for n in new)

    VERSION_FILE.write_text(new_str + "\n", encoding="utf-8")
    git("add", "VERSION")

    subject = f"v{new_str} {args.message}"
    commit = git("commit", "-m", subject)
    if commit.returncode != 0:
        print(commit.stdout + commit.stderr)
        return 1

    if args.tag:
        tag = git("tag", f"v{new_str}")
        if tag.returncode != 0:
            print("打标签失败：" + tag.stderr.strip())
            return 1

    if args.push:
        push = git("push")
        if push.returncode != 0:
            print("推送失败：" + push.stderr.strip())
            return 1
        if args.tag:
            git("push", "--tags")

    old_str = ".".join(str(n) for n in current)
    print(f"\n已提交：{subject}")
    print(f"版本：{old_str} → {new_str}（级别 {level}）")
    if args.tag:
        print(f"已打标签：v{new_str}")
    if args.push:
        print("已推送")
    return 0


if __name__ == "__main__":
    sys.exit(main())
