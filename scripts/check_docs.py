#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""文档与契约的一致性检查。

全量模式：链接有效性、JSON 语法、契约示例与契约校验器的一致性、模块文档是否已登记、
文档里的编号引用是否落在登记范围内。
--staged 模式：额外要求"代码有改动就必须更新 docs/DEVLOG.md"（pre-commit 使用）。

契约示例由 backend/contract 的校验器校验（依赖 jsonschema）；
**缺依赖或校验器导入失败时判失败**——静默跳过的校验等于没有校验。
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

# 这些路径下出现实质改动时，要求同一提交里更新 DEVLOG。
# 含 scripts/：改检查脚本本身属于"改规则"，同样影响后续所有人的做法。
CODE_PREFIXES = (
    "backend/", "frontend/", "plugins/", "scripts/",
    "contract/schema/", "contract/examples/",
)

# 模块目录 → 该模块的开发文档。目录下**新增或删除**文件时，要求文档同步更新。
# 只修改既有文件时不强制（避免改一行代码就要动文档），只在 stderr 提示。
MODULE_DOC_MAP = {
    "backend/core/": "docs/modules/core.md",
    "backend/contract/": "docs/modules/contract.md",
    "backend/sources/": "docs/modules/source.md",
    "backend/filters/": "docs/modules/filter.md",
    "backend/storage/": "docs/modules/storage.md",
    "backend/aggregate/": "docs/modules/aggregate.md",
    "backend/server/": "docs/modules/server.md",
    "frontend/ui/": "docs/modules/ui-shell.md",
    "frontend/api/": "docs/modules/api-client.md",
    "frontend/renderers/": "docs/modules/renderer.md",
}
# 占位与纯说明文件不算实质改动（AGENTS.md 是就地规则，不代表模块能力变化）
IGNORED_SUFFIXES = (".gitkeep", "README.md", "AGENTS.md")

# 编号登记表：文档里引用 `S5`/`D3` 这类编号，其含义与有效范围由该文件的 §1 声明。
# 没有登记处，编号换会话后就无从解析——引用的内容等于不存在。
ID_REGISTRY = ROOT / "docs" / "acceptance.md"
# 登记表行：| `S` | 成功标准 | 本文件 §3 | S1–S7 |
# 范围分隔符放宽到常见几种横线，避免全角/半角差异导致整张表解析失败
ID_ROW_RE = re.compile(
    r"^\|\s*`([A-Z]{1,3})`\s*\|[^|]*\|[^|]*\|\s*([A-Z]{1,3})(\d{1,3})\s*[–—~\-]\s*[A-Z]{1,3}(\d{1,3})\s*\|"
)


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
    """用契约校验器校验示例（只此一处实现，跨字段规则也走它）。

    文件名以 invalid- 开头的期望被拒绝，**且必须给出出错字段路径**：
    报"数据不合法"而不知哪儿错，等于没校验。
    """
    schema_path = ROOT / "contract" / "schema" / "dataset.schema.json"
    examples_dir = ROOT / "contract" / "examples"
    if not schema_path.exists():
        return [f"缺少 {rel(schema_path)}"]

    # 本脚本在 scripts/ 下执行，仓库根不在 sys.path 里；校验器按 backend.contract 导入
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    try:
        from backend.contract import validate
    except ImportError as exc:
        # 契约校验是核心保障。静默跳过等于没有校验，所以这里必须判失败
        return [
            f"契约校验器无法导入：{exc}",
            "  安装依赖：pip install jsonschema",
        ]

    problems: list[str] = []
    for f in sorted(examples_dir.glob("*.json")):
        expect_valid = not f.name.startswith("invalid-")
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            problems.append(f"{rel(f)}: JSON 语法错误 -> {exc}")
            continue
        try:
            result = validate(data)
        except RuntimeError as exc:
            # schema 读不到属仓库损坏，不是数据问题：报出来而不是逐份示例重复报
            problems.append(str(exc))
            break

        if expect_valid and not result.ok:
            problems.append(f"{rel(f)}: 期望合法却被拒绝 -> {result.violations[0].describe()}")
        elif not expect_valid:
            if result.ok:
                problems.append(f"{rel(f)}: 期望非法却通过了校验（校验器在放水）")
            elif not any(v.path for v in result.violations):
                problems.append(f"{rel(f)}: 被拒绝但未指出出错字段路径")
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


