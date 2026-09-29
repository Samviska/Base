# 技术总览

> **接手项目时第一个读这个文件。** 一份读全：用什么技术、什么版本、环境怎么配、目录怎么组织、注意什么。
> 读完再去看 [README.md](README.md) 的文档地图。
>
> "为什么这么定"在 [DECISIONS.md](DECISIONS.md)，本文件只写结论。

---

## 1. 这个项目是什么

面向嵌入式传感器数据的**可扩展分析与绘图应用**：从各种日志提取数据 → 滤波 → 在画布上交互式绘图。

核心不是"画图"，而是**让 AI 能持续维护与扩展**：核心稳定、契约固定、能力靠插件增长。

---

## 2. 技术栈与版本

| 层 | 技术 | 版本 | 说明 |
| --- | --- | --- | --- |
| 后端语言 | **Python** | **3.11 起** | 3.11 起 CPython 有明显性能优化 |
| 前端框架 | **Vue 3** | 锁定 | **只用组合式 API**，不得混用 Vue 2 / 选项式写法 |
| 前端构建 | **Vite** | 锁定 | dev server 用于开发；build 只用于交付 |
| 前端语言 | **JavaScript + JSDoc** | — | 类型提示靠 JSDoc 注释，**不引入 TypeScript 编译** |
| 图形绘制 | **Canvas 2D** | 浏览器原生 | 渲染器**接口**不绑定绘图技术，可整块替换 |
| 前后端通信 | **WebSocket** | — | 单条长连接 + JSON 信封；HTTP 仅用于加载页面 |
| 数据存储（V1） | **JSON** | — | 接口按"按 x 范围读取"定义，可加格式 |
| 契约定义 | **JSON Schema** | draft 2020-12 | 语言中立的权威定义，放 `contract/schema/` |

### 明确禁止

| 禁止 | 原因 |
| --- | --- |
| 渲染器**接口**依赖 UI 框架 | 换框架时所有渲染插件（含第三方）作废 → [DECISIONS](DECISIONS.md) D3 |
| 用 SVG 承载大数据 | 每个点一个 DOM 节点，到万级就明显吃力 |
| 为显示流畅做抽样 | 会抹掉尖峰，而问题就在尖峰上 |
| 后端出现界面相关内容 | 违背分层 |
| 打包进入开发流程 | 开发循环必须是"改代码 → 运行 → 看结果" |
| 存储接口名里带格式 | 加格式时要改所有调用点 |
| 读写时丢弃契约未知字段 | 插件的扩展信息会静默消失 |
| 依赖版本用 `^` / `~` | 避免"某天它自己变了" |

---

## 3. 开发环境要求

### 3.1 必需工具

| 工具 | 版本 | 用途 |
| --- | --- | --- |
| **Python** | **3.11 或更高** | 后端运行 |
| **Node.js** | **18 或更高**（建议 20 LTS） | 前端 dev server 与构建。Vite 要求 18 以上 |
| **Git** | 较新版本即可 | 版本管理 |

浏览器：任一现代浏览器（需支持 ES Module 与 Canvas 2D）。

### 3.2 确认环境就绪

```powershell
python --version   # 期望 3.11 或更高
node --version     # 期望 v18 或更高
git --version
```

### 3.3 提交前的自动检查

提交时会自动运行 `scripts/check_docs.py --staged`（由 `.githooks/pre-commit` 调用）：

| 检查项 | 说明 |
| --- | --- |
| 文档链接 | `docs/` 内的相对链接是否有效 |
| JSON 语法 | `contract/` 下所有 JSON |
| **契约示例** | 用 schema 校验 `contract/examples/`；`invalid-` 开头的必须被拒绝 |
| 模块登记 | `docs/modules/` 下的文档必须已在 `docs/MODULES.md` 登记 |
| **文档更新** | 代码有改动时，`docs/DEVLOG.md` 必须同时更新 |
| **模块文档同步** | 某模块目录下**新增或删除**文件时，该模块的 `docs/modules/*.md` 必须同时更新 |
| **版本号** | 每次提交必须递增 `VERSION` |

