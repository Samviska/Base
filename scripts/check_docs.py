#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""文档与契约的一致性检查。

全量模式：链接有效性、JSON 语法、契约示例与 schema 的一致性、模块文档是否已登记。
--staged 模式：额外要求"代码有改动就必须更新 docs/DEVLOG.md"（pre-commit 使用）。

契约示例的校验依赖 jsonschema；未安装时跳过并提示，不算失败。
跳过文档更新检查：设置 SKIP_DOC_CHECK=1，并在提交信息里说明理由。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

# Windows 控制台默认按 ANSI 代码页解码，中文提示会乱码，这里统一按 UTF-8 输出
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

ROOT = Path(__file__).resolve().parent.parent

# markdown 内的相对链接，只关心指向本仓库文件的
LINK_RE = re.compile(r"\]\(([^)\s]+\.(?:md|json))(?:#[^)]*)?\)")

# 这些路径下出现实质改动时，要求同一提交里更新 DEVLOG
CODE_PREFIXES = ("backend/", "frontend/", "contract/schema/", "contract/examples/")
# 占位与纯说明文件不算实质改动
IGNORED_SUFFIXES = (".gitkeep", "README.md")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def iter_files(pattern: str):
    for f in ROOT.rglob(pattern):
        if ".git" in f.parts or "node_modules" in f.parts:
            continue
        yield f


def check_links() -> list[str]:
    problems: list[str] = []
    for md in iter_files("*.md"):
        try:
            text = md.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            problems.append(f"{rel(md)}: 不是 UTF-8 编码")
            continue
        for target in LINK_RE.findall(text):
            if target.startswith(("http://", "https://")):
                continue
            if not (md.parent / target).resolve().exists():
                problems.append(f"{rel(md)}: 断链 -> {target}")
    return problems


def check_json() -> list[str]:
    problems: list[str] = []
    for js in iter_files("*.json"):
        try:
            json.loads(js.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            problems.append(f"{rel(js)}: JSON 语法错误 -> {exc}")
    return problems


def check_contract_examples() -> list[str]:
    """用 schema 校验示例。文件名以 invalid- 开头的期望被拒绝。"""
    schema_path = ROOT / "contract" / "schema" / "dataset.schema.json"
    examples_dir = ROOT / "contract" / "examples"
    if not schema_path.exists():
        return [f"缺少 {rel(schema_path)}"]
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        print("[跳过] 未安装 jsonschema，契约示例未做结构校验（pip install jsonschema）")
        return []

    validator = Draft202012Validator(json.loads(schema_path.read_text(encoding="utf-8")))
    problems: list[str] = []
    for f in sorted(examples_dir.glob("*.json")):
        expect_valid = not f.name.startswith("invalid-")
        errors = list(validator.iter_errors(json.loads(f.read_text(encoding="utf-8"))))
        if expect_valid and errors:
            problems.append(f"{rel(f)}: 期望合法却被拒绝 -> {errors[0].message}")
        if not expect_valid and not errors:
            problems.append(f"{rel(f)}: 期望非法却通过了校验（校验器在放水）")
    return problems


def check_module_registry() -> list[str]:
    """docs/modules/ 下的模块文档必须在 docs/MODULES.md 中登记。"""
    modules_dir = ROOT / "docs" / "modules"
    registry = ROOT / "docs" / "MODULES.md"
    if not modules_dir.exists() or not registry.exists():
        return []
    text = registry.read_text(encoding="utf-8")
    problems: list[str] = []
    for f in sorted(modules_dir.glob("*.md")):
        if f.name.startswith("_"):
            continue
        if f.name not in text:
            problems.append(f"docs/modules/{f.name}: 未在 docs/MODULES.md 中登记")
    return problems


def staged_files() -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    return [line.strip() for line in out.stdout.splitlines() if line.strip()]


def check_docs_updated(staged: list[str]) -> list[str]:
    if os.environ.get("SKIP_DOC_CHECK") == "1":
        print("[跳过] SKIP_DOC_CHECK=1，未检查文档更新")
        return []
    code_changed = [
        f for f in staged
        if f.startswith(CODE_PREFIXES) and not f.endswith(IGNORED_SUFFIXES)
    ]
    if not code_changed or "docs/DEVLOG.md" in staged:
        return []
    preview = ", ".join(code_changed[:5]) + (" ..." if len(code_changed) > 5 else "")
    return [
        "代码有改动，但 docs/DEVLOG.md 未在本提交中更新。",
        f"  改动的代码文件：{preview}",
        "  处理方式：在 docs/DEVLOG.md 最上面追加一条（格式见该文件顶部）。",
        "  确属无需记录的改动：SKIP_DOC_CHECK=1 git commit ... 并在提交信息里说明理由。",
    ]


def main() -> int:
    staged_only = "--staged" in sys.argv
    problems = check_links() + check_json() + check_contract_examples() + check_module_registry()
    if staged_only:
        problems += check_docs_updated(staged_files())

    if problems:
        print("\n检查未通过：")
        for p in problems:
            print("  - " + p)
        return 1

    print("文档与契约检查通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