def load_id_registry() -> dict[str, tuple[int, int]]:
    """解析编号登记表，返回 {前缀: (下界, 上界)}。"""
    registry: dict[str, tuple[int, int]] = {}
    if not ID_REGISTRY.exists():
        return registry
    for line in ID_REGISTRY.read_text(encoding="utf-8").splitlines():
        m = ID_ROW_RE.match(line.strip())
        if not m:
            continue
        prefix, inner, lo, hi = m.group(1), m.group(2), int(m.group(3)), int(m.group(4))
        # 范围列写的前缀必须与登记的前缀一致，写错了这条路等于没校验
        if inner != prefix or lo > hi:
            continue
        registry[prefix] = (lo, hi)
    return registry


def check_id_references() -> list[str]:
    """文档里引用的编号必须落在登记表声明的范围内。

    只校验**已登记**的前缀：未登记的前缀无法与 UTF8 / SHA256 这类普通词区分，
    强判会大量误报。新增前缀属于"新增体系"，由 AGENTS.md 要求人工登记。
    围栏代码块内的内容不检查——那里是示例与验证证据，不是引用。
    """
    if not ID_REGISTRY.exists():
        return [f"缺少编号登记表 {rel(ID_REGISTRY)}"]
    registry = load_id_registry()
    if not registry:
        return [f"{rel(ID_REGISTRY)} 的编号登记表为空或格式不符，编号引用无法校验"]

    problems: list[str] = []
    seen: set[tuple[str, str]] = set()
    ordered = sorted(registry.items(), key=lambda kv: -len(kv[0]))  # 长前缀优先
    for md in iter_files("*.md"):
        try:
            text = md.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue  # 编码问题由 check_links 报告，这里不重复报
        in_fence = False
        for line in text.splitlines():
            if line.lstrip().startswith(("```", "~~~")):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            for prefix, (lo, hi) in ordered:
                for m in re.finditer(rf"\b{prefix}(\d{{1,3}})\b", line):
                    n = int(m.group(1))
                    if lo <= n <= hi:
                        continue
                    key = (rel(md), f"{prefix}{n}")
                    if key in seen:
                        continue
                    seen.add(key)
                    problems.append(
                        f"{rel(md)}: 引用了未定义的编号 {prefix}{n}"
                        f"（登记范围 {prefix}{lo}–{prefix}{hi}）"
                    )
    return problems


def was_updated(rows: list[tuple[str, str]], path: str) -> bool:
    """判断某个文件是否被**实质更新**。

    只认新增 / 修改 / 重命名。删除也会让路径出现在暂存区里——
    若不排除，删掉文档就等于"更新了文档"，这是最容易漏掉的绕过方式。
    """
    return any(p == path and st in ("A", "M", "R") for st, p in rows)


def staged_status() -> list[tuple[str, str]]:
    """返回 [(状态字母, 路径)]。状态：A 新增 / M 修改 / D 删除 / R 重命名。"""
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-status"],
        cwd=ROOT, capture_output=True, text=True, check=True,
        # Windows 上默认按 locale(GBK) 解码，含中文路径时会直接抛异常
        encoding="utf-8", errors="replace",
    )
    rows: list[tuple[str, str]] = []
    for line in out.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            rows.append((parts[0][:1], parts[-1].strip().replace("\\", "/")))
    return rows