**依赖 `jsonschema`。缺失时会直接判失败**（不允许静默跳过——静默跳过的校验等于没有校验）：

```powershell
pip install jsonschema
```

临时跳过：`SKIP_DOC_CHECK=1 git commit ...`，并在提交信息里说明理由。

#### 已知限制（必须知道）

| 限制 | 说明 | 缓解 |
| --- | --- | --- |
| `git commit --no-verify` 可绕过本地钩子 | git 的设计，本地无法阻止 | **已由 GitHub Actions 覆盖**：`.github/workflows/check.yml` 跑同一套脚本 |
| **clone 后钩子默认不生效** | `core.hooksPath` 是本地配置，不随仓库分发 | **clone 后必须跑 `python scripts/setup.py`** |
| CI 只检查**最后一个提交**的过程约束 | 一次推送多个提交时，中间提交可能漏检 | 一次推送尽量少提交；后续可扩展为 range 检查 |
| 合并提交不展开差异 | `--commit` 模式下过程约束会跳过 | 避免用合并提交推送 |
| 检查只管形式，不管内容 | 能拦住"没写文档"，拦不住"文档写得含糊" | 定期做 S3 验收：让全新会话只读文档做一件小事 |

### 3.4 首次搭建

```powershell
python scripts/setup.py
```

一条命令做三件事：建 `.venv` 虚拟环境 → 按 `requirements.txt` 装依赖 → 启用 git 钩子。

**跑完自检**：

```powershell
.venv\Scripts\python.exe scripts\check_docs.py     # 应输出「文档与契约检查通过」
```

> 钩子必须启用，否则所有提交前检查都会静默失效（见 §3.3 的已知限制）。

### 3.5 依赖管理

| 项 | 规定 |
| --- | --- |
| 依赖清单 | `requirements.txt`，**版本写死**（`==`） |
| 安装位置 | 项目自己的 `.venv`，**不装进全局环境** |
| 只列直接依赖 | 传递依赖由 pip 自动解析。依赖少，足够可控 |
| 不引入 uv / poetry | 依赖超过 10 个、或需要区分开发依赖时再评估 |

**为什么必须用虚拟环境**：全局环境里已经有大量与本项目无关的包，
混在一起既容易版本冲突，打包 exe 时也容易带上无关库。

**解释器路径**：Windows 是 `.venv\Scripts\python.exe`，Linux / macOS 是 `.venv/bin/python`。
**不要"激活"虚拟环境**——PowerShell 默认禁止执行 `Activate.ps1`，直接指定解释器更可靠，
脚本里也好写。`pre-commit` 钩子与 CI 都遵循这个规则。

### 3.6 换工具 / 换模型时

规则本身与工具无关；"规则怎么被送到模型面前"与工具有关。

| 情况 | 会发生什么 |
| --- | --- |
| 在**项目根目录**打开会话 | 根 `AGENTS.md` **自动注入**（DSH、Claude Code 等遵循该约定） |
| 碰到某个模块目录 | 该目录下的 `AGENTS.md` **按需注入**就地规则 |
| 工具不支持 `AGENTS.md` 约定 | 第一条消息让它先读 `AGENTS.md`；**提交时钩子仍会拦住违规** |
| 任何情况 | **pre-commit 与模型无关**——代码改了不更新文档，就是提交不了 |

**唯一需要人工保证的事：会话要在项目根目录打开。**
项目根靠 `.git` 识别；在父目录开会话，它不会被识别为项目根，也就读不到根 `AGENTS.md`。

---

## 4. 目录架构

