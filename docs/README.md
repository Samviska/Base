# 文档地图

> **给接手的人或 AI**：先读完这一页，再决定去读哪份文档。
> 本页只做导航，不重复内容。内容有冲突时，以**被指向的那份文档**为准。

---

## 我要做某件事，该读哪里

| 我要做的事 | 先读 | 再读 |
| --- | --- | --- |
| 加一种新日志格式的解析 | [modules/source.md](modules/source.md) | [guides/add-source-plugin.md](guides/add-source-plugin.md) |
| 改 / 修渲染器的绘制或交互 | [modules/renderer.md](modules/renderer.md) | [contract.md](contract.md) |
| 加一个新图形样式 | [modules/renderer.md](modules/renderer.md) | [guides/add-renderer.md](guides/add-renderer.md) |
| 加一个滤波算法 | [modules/filter.md](modules/filter.md) | [guides/add-filter-plugin.md](guides/add-filter-plugin.md) |
| 改界面布局、加面板 | [modules/ui-shell.md](modules/ui-shell.md) | — |
| 改数据格式（契约） | [contract.md](contract.md) | **必须先读契约变更流程** |
| 加一种存储格式 | [modules/storage.md](modules/storage.md) | [guides/add-storage-format.md](guides/add-storage-format.md) |
| 改前后端通信的消息 | [protocol.md](protocol.md) | [modules/server.md](modules/server.md) |
| 改聚合算法 | [modules/aggregate.md](modules/aggregate.md) | [ARCHITECTURE.md](ARCHITECTURE.md) |
| 查"这个决定当初为什么这么定" | [DECISIONS.md](DECISIONS.md) | — |
| 查技术栈、版本、环境要求 | [overview.md](overview.md) | [DECISIONS.md](DECISIONS.md) |
| 查前后端有哪些消息 | [messages.md](messages.md) | [protocol.md](protocol.md) |
| 查"上次改了什么、为什么" | [DEVLOG.md](DEVLOG.md) | — |
| **准备提交 / 搞不清版本号怎么定** | [versioning.md](versioning.md) | — |
| 看还没做的功能 | [roadmap.md](roadmap.md) | — |
| 查验收标准、或 `S5` / `D3` 这类编号的含义 | [acceptance.md](acceptance.md) | — |
| **验证这套文档与规则换会话后还能不能用** | [guides/framework-test.md](guides/framework-test.md) | — |
| **第一次接触这个项目** | **[overview.md](overview.md)** | 本文件（文档地图） |
| **要开始开发这个项目** | [guides/kickoff.md](guides/kickoff.md) | — |

> **表里找不到你要做的事** → 说明文档有缺口，**先补文档再动手**。

---

## 文档清单

| 文件 | 作用 | 什么时候读 |
| --- | --- | --- |
| `README.md` | 本文件：文档地图 | 每次开始干活前 |
| `MODULES.md` | **模块地图**：模块 ↔ 代码位置 ↔ 文档 ↔ 可替换性 | 定位代码时 |
| `ARCHITECTURE.md` | 全局架构、分层规则、依赖方向、显示策略 | 第一次接手 / 改动跨模块时 |
| `overview.md` | **技术总览**：技术栈与版本、开发环境、目录架构、注意事项 | **第一次接手时先读** |
| `messages.md` | **消息清单**：前后端所有消息与 payload | 碰前后端交互时 |
| `contract.md` | **数据契约**：字段、轴描述、校验、版本规则 | 碰数据结构时**必读** |
| `protocol.md` | 前后端消息与通信规则 | 碰前后端交互时 |
| `DECISIONS.md` | 决策与理由 | 想改已定方案前 |
| `DEVLOG.md` | 开发日志：改了什么、为什么、影响面 | 排查历史 / 每次改完**必须写** |
| `versioning.md` | **版本号规则**：怎么递增、提交信息格式、标签 | 提交前 |
| `roadmap.md` | 交付范围与未实现功能 | 判断"这个该不该现在做" |
| `acceptance.md` | **验收标准与编号体系**：目标、成功标准、功能范围、验收清单 | 想知道"做成什么样算完成"，或读到不认识的编号时 |
| `modules/` | 每个模块的开发文档 | 改某个模块前**必读该模块** |
| `guides/` | 操作手册：怎么做某一件事 | 新增能力时 |

---

## 维护规则

### 规则由什么强制（不靠自觉）

| 层 | 机制 | 强制力 |
| --- | --- | --- |
| 1 | **[AGENTS.md](../AGENTS.md)**（项目根） | DSH 自动加载（项目根有 `.git` 即生效），**不依赖 AI 主动去读** |
| 2 | **各模块目录下的 `AGENTS.md`** | 碰到该目录时**按需注入**就地规则 |
| 3 | **pre-commit 钩子** | 代码改动未更新 `DEVLOG.md`、或模块下增删文件未更新模块文档 → **提交被拒绝** |
| 4 | `scripts/check_docs.py` | 链接 / JSON / 契约示例 / 模块登记 / **编号引用**，可随时或定期跑 |

> **第 3 层是唯一不依赖模型配合的一层**：换任何 LLM 都绕不过 git。
> 前两层若因换工具而失效，提交时的报错仍会说明该做什么。

```powershell
python scripts/check_docs.py            # 全量检查
python scripts/check_docs.py --staged   # 提交前检查（钩子自动调用）
```

临时跳过：`SKIP_DOC_CHECK=1 git commit ...`，**并在提交信息里说明理由**。

### 规则正文

1. **改了某个模块的代码，必须同步更新 `modules/` 下对应的文档。**
2. **每次代码改动，必须在 `DEVLOG.md` 追加一条**（格式见该文件顶部）。
3. **契约变更**（`contract.md`）必须：提升版本号 → 更新校验器 → 在 `DEVLOG.md` 标注影响面。
4. **新增决策**记入 `DECISIONS.md`；**不要**把决策写进 `DEVLOG.md`。两者是"为什么这么定"和"这次改了什么"的区别。
5. **文档只写约束、边界、原因。** 不写问答过程，不写改动履历，不写"本函数用于……"式的复述。
6. **术语先解释再用。** 不假设读者知道任何技术名词。
7. **规则必须配正例或反例。** 没有例子的规则等于没有规则。
