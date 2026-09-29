# 开发日志

> **这是给 AI 读和写的文件。**
> 目的：即使对话上下文完全丢失，也能靠它追溯"改过什么、为什么改、影响了谁"。
>
> **最新记录在最上面。**

---

## 什么时候必须写

| 时机 | 必须写吗 |
| --- | --- |
| 任何代码改动 | **是** |
| 契约变更 | **是**，且必须写明影响面与迁移方式 |
| 修复 bug | **是**，必须写**根因**（不是"改了什么"，而是"为什么会错"） |
| 新增或删除模块 | **是**，并同步更新 [MODULES.md](MODULES.md) |
| 改动文档体系、规则或工具链 | **是**（会影响后续所有人的做法） |
| 只改文档**内容** | 否 |
| 只调格式、改注释 | 否 |

> **强制方式**：代码有改动而 `DEVLOG.md` 未更新时，**pre-commit 会拒绝提交**。
> 临时跳过用 `SKIP_DOC_CHECK=1`，并在提交信息里说明理由。

---

## 格式（严格按此填写）

```markdown
## YYYY-MM-DD | 模块名 | 一句话标题

**改动**：改了哪些文件、最终做成了什么样
**原因**：为什么必须改（问题现象 / 需求来源）
**根因**：仅 bug 修复时填。为什么会出错，如何避免同类问题
**影响面**：契约变了吗？其他模块要跟着改吗？需要迁移吗？
**验证**：怎么证明改对了（可执行的验证方式，不是"测过了"）
**相关**：关联的决策、文档、条目编号
```

## 规则

1. **一条记录只记一件事**，不要合并多个改动。
2. **不写代码流水账**。"改了 a.py 第 30 行"没有价值；"聚合从按点改成按像素列"才有价值。
3. **`影响面` 必须诚实填写**。契约变了就要写出来，哪怕只是加了一个可选字段。
4. **决策不记在这里**，记到 [DECISIONS.md](DECISIONS.md)。
5. **不删除、不改写历史记录**。写错了就追加一条更正。

---

## 记录

### 2026-09-29 | 工具链 | 补第 8 个漏洞：钩子文件本身可被删除

**改动**：`commit.py` 的启动自检从"只查 `core.hooksPath` 配置"扩展为"配置正确**且**钩子文件存在且非空"。

**原因**：复测发现删掉 `.githooks/pre-commit` 之后：

- 直接 `git commit` 的**所有检查被静默跳过**（git 找不到 hook 文件时不报错），exit=0
- `commit.py` 也没发现——它只验证了配置指向哪，没验证目标是否还在

**根因**：自检只验证"配置指向哪里"，没验证"目标是否存在"。
**配置正确 + 文件缺失** = 看起来一切正常，实际毫无防护。这是本轮最隐蔽的一个漏洞。

**影响面**：无契约变更。

**验证**：删除钩子后 `python scripts/commit.py` 报错（exit=1）并给出恢复命令；恢复后流程正常。

**相关**：`scripts/commit.py`、[overview.md](overview.md) 已知限制

### 2026-09-29 | 工具链 | 对抗性复测：找出并修复 7 个漏洞

**改动**：

- `check_docs.py` 新增 `was_updated()`：只认新增 / 修改 / 重命名，**删除不再算"已更新"**
  （同时修正 DEVLOG 检查、模块文档同步、版本号检查三处）
- `CODE_PREFIXES` 补上 `plugins/`——此前改插件不要求写 DEVLOG
- `jsonschema` 缺失从"跳过并放行"改为**判失败**
- 新增 `scripts/setup.py`：一键启用 git 钩子
- `commit.py` 启动时自检 `core.hooksPath`，未启用则拒绝提交
- `README.md` 补"首次使用"；`docs/overview.md` 补"已知限制"

**原因**：对已建立的机制做对抗性复测，专门找绕过路径与边界情况，而不是重跑正常流程。

**根因（本轮暴露的 7 个问题）**：

| 漏洞 | 实测证据 |
| --- | --- |
| `git commit --no-verify` 完全绕过 | 提交成功，exit=0 |
| 删除 `DEVLOG.md` 被当作"已更新" | 目标报错未出现 |
| 删除 `VERSION` 被当作"已递增" | 目标报错未出现 |
| 删除模块文档被当作"已同步" | 目标报错未出现 |
| `plugins/` 不在检查范围 | 无 DEVLOG 报错 |
| **`core.hooksPath` 未配置 → 钩子完全不执行** | 违规提交成功，exit=0 |
| 未装 `jsonschema` → 契约校验静默失效 | 提示跳过且 exit=0 |

前四个**同源**：检查只判断"路径出现在暂存区"，没有判断"状态是新增还是删除"。
删除文件同样会让路径出现在暂存区——于是"**删掉文档**"反而满足了"更新文档"。