def commit_rows(rev: str) -> list[tuple[str, str]] | None:
    """读取某个提交的改动清单，供 CI 复用同一套过程约束检查。

    CI 里没有"暂存区"，只有提交，所以需要这个入口。
    已知缺口：合并提交不展开差异，会返回空清单，过程约束检查随之跳过。
    """
    out = subprocess.run(
        ["git", "show", "--name-status", "--format=", rev],
        cwd=ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    if out.returncode != 0:
        return None
    rows: list[tuple[str, str]] = []
    for line in out.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            rows.append((parts[0][:1], parts[-1].strip().replace("\\", "/")))
    return rows


def check_module_doc_sync(rows: list[tuple[str, str]]) -> list[str]:
    """模块目录下新增或删除文件，说明该模块的能力变了，模块文档必须同步。"""
    if os.environ.get("SKIP_DOC_CHECK") == "1":
        return []
    problems: list[str] = []
    for prefix, doc in MODULE_DOC_MAP.items():
        structural = [
            p for st, p in rows
            if p.startswith(prefix) and st in ("A", "D") and not p.endswith(IGNORED_SUFFIXES)
        ]
        if structural and not was_updated(rows, doc):
            sample = ", ".join(structural[:3]) + (" ..." if len(structural) > 3 else "")
            problems.append(
                f"{prefix} 下新增或删除了文件（{sample}），"
                f"说明该模块的能力变了，但 {doc} 未在本提交中更新。"
            )
    return problems


def check_docs_updated(rows: list[tuple[str, str]]) -> list[str]:
    if os.environ.get("SKIP_DOC_CHECK") == "1":
        print("[跳过] SKIP_DOC_CHECK=1，未检查文档更新")
        return []
    code_changed = [
        p for st, p in rows
        if p.startswith(CODE_PREFIXES) and st in ("A", "M", "R") and not p.endswith(IGNORED_SUFFIXES)
    ]
    if not code_changed or was_updated(rows, "docs/DEVLOG.md"):
        return []
    preview = ", ".join(code_changed[:5]) + (" ..." if len(code_changed) > 5 else "")
    return [
        "代码有改动，但 docs/DEVLOG.md 未在本提交中更新。",
        f"  改动的代码文件：{preview}",
        "  处理方式：在 docs/DEVLOG.md 最上面追加一条（格式见该文件顶部）。",
        "  确属无需记录的改动：SKIP_DOC_CHECK=1 git commit ... 并在提交信息里说明理由。",
    ]


def check_version_bumped(rows: list[tuple[str, str]]) -> list[str]:
    """本项目要求每次提交都伴随 VERSION 递增，避免版本号与代码脱节。"""
    if os.environ.get("SKIP_DOC_CHECK") == "1":
        return []
    substantial = [p for _, p in rows if not p.endswith(IGNORED_SUFFIXES)]
    if not substantial:
        return []  # 只动了占位或说明文件，不要求升版本
    if was_updated(rows, "VERSION"):
        return []
    return [
        "VERSION 未在本提交中更新。本项目要求每次提交都伴随版本号递增。",
        '  推荐做法：python scripts/commit.py -m "你的描述"（自动递增并提交）',
        "  确需跳过：SKIP_DOC_CHECK=1 git commit ... 并在提交信息里说明理由。",
    ]


def main() -> int:
    staged_only = "--staged" in sys.argv
    # commit.py 在递增 VERSION **之前**调用本脚本做预检，此时版本号必然还没变，
    # 故由它传 --skip-version 跳过该项。真正的强制检查发生在 git commit 触发的钩子里。
    skip_version = "--skip-version" in sys.argv
    commit_rev = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--commit=")), None)

    problems = (
        check_links()
        + check_json()
        + check_contract_examples()
        + check_module_registry()
        + check_id_references()
    )

    # 过程约束需要一份"改动清单"：本地来自暂存区，CI 来自提交
    rows: list[tuple[str, str]] | None = None
    if staged_only:
        rows = staged_status()
    elif commit_rev:
        rows = commit_rows(commit_rev)
        if rows is None:
            problems.append(f"无法读取提交 {commit_rev} 的改动清单")

    if rows is not None:
        problems += check_docs_updated(rows)
        problems += check_module_doc_sync(rows)
        if not skip_version:
            problems += check_version_bumped(rows)

    if problems:
        print("\n检查未通过：")
        for p in problems:
            print("  - " + p)
        return 1

    print("文档与契约检查通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
