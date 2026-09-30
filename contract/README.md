# 契约权威定义

这里放**语言中立**的契约定义，作为 Python 后端与 JavaScript 前端之间的**唯一依据**。
两边的实现都必须以这里为准，不得各自定义一套。

## 目录

| 目录 | 内容 |
| --- | --- |
| `schema/` | JSON Schema 等结构定义 |
| `examples/` | 示例数据（供测试、插件自检、文档引用） |
| `tests/` | 校验用例（语言中立，当前为空；Python 侧用例见 `backend/tests/test_contract.py`） |

### 当前内容

| 文件 | 用途 |
| --- | --- |
| `schema/dataset.schema.json` | **契约的唯一权威结构定义**（JSON Schema draft 2020-12）。单文件，内部用 `$defs` 组织，避免跨文件 `$ref` 带来的加载复杂度 |
| `examples/example-basic.json` | 合法示例：多序列、`time` 轴、`categorical` 轴、`null` 缺失值、注解、`extensions` 未知字段 |
| `examples/example-unknown-kind.json` | 合法示例：核心不认识的 `kind` + `numeric_values`（对上一条非法例的正例） |
| `examples/invalid-missing-unit.json` | 非法：`series.unit` 缺失 |
| `examples/invalid-unknown-kind.json` | 非法：未知 `kind` 但未声明 `numeric_values` |
| `examples/invalid-time-no-origin.json` | 非法：`time` 轴缺 `origin` |
| `examples/invalid-length-mismatch.json` | 非法：`x.data` 与 `y.data` 不等长（schema 表达不了，靠校验器的跨字段检查） |

> schema 的 `$id` 使用 URN 形式，它只是**标识符**，不指向任何真实网站。
> schema 只约束结构；**x 与 y 等长**这类跨字段检查由校验器补充实现（JSON Schema 无法表达）。

## 怎么校验

```powershell
.venv\Scripts\python.exe scripts\check_docs.py                          # 全量：含示例校验
.venv\Scripts\python.exe -m unittest discover -s backend/tests -t . -v  # 校验器用例
```

校验器在 `backend/contract/`，示例的期望结果由文件名决定：
`invalid-` 开头必须被拒绝，其余必须通过。新增示例即自动纳入这两个入口，**不需要改脚本**。

## 规则

1. 契约定义**不依赖任何模块**；所有模块依赖它。
2. 变更时按顺序做完：**提升版本号 → 更新校验器 → 更新 [docs/contract.md](../docs/contract.md) → 记 [DEVLOG](../docs/DEVLOG.md)（含影响面）**。
3. **未知字段必须原样保留**：示例里应包含扩展字段，并有往返测试覆盖。
4. 示例数据必须**真实可跑**，不能是随手编的片段——它们同时是插件自检的输入。
5. 校验用例要**成对**：一份合法、一份对应的非法，用来证明校验器不是在放水。