**影响面**：无契约变更。
此后未安装 `jsonschema` 会阻止提交；`plugins/` 下的改动需要写 DEVLOG。

**验证**：7 项逐条复测；`python scripts/setup.py` 可恢复被绕过的钩子配置。

**相关**：`scripts/check_docs.py`、`scripts/setup.py`、[overview.md](overview.md) §3.3

> **未修复的 1 项**：`--no-verify` 是 git 的设计，本地无法阻止。
> 缓解手段是远端 CI 或服务端钩子——待配置远端后补上。
>
> **过程失误（值得记下）**：复测脚本里用了 `git reset --hard` 恢复现场，
> 结果把**本轮尚未提交的全部修复**冲掉了（`git add` 过的新文件也一并被删），
> 只能重做一遍。教训：测试脚本要清理自己的痕迹，
> 但**绝不能用会丢弃工作区改动的命令**——应当先提交，再测试。

### 2026-09-29 | 工具链 | 修复提交脚本的自锁：预检与版本递增的顺序

**改动**：`check_docs.py` 新增 `--skip-version` 参数；`commit.py` 预检时传入它。

**原因**：第二次用 `commit.py` 提交时报 "VERSION 未在本提交中更新" 并中止——脚本把自己锁死了。

**根因**：`commit.py` 的顺序是"先预检 → 再递增版本"，而预检里包含"VERSION 必须已更新"这一条，
于是永远无法通过。第一次提交之所以没暴露，是因为那时 `VERSION` 是**新增文件**，
检查看到它就在暂存区里便放行了——**只验证了首次路径，漏掉了重复提交的路径**。
修法：预检跳过该项（此刻本就该还没改），真正的强制交给 `git commit` 触发的钩子——
那时版本号已经递增完毕。

**影响面**：无契约变更。

**验证**：连续用 `commit.py` 提交两次均成功；直接 `git commit` 仍被拒绝。

**相关**：`scripts/commit.py`、`scripts/check_docs.py`

### 2026-09-29 | 工具链 | 修复 subprocess 在 Windows 上的编码崩溃

**改动**：`scripts/commit.py` 与 `scripts/check_docs.py` 中所有
`subprocess.run(..., text=True)` 调用补上 `encoding="utf-8", errors="replace"`。

**原因**：第一次用 `commit.py` 提交时，stderr 出现 `UnicodeDecodeError: 'gbk' codec ...`，
但**提交仍然成功**，很容易被当成噪音忽略。

**根因**：Windows 上 `subprocess` 在 `text=True` 时按系统 locale（简中为 GBK）解码子进程输出，
而 git 与钩子输出的是 UTF-8，中文字节被按 GBK 解就失败。
**危险之处**：它发生在读取线程里，不影响主进程退出码——只看"提交成功"永远发现不了。
含中文路径的 `git diff --name-status` 会触发同样的问题。

**影响面**：无契约变更，仅修工具链编码问题。

**验证**：重新用 `commit.py` 提交，stderr 无异常；`git log` 中文提交信息正常显示。

**相关**：`scripts/commit.py`、`scripts/check_docs.py`

### 2026-09-29 | 工具链 | 引入版本号系统与规格化提交

**改动**：

- 新增 `VERSION`（应用版本，唯一版本源；基线 `0.1.0`）
- 新增 `scripts/commit.py`：检查 → 自动递增版本号 → 提交（可选 `--tag` / `--push`）
- 新增 `docs/versioning.md`：版本规则（两个版本号的区别、递增级别判定、提交信息格式、标签策略）
- `scripts/check_docs.py` 新增检查：`VERSION` 未随提交更新则拒绝提交
- `AGENTS.md`、`docs/README.md`、`docs/overview.md` 同步

**原因**：提交需要与代码状态一一对应。原先只有 commit hash——唯一、精确，
但人不可读、无顺序、也不含"改动大小"的信息。出问题时使用者无法用一句话说清他拿的是哪个版本。

**影响面**：无契约变更。
**此后必须用 `python scripts/commit.py -m "..."` 提交**；直接 `git commit` 会被拒绝（版本号未递增）。

**验证**：

- 版本号自动递增实测：`0.1.0 → 0.2.0`
- 违规提交（改了文件但 `VERSION` 未变）被钩子拒绝
- 显式覆盖 `--bump=minor`、`--tag`、`--push` 均可用

**相关**：[versioning.md](versioning.md)、[AGENTS.md](../AGENTS.md) 提交一节

### 2026-09-29 | 工具链 | 把"换 LLM 也能正常干活"变成机制

**改动**：

- 在 5 个模块目录放**就地 `AGENTS.md`**：`frontend/renderers/`、`backend/aggregate/`、
  `backend/filters/`、`backend/sources/`、`contract/`