```
Base/
├── README.md              项目入口
├── AGENTS.md              **AI 会话自动加载的规则入口**（每次动手前必读）
├── VERSION                **应用版本号**（唯一版本源，脚本自动维护）
├── LICENSE                MIT
├── .githooks/             git 钩子（提交前强制检查文档与版本号）
├── .github/workflows/     CI（推送后跑同一套检查，堵住 --no-verify 绕过）
├── docs/                  全部文档（入口是 docs/README.md）
│   ├── overview.md        本文件
│   ├── README.md          文档地图
│   ├── MODULES.md         模块地图
│   ├── ARCHITECTURE.md    分层与约束
│   ├── contract.md        数据契约
│   ├── protocol.md        通信规则
│   ├── messages.md        消息清单
│   ├── DECISIONS.md       决策与理由
│   ├── DEVLOG.md          开发日志
│   ├── versioning.md      版本号规则
│   ├── roadmap.md         范围与未实现功能
│   ├── modules/           每个模块一份开发文档
│   └── guides/            操作手册
│
├── contract/              契约的**语言中立**权威定义
│   ├── schema/            JSON Schema
│   ├── examples/          示例数据（含故意非法的样例）
│   └── tests/             校验用例
│
├── backend/               Python 后端
│   ├── core/              编排、会话、缓存失效
│   ├── contract/          契约实现与校验器
│   ├── sources/           数据源插件
│   ├── filters/           滤波插件
│   ├── storage/           存储实现
│   ├── aggregate/         聚合（视口裁剪 + 像素列 min/max）
│   ├── server/            WebSocket 服务
│   └── tests/
│
├── frontend/              Vue 前端
│   ├── ui/                面板、控件、对话框
│   ├── api/               通信客户端
│   ├── renderers/         渲染器
│   └── tests/
│
├── plugins/               外部插件（与内置分开）
│   ├── sources/  filters/  renderers/
│
└── scripts/               启动与打包
```

模块与文档的对应关系，见 [MODULES.md](MODULES.md)。

---

## 5. 注意事项（最容易踩的）

| 注意事项 | 后果 |
| --- | --- |
| **不要在 `mousemove` / `wheel` 里直接发数据请求** | 请求风暴，交互反而更卡。必须按帧节流 + 代次作废 |
| **Canvas 不是响应式的** | 改了数据必须**显式重绘**，否则画面与状态不一致 |
| **渲染器接口不得引用 Vue** | 一旦绑框架，"渲染器可整块替换"就作废 |
| **滤波必须在聚合之前，且都拿全量数据** | 顺序颠倒会让滤波结果**直接算错** |
| **前端永远拿不到全量数据** | 跨进程接口只暴露"按视口 + 分辨率请求"，这是靠结构保证的，不是靠约定 |
| **不要用 `0` / `-1` 表示缺失值** | 必须用 `null`，否则波形出现假数据 |
| **时间精度要声明** | 微秒当毫秒会让波形压缩 1000 倍 |
| **时钟跳变必须显式处理** | 否则产生乱序 x 轴，整张图失去意义 |
| **插件异常不得让应用崩溃** | 必须捕获、记录并呈现 |
| **交付不是"打好的包"** | 默认交付形态是"能直接跑起来"；打包只在交付环节做 |

---

## 6. 开发与交付流程

| 阶段 | 要求 |
| --- | --- |
| **开发** | **改完即见**：前端用 dev server，后端直接跑源码。不需要手动构建或打包 |
| **提交** | 用 `python scripts/commit.py -m "描述"`：自动检查、递增版本号并提交。**直接 `git commit` 会被钩子拒绝**（版本号没递增） |
| **交付** | 一条命令产出单个 exe。**打包后插件机制必须仍然可用**（一票否决项） |

---

## 7. 尚未确定

| 项 | 建议 | 影响 |
| --- | --- | --- |
| 代码格式化 / 静态检查 | Python 侧先只用 ruff；前端暂不引入 lint | 协作一致性，可后补 |
| 测试框架 | Python 用 pytest；前端用 Vitest | "插件自检方式"的实现 |

> 依赖管理已定，见 §3.5。上表未定项**不阻塞文档与架构工作**。

---

## 8. 相关文档

- [README.md](README.md) —— 文档地图：我要做某件事该读哪里
- [MODULES.md](MODULES.md) —— 模块地图：代码在哪、能不能随便改
- [ARCHITECTURE.md](ARCHITECTURE.md) —— 分层、数据流、显示策略、UI 约束
- [contract.md](contract.md) —— 数据契约
- [messages.md](messages.md) —— 前后端消息清单
- [DECISIONS.md](DECISIONS.md) —— 为什么这么定