- `scripts/check_docs.py` 增加**模块文档同步**检查（模块目录下增删文件 → 对应模块文档必须同批更新）
- 根 `AGENTS.md` 增加"这套规则怎么保证被遵守"一节；`docs/README.md`、`docs/overview.md` 同步
- 新增 `CLAUDE.md`（指向 `AGENTS.md`），兼容其它工具的入口约定
- `.gitignore` 忽略 `AGENTS.local.md` / `CLAUDE.local.md`（个人本地覆盖，不入库）

**原因**：换 LLM 或换会话时，规则可能根本没被读到，导致改动不写文档。
原机制只有"项目根 `AGENTS.md` + 钩子查 DEVLOG"两条，不足以防住这件事。

**根因**：任何依赖"AI 主动去读文档"的机制，换模型后必然衰减。
必须让规则**被自动注入**（不依赖主动性），并让违规**被物理拒绝**（不依赖配合）。

**影响面**：无契约变更。
提交时新增一项检查：模块目录下新增或删除文件时，该模块的开发文档必须同批更新。

**验证**：

- 从 DSH 源码确认默认配置：`projectRootMarkers = ['.git']`、
  `instructionFileCandidates = ['AGENTS.md', 'CLAUDE.md']`、`maxBytes = 65536`。
  项目根有 `.git`，故 `AGENTS.md` 会被**自动注入每个会话**；子目录 `AGENTS.md` 按需注入。
- 实测探针文件触发两条精确报错（DEVLOG 缺失、模块文档缺失），无误报
- 修正了一处设计冲突：就地 `AGENTS.md` 曾被误判为"模块能力变化"，
  已在过滤条件与 `IGNORED_SUFFIXES` 中排除

**相关**：[AGENTS.md](../AGENTS.md)、[README.md](README.md) 维护规则、`scripts/check_docs.py`

### 2026-09-29 | 工具链 | 建立"文档不会漏写"的三层强制机制

**改动**：新增 [AGENTS.md](../AGENTS.md)（会话自动加载的规则入口）、`.githooks/pre-commit`、
`scripts/check_docs.py`；配置 `core.hooksPath = .githooks`。
`docs/README.md` 的维护规则增加"规则由什么强制"一节；`docs/overview.md` 补充环境与提交流程。

**原因**：此前维护规则只是文档里的**文字约定**。换个会话后，AI 若没读到规则，等于规则不存在，
于是"改了代码不更新文档"必然发生。**约定无法自我执行**，需要机制兜住。

**根因**：把"应该做"写进文档，与"必须做"是两件事。前者靠自觉，后者要有工具。
本次补上的三层是：入口（AGENTS.md 被自动加载）→ 强制（钩子拒绝提交）→ 兜底（检查脚本可随时跑）。

**影响面**：无契约变更。**此后代码有改动却未更新 `docs/DEVLOG.md` 的提交会被拒绝**。
临时跳过用 `SKIP_DOC_CHECK=1`，必须在提交信息里说明理由。

**验证**：
- 全量检查通过：链接 172 处、5 个 JSON、4 份契约示例、10 份模块文档登记
- 实测"只改 `backend/` 代码、不更新 DEVLOG"的提交被拒绝（exit=1），提示可读
- 实测 `SKIP_DOC_CHECK=1` 可正常提交
- 修复了检查脚本在 Windows 控制台输出中文乱码的问题（stdout/stderr 重配置为 UTF-8）

**相关**：[AGENTS.md](../AGENTS.md)、[README.md](README.md) 维护规则、[overview.md](overview.md) §3.3

### 2026-09-29 | 文档 | 建立项目骨架与模块化文档体系

**改动**：建立分层目录（`docs/`、`contract/`、`backend/`、`frontend/`、`plugins/`、`scripts/`）；
新增文档地图 `docs/README.md`、模块地图 `docs/MODULES.md`、全局架构 `docs/ARCHITECTURE.md`、
数据契约 `docs/contract.md`、通信协议 `docs/protocol.md`、决策记录 `docs/DECISIONS.md`、本文件、`docs/roadmap.md`；
建立 `docs/modules/`（模块文档）与 `docs/guides/`（操作手册）。

**原因**：此前的需求以问答形式记录，内容虽全，但丢失对话上下文后无法快速定位
"要改的代码在哪、受什么规则约束"。需要一套**按模块组织、可被 AI 当作导航使用**的文档体系。

**影响面**：无代码影响（代码尚未建立）。决策内容从旧文档迁移而来，**未改变任何已定决策**。

**验证**：按 `docs/README.md` 的"我要做某件事，该读哪里"表逐条走一遍，每条都能定位到具体文档。

**相关**：[MODULES.md](MODULES.md)、[DECISIONS.md](DECISIONS.md)
