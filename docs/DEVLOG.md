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

### 2026-09-30 | 修复 | 聚合显示在"每列一两个点"时像一片毛刺

**现象**：某份真实日志在某个缩放级别下，波形变成密集竖线段，看不出形状。

**诊断**（先查数据，再怀疑渲染）：解析该日志——相邻点差中位数 456、99% 分位 1778、最大 2966，
而那个视口的纵轴跨度约 17k，竖线长度 3%~17%，与截图完全吻合。
**渲染没有算错**：视口内约 1600 个点、画布约 1258 列，每列只有一两个点，
"每列一条 min→max 竖线"必然长这样。这是"不丢极值"的固有外观，不是 bug——但确实没法看。

**改动**：聚合显示时除了竖线段，再画一条**列中点连线**：极值仍由竖线表达
（尖峰照样看得见），中点线把趋势接起来，视觉上仍是连续波形。

**影响面**：只改渲染器的绘制路径；契约、消息清单、渲染器接口均未变。
代价是多遍历一遍列（列数 ≤ 画布宽度）。

**验证**：`npm test` → 37 条通过；`npm run e2e` → **28 项通过**。
内测新增【8】临界区步骤：放大到约 1300 个点（仍是聚合显示）并截图
`_local/e2e-05-临界放大.png` —— 波形连续、尖峰清晰。
合成日志也加了确定性抖动，贴近真实设备数据的形态（纯正弦看不出这个问题）。

**相关**：[modules/renderer.md](modules/renderer.md) §3.1

### 2026-09-30 | 前端 | 测量光标：多个光标 + 吸附数据点 + 右栏读数（新增功能）

**改动**：

- 新增 `frontend/renderers/cursor.js`：`snapToSeries(list, name, x)` —— 吸附规则的**唯一实现**，
  返回 `{ series, index, x, y, ymin, ymax, aggregated }`
- 渲染器新增 `setCursors(list)` 与 `cursor-move` 事件：画光标线（虚线 + 编号标签 + 交点圆点）、
  命中后拖动、**拖动时吸附到最近的数据点**并把读数报给界面；视口外的光标不画也不参与命中
- 渲染器接口必需方法 8 → **9 个**（含 `setCursors`）；`VIEW_EVENTS` 增加 `cursor-move`
- 新增 `frontend/ui/components/CursorPanel.vue`：右侧面板显示每个光标的 X/Y 与相邻两个的 ΔX/ΔY
- 新增用例 `frontend/tests/cursor.test.js`（6 条）+ 渲染器交互用例（拖动吸附、视口外光标不挡滚轮）
- 内测脚本新增两步：光标添加/拖动/读数、聚合模式的说明；断言里加了一条
  **"拖动光标不应平移画布"**（判断是否真的抓住了线）

**原因**：使用者需要量测两点之间的差值——示波器/Origin 里的"光标"功能。

**影响面**：契约与消息清单**未变**（纯前端状态，不发消息）。渲染器**接口新增一个必需方法**，
故按 `minor` 递增。

**内测发现并修掉的两处**（都不在算法里）：

1. 两个光标默认落在同一位置，差值恒为 0，等于没给信息 → 添加时依次错开
2. 内测脚本按"容器中心"去抓光标线，而光标在**绘图区中心**（差 22px）→ 没抓住、变成平移画布，
   而"读数变了"这条断言**假通过**。修法：边距由渲染器导出（`LAYOUT`）供脚本精确计算，
   并补一条"拖动光标不应平移画布"的断言把这层意思钉死

**验证**：`npm test` → 37 条通过；`npm run e2e` → **27 项全部通过**
（含"确实抓住了线"、拖动后读数 4994.540 → 8000.192、ΔX 4999.500 / ΔY 217518 非零）；
截图 `_local/e2e-06-光标.png` 人工复核：两条光标线、交点、右栏读数与差值、聚合说明均正确。

**相关**：[modules/renderer.md](modules/renderer.md) §3.3、[modules/ui-shell.md](modules/ui-shell.md) §5

### 2026-09-30 | 自测 | 引入真实浏览器内测（Playwright + 系统 Edge）

**改动**：

- 新增 `frontend/tests-e2e/run.mjs`（`npm run e2e`）：真实浏览器把"选日志 → 出图 →
  缩放 / 拖拽 / 双击 / 全览 / 勾曲线"整条路走一遍，17 项断言 + 5 张截图（`_local/e2e-*.png`）
- 关键控件加 `data-testid`（路径、插件下拉、参数、打开、全览、状态栏各项、画布）
- 状态栏把点数拆成**数据总量**与**本次绘制**两项；状态栏/文案相应调整
- 刻度数字紧凑化（`882134` → `882k`）；横轴标题改左对齐、首尾刻度贴边（不再重叠）；
  底部边距 30 → 44 给标题让位
- `frontend/README.md` 补"怎么跑内测"与"跑前先重启 dev server"

**原因**：使用者要求"自行内测，不要依赖他帮我测"。此前三个 bug（滚轮静默失效、
拖拽被中断、双击回不到全览）**全都是在浏览器层面才暴露的**，而当时这里只有假 DOM 用例。

**内测发现并修掉的问题**：

1. 状态栏"点数"含义不清——聚合时它显示的是像素列数，我自己都被绕了一次，故拆成两项
2. 横轴标题与最后一个刻度标签叠在一起（`时间（ms）` 压在 `+40.0s` 上）
3. 纵轴刻度六位数难读
4. **Vite HMR 会累积状态**，页面可能停留在旧代码上（表现就是"改了没效果"）——
   跑内测前重启 dev server 是可靠做法，已写进脚本与 README

**影响面**：契约、消息清单、渲染器接口均未变。新增开发依赖 `playwright`（驱动系统 Edge，
**不下载浏览器**）；新增 `npm run e2e`。

**验证**：`npm test` → 29 条通过；`npm run e2e` → **17 项全部通过**（含双击复位、
"轴带缩放不动横轴"、拖出画布不中断、放大后回到原始点、勾掉曲线少一条）；
截图人工复核：正弦波形连续、20 s 处的尖峰清晰可见、轴标题与单位正确。

**相关**：[frontend/README.md](../frontend/README.md)、[modules/renderer.md](modules/renderer.md) §3.1、
[modules/ui-shell.md](modules/ui-shell.md) §5

### 2026-09-30 | 修复 | 双击回不到全览（接线顺序错误）

**现象**：导入文件时能看到全部数据，但"自适应 / 双击"之后只剩下**一部分**——
横轴没回到完整范围，只有纵轴恢复了。

**根因**：`App.vue` 里先把 `datasetId` 加一（触发 ChartView 重建）、**之后**才设置 `fullRange`，
而渲染器只在 `onMounted` 时读一次 `options.fullRange`。于是它拿到的永远是 `null`，
`resetView()` 判定"横轴已在全览" → 只重置纵轴，横轴留在用户缩放后的那一段。
**全览范围从来没有进到渲染器里。**

**改动**：

- `App.vue`：`fullRange` 的赋值挪到重建渲染器**之前**，并加注释说明顺序不能反
- 把"重置视图"从双击内部**显式化成接口方法** `resetView()`——双击与「全览」按钮走同一条路径，
  行为不会分叉（此前只有"双击"这一个隐形入口，使用者根本不知道）
- 界面右上角新增「**全览**」按钮
- `frontend/renderers/interface.js` 必需方法从 7 个增到 8 个（含 `resetView`）；renderer.md 同步
- 用例 +1（直接调用 `resetView`）

**影响面**：渲染器**接口新增一个必需方法**，第三方渲染器需实现，否则 `assertRenderer` 会拦下；
故本次按 `minor` 递增（接口能力变化，不是修修补补）。契约与消息清单未动。

**教训**：这个 bug 不在算法，而在**组件与渲染器的接线顺序**——纯函数与渲染器用例都覆盖不到。
本项目的**组件级测试仍是空白**（需引入 Vue 测试工具 + jsdom），列为下一步候选。

**验证**：`npm test` → 29 条通过（27 通过 + 2 条需真后端跳过）；`npm run build` 通过。

**相关**：[modules/renderer.md](modules/renderer.md) §3.2

### 2026-09-30 | 修复 | 拖拽被中断、双击重置的适用范围太窄

**现象**：① 拖拽平移"消失"了（拖快一点就中断）；② 双击只有"手动缩放过纵轴"才生效，
只拖拽过横轴时双击毫无反应。

**根因**：

1. `pointerleave` 监听在指针离开画布时直接清空拖拽状态——而指针捕获本来就在工作，
   拖拽不该因为出界而中断。
2. 双击的处理条件是 `state.yView !== null`，只覆盖了"纵轴被缩放"这一种偏离，
   漏掉了"横轴被平移或缩放"的情况。想看全局却发现回不去，只能刷新页面。

**改动**：

- 去掉 `pointerleave` 监听：拖拽只由 `pointerup` / `pointercancel` 结束
- 双击改为**重置视图**：纵轴回自动适应 + 横轴回**数据完整范围**；
  只有当"纵轴自动 **且** 横轴已在完整范围"时才不动作
- 数据完整范围经 `options.fullRange` 由上层传入（渲染器拿不到全量数据，见分层纪律）
- 新增"在轴带上拖拽平移该轴"，与轴带滚轮缩放配对；光标相应变化（拖拽时 `grabbing`）
- 交互用例 +5：拖拽平移、出界不中断、纵轴带拖拽、双击重置、全览时双击不动作

**影响面**：渲染器 `options` 新增可选字段 `fullRange`；接口的 7 个方法一个没变。
契约与消息清单未动。

**验证**：`npm test` → 28 条通过（26 通过 + 2 条需真后端跳过）；`npm run build` 通过。
其中"纵轴带拖拽"用**像素跨度不变 + 中心位移**来断言（平移不该改变跨度，
但浮点会有 1e-14 级误差，故用容差比较）。

**相关**：[modules/renderer.md](modules/renderer.md) §3.2

### 2026-09-30 | 修复 | 滚轮缩放静默失效（NaN 比较，无任何报错）

**现象**：鼠标滚轮完全没反应；在左侧纵轴带上滚轮也没用；双击恢复自动适应同样无效。

**根因**：`zoomRange(range, ...)` 按 `{lo, hi}` 取值，而横轴分支把视口 `{x0, x1}` 原样传了进去。
`anchor - (anchor - undefined) * factor` 得到 `NaN`，而 `NaN > minSpan` **恒为 false**，
函数于是返回 `null`、调用方按"缩到极限了"静默忽略——**不抛错、不警告、什么也不发生**。
纵轴那一支本身没问题，但纵轴从未被手动缩放过（`yView` 一直是 `null`），
所以"双击恢复自动"也就无从生效。三条现象是同一个根因。

**修复**：

- 横轴分支显式转字段：`zoomRange({ lo: view.x0, hi: view.x1 }, ...)`
- `zoomRange` 参数不合法时**抛 `TypeError`**，不再用 `null` 把错误吞掉
- 新增 `frontend/tests/renderer-interaction.test.js`（9 条）：用最小假 DOM 把 mount 之后的
  **事件 → 状态 → 重绘**整条链跑一遍——绘图区滚轮、横轴带、纵轴带、Shift、双击复位、
  光标提示、缩到极限。此前只有纯函数用例，结果是"全绿但交互是死的"

**教训**（两条都值得记）：

1. **算法正确 ≠ 接上了**。纯函数用例覆盖不到"事件有没有接到、状态有没有传到绘制"。
2. 假 `requestAnimationFrame` 必须保持**异步语义**：同步执行会让 `requestDraw` 里的
   `frameId` 赋值落在回调之后，`frameId` 永远非 0、后续重绘全被挡掉——
   测试环境与真实环境不一致，比没有测试更危险。

**影响面**：只改渲染器内部与用例；契约、消息清单、渲染器接口（7 个方法）均未变。

**验证**：`npm test` → 23 条通过（21 通过 + 2 条需真后端的跳过），其中纵轴缩放的
"画面被拉伸"通过**按颜色筛掉网格线**后测量数据折线的像素跨度来断言；
`npm run build` 通过。

**相关**：[modules/renderer.md](modules/renderer.md) §3.2、[guides/ai-coding-rules.md](guides/ai-coding-rules.md)

### 2026-09-30 | 交互 | 文件浏览改为可去整块硬盘

**改动**：

- `backend/core/browse.py`：响应新增 `roots`（Windows 各盘符 / 类 Unix 的 `/`）与
  `shortcuts`（主目录、桌面、文档、下载，存在才给）；相对路径解析不到时退回主目录
- `frontend/ui/components/FileBrowser.vue`：加可编辑的路径输入框（粘贴绝对路径回车即前往）、
  盘符与常用目录快捷按钮；**打开时只有绝对路径才当起点**

**原因**：使用者反馈"只能在项目目录里选文件"。**根因**：弹窗打开时把界面里的
`contract/examples/example-basic.json` 这种**相对路径**当成了浏览起点，后端按工作目录解析，
于是浏览被锁在项目里；同时弹窗没有盘符入口，出不去。

**影响面**：契约**结构未变**（`M18` 是上一次提交新增的消息，本次只补两个字段并更新 messages.md）；
渲染器接口未动。

**验证**：后端 117 条用例通过（新增 `roots`/`shortcuts`、相对路径回退两条）；
`npm test` 14 条通过；`npm run build` 通过。实测 `browse` 能列出 `C:\` 与桌面上的日志目录。

**相关**：[messages.md](messages.md) M18、[modules/core.md](modules/core.md) §3.3

### 2026-09-30 | 交互 | 按轴缩放、文件浏览弹窗、术语改直白

**改动**：

- `frontend/renderers/builtin/line.js`：滚轮**按鼠标所在的轴**缩放——
  左侧纵轴带 → 纵轴、底部横轴带 → 横轴、绘图区内 → 横轴、`Shift` → 纵轴；
  一律**以鼠标位置为锚点**；双击恢复纵轴自动适应；光标形状提示当前能缩放哪条轴；
  纵轴手动缩放时画布右上角给出提示。导出纯函数 `zoomRange` 供测试
- **新增消息 M18 `browse`**（实现 `backend/core/browse.py`）：列目录。
  浏览器拿不到本机路径，而 `open_file` 要的正是路径，所以浏览只能由后端提供；
  只列名字与大小，**不读内容**
- 新增 `frontend/ui/components/FileBrowser.vue`：文件浏览弹窗（上一级、主目录、
  单击进目录、双击选中并确认、显示文件大小、条目上限提示）；`FilePanel` 加「浏览…」按钮
- 术语按使用者的话改直白：「数据源」→「日志格式」、「序列」→「曲线」，
  并补一句"一条曲线 = 数据里的一组 x/y"

**原因**：使用者反馈两处界面看不懂（"数据源""序列"到底是什么），
以及滚轮只能缩放横轴、无法对指定轴缩放。轴缩放的做法参考了行情/示波类软件的通行惯例
（价格轴可单独滚动缩放、按轴缩放 + 光标提示）。

**影响面**：契约**结构未变**；**新增一条消息** M18，已在 [messages.md](messages.md) 登记，
[acceptance.md](acceptance.md) §1 的 `M` 前缀范围同步改为 M1–M18。
渲染器接口的 7 个方法一个没变（第三方渲染器仍合规）。

**验证**：后端 `115 条`用例通过（新增 6 条列目录用例，含"传文件退到所在目录"与排序）；
前端 `14 条`通过（新增 `zoomRange` 锚点缩放断言：锚点不动、边缘拉长、缩到极限返回 null）；
`npm run build` 通过。浏览器里的手感（光标、锚点、双击复位）待确认。

**相关**：[modules/renderer.md](modules/renderer.md) §3.2、[messages.md](messages.md) M18、
[modules/ui-shell.md](modules/ui-shell.md) §5

### 2026-09-30 | 前端 | 插件选择与参数控件（按声明生成）

**改动**：

- `frontend/ui/components/FilePanel.vue`：增加数据源插件下拉与**参数控件**——控件种类由
  参数声明的 `type` 决定（字符串 → 文本框、int/float → 数字框、enum → 下拉），
  数值型按声明转成数字（不转的话后端会判为非法请求）
- `frontend/ui/App.vue`：连接后拉 `list_plugins`，取数据源插件与 `warnings`；
  切换插件时按声明写回默认值；`open_file` 带上 `source_plugin` 与 `options`
- `frontend/ui/components/StatusBar.vue`：显示坏插件警告（S4）
- 文案表补「数据源」「参数」两条；`docs/modules/ui-shell.md` §5 补"界面元素 ← 声明"的来源表

**原因**：后端插件机制已就绪，但界面只会发 `path`（默认走 `contract-json`），
真实日志在界面上依然打不开——差的就是这一步。

**影响面**：契约**未变**；用到的都是已登记的字段（M3 的 `source_plugin` / `options`、
M2 的 `params` / `warnings`）。界面里**没有任何插件专名**：下拉项与控件全部由后端声明生成，
所以新增一个插件时本模块改动应为 0 行（U2 的验收方法）。

**验证**：

- `npm test` → 13 条通过（含 2 条连真后端的联通用例）
- `npm run build` → 通过
- 端到端（真服务 + 前端通信层）：插件下拉列出 `contract-json` 与 `jp18-ecg`；
  用 `jp18-ecg` + `sample_rate: 500` 打开 655 KB 的真实日志 → **67160 点**、横轴 `time/ms`、
  `x_range [0, 134318]`；随后全览 `query_range` → 1920 个像素列
- 浏览器里的最终视觉效果待确认

**相关**：[modules/ui-shell.md](modules/ui-shell.md) §5、[messages.md](messages.md) M2 / M3

### 2026-09-30 | 前端 | 渲染器按轴描述显示坐标轴（数据自描述落地）

**改动**：

- `frontend/renderers/builtin/line.js`：新增轴标题与纵轴单位显示；刻度按轴描述格式化
  （导出 `formatTick`）——`kind: time` + `tick_format: offset_seconds` 显示 `+12.5s`，
  `kind: sequence` 显示整数；横轴描述取 `options.axes`、纵轴单位取新增的 `options.units`
- `frontend/ui/ChartView.vue`、`App.vue`：把 M3 摘要里的 `axis` 与 `unit` 传给渲染器
- `docs/modules/renderer.md` 补 §3.1「轴描述 → 界面显示」映射表
- 用例：`frontend/tests/renderer-interface.test.js` 增加刻度格式化断言

**原因**：用户提出"通过读取 JSON 的特征来知道横轴纵轴该显示什么，我们提供标准"——
这正是契约 §4.2 轴描述那一层的用途。此前渲染器把刻度画成裸数字，轴名与单位都看不到。

**影响面**：契约**未变**；渲染器 `options` 新增可选字段 `units`，**渲染器接口的 7 个方法一个没变**
（第三方渲染器仍合规）。`categorical` 轴的刻度标签仍显示不出来——M6 的响应只带索引不带轴数据，
已记入 renderer.md 坑表，属第 6 批（柱状图）。

**验证**：`npm test` → 13 条通过（含刻度格式化 6 个断言）；`npm run build` → 通过。
浏览器里的视觉效果待确认。

**相关**：[modules/renderer.md](modules/renderer.md) §3.1、[contract.md](contract.md) §4.2

### 2026-09-30 | 数据源 | 插件机制落地 + JP18 心电日志解析（第 2 批·上）

**改动**：

- 新增 `backend/sources/`：注册表（`registry.py`）+ 内置插件 `contract_json.py`
  （原 `backend/core/source.py` 的过渡实现转正）。**目录即插件**：`plugins/sources/<名字>/`
  放 `manifest.json` + 入口模块，服务启动时扫描注册；坏插件只记警告，不影响启动
- 新增 `plugins/sources/jp18/`：**真实设备日志**（十六进制文本）的解析插件，含格式说明 README
- `backend/core/dispatch.py`：`open_file` 改调插件注册表；异常按 `FILE_NOT_FOUND` /
  `PLUGIN_FAILED` / `CONTRACT_VIOLATION` 映射；插件输出**兜底再校验一次**；
  `list_plugins` 增加数据源插件与 `warnings`（坏插件提示，S4）
- 用例 `backend/tests/test_sources.py`（17 个：注册表、坏插件隔离、JP18 解析、可复现性）
- 删除 `backend/core/source.py`；`.gitignore` 忽略 `_intermediate/`（临时脚本与输出不入库）
- 文档：`source.md`、`core.md`、`messages.md` M2、`guides/add-source-plugin.md`（待建 → 可执行）

**JP18 格式结论**（用真实日志反推，单独记下来免得下次再猜）：

| 段 | 长度 | 说明 |
| --- | --- | --- |
| 包头 | 1 字节 | 固定 `0x88` |
| 样本 | 66 组 × 3 字节 | 大端**有符号 24 位**（即"3 字节合成有符号 32 位整型"） |
| 填充 | 视情况 | 样本不足 66 组时用 `80 80 80` 组补齐 |
| 末尾 | 4 字节 | 不解析 |

子包固定 **203 字节**（与 1624 = 8 × 203 的读取缓冲对上）。判定依据：320 个子包**包头零失配**，
且 320×66 − 1120 组填充 = **正好 20000 个样本**——不是整数就说明切分错位。
**踩过的坑**：不能靠"搜索 0x88"找包边界，数据里平均每 200 字节就有一个 0x88，必须按固定包长切分再校验首字节。

**原因**：kickoff §五 第 2 批。用户提供真实日志与格式说明后，"第 2 批是插件形态、
可以后做"的判断得到验证：插件机制落地后，接入一类新日志只新增 `plugins/sources/<名字>/`。

**影响面**：契约**结构未变**（`schema_version` 仍 `1.0`），无需迁移。
`messages.md` M2 的响应新增**可选字段** `warnings`：不认识的客户端忽略即可，不需迁移。
`backend/core/source.py` 被删除，职责由内置插件 `contract-json` 承担——**行为不变**
（不指定 `source_plugin` 时仍是"直接读契约 JSON"）。
存储实现（第 2 批·下）与前端"选插件 + 填参数"界面尚未做，真实日志目前要走命令行或改前端才用得上。

**验证**：

- `.venv\Scripts\python.exe -m unittest discover -s backend/tests -t . -v` → 109 个用例通过
- 端到端（真服务 + 真客户端 + 用户提供的日志文件）：
  `list_plugins` → `contract-json` / `jp18-ecg` / `moving-average`，`warnings` 为空；
  `open_file` 指定 `jp18-ecg`、`sample_rate: 250` → 20000 点、轴 `time`/`ms`/`origin=start`、
  `x_range [0, 79996]`、`notes` 记录"跳过 1120 组 80 80 80 填充"，耗时 360 ms；
  随后 `query_range` 全览 → 1920 个像素列、10 ms
- 坏插件三种情形（入口抛异常、缺 manifest、入口文件不存在）都只产生警告，服务照常启动

**相关**：[guides/kickoff.md](guides/kickoff.md) §五 第 2 批、[modules/source.md](modules/source.md)、
[guides/add-source-plugin.md](guides/add-source-plugin.md)、`plugins/sources/jp18/README.md`

### 2026-09-30 | 前端 | 最小闭环：Vue 3 + Vite、按帧节流、Canvas 折线图（第 5 批）

**改动**：

- 新增前端工程：`frontend/package.json`、`vite.config.js`、`index.html`。
  Vite 的 root 就是 `frontend/`，目录按业务用途分（`ui/` `api/` `renderers/`），不套 `src/`
- `frontend/api/client.js`：建连、按 `id` 配对响应、事件分发；断线时**让在途请求全部失败**，
  界面不会停在加载中；重连是手动的（自动重连策略仍未定，C4）
- `frontend/api/viewport-loader.js`：**按帧节流 + 代次作废**（protocol.md §4 的硬规则落点）
- `frontend/renderers/`：接口约定 + 内置折线图（Canvas 2D）。聚合时画像素列竖线段，
  未聚合时画折线并让缺失值断线；缩放/平移交互；轴类型不认识或对数轴未实现时**降级并在画布上标注**
- `frontend/ui/`：`App.vue` + FilePanel / ChartView / StatusBar 三个组件、文案表、CSS 变量
- 用例 `frontend/tests/`：10 条常规（Node 内置 test runner，含节流与代次作废）
  + 2 条真后端联通用例（默认跳过，设 `BACKEND_URL` 后才跑）
- 文档：`api-client.md`、`renderer.md`、`ui-shell.md`、`frontend/README.md`、
  `guides/ai-coding-rules.md`（两处"必须给示例代码"已就位）、`protocol.md` §4、根 `README.md`

**原因**：kickoff §五 第 5 批——看到图。此前所有能力只存在于后端与测试里。

**影响面**：契约**未变**（`schema_version` 仍 `1.0`），后端代码**零改动**
（U2 的验收方法：新增界面不应碰核心——本批确实一行没碰）。
新增前端依赖 `vue@3.5.43`、`vite@8.3.1`、`@vitejs/plugin-vue@6.0.9`，版本写死、不用 `^`/`~`。
渲染器事件 payload 定为 `{x0, x1}`（zoom / pan），目标分辨率由 UI 按画布宽度提供——已写进 renderer.md。
标注（`mark-add` / `mark-remove`）与柱状图仍待第 6 批。

**验证**：

- `npm test` → 12 条通过；其中两条连真后端，字段级核对 `hello` / `open_file` / `query_range`
  与错误码（`FILE_NOT_FOUND`、`CONTRACT_VIOLATION` 且带 `detail.path`）
- `npm run build` → 24 个模块编译通过（190 ms）
- dev server `http://127.0.0.1:5173/` 返回 200，`/ui/App.vue` 编译通过（36 KB）
- **待人工确认**：浏览器里打开该地址、选 `contract/examples/example-basic.json`，
  确认波形、缩放平移与"当前为聚合显示"标注（渲染结果无法在无浏览器环境自动断言）

**相关**：[guides/kickoff.md](guides/kickoff.md) §五 第 5 批、[modules/api-client.md](modules/api-client.md)、
[modules/renderer.md](modules/renderer.md)、[modules/ui-shell.md](modules/ui-shell.md)、
[protocol.md](protocol.md) §4

### 2026-09-30 | 核心与通信 | WebSocket 服务与命令分发落地（第 4 批）

**改动**：

- 新增 `backend/core/`：`session.py`（会话与三层缓存）、`dispatch.py`（消息 → 响应）、
  `errors.py`（错误码集中定义）、`source.py`（**过渡**数据源入口，直接读契约 JSON）
- 新增 `backend/server/`：`app.py`（端点、信封、`hello` 事件）、`__main__.py`（启动入口）
- 新增用例 `backend/tests/test_core.py`（28 个）与 `test_server.py`（6 个：起真服务 + 真客户端）
- `requirements.txt` 增加 `websockets==17.1`——标准库没有 WebSocket 服务端，
  手写帧解析与掩码的代价远高于多一个依赖
- 同步 `docs/modules/core.md`、`docs/modules/server.md`、`docs/protocol.md` §6、
  `README.md`（补"跑起来"与当前状态）、`docs/modules/filter.md`（补浮点残差一行）

**原因**：kickoff §五 第 4 批。数据源与存储（第 2 批）是插件形态、按用户要求搁置，
因此核心先接一个**过渡入口**直接读契约 JSON；插件机制就绪后删掉 `source.py`、
改为调插件注册表，命令层的请求与响应形状不变。

**影响面**：契约**结构未变**，`schema_version` 仍为 `1.0`，**无需迁移**。
新增运行依赖 `websockets`（`Requires-Python >=3.11`，与项目下限一致，CI 的 3.11 可装）。
已实现 `list_plugins`/`open_file`/`close_source`/`list_storage_formats`/`query_range`/
`get_filter_chain`/`set_filter_chain`；标注（M9–M12）与会话（M13、M14）尚未实现，
收到时回 `INTERNAL` 并说明"尚未实现"——它们确实登记在 messages.md 里，谎报 `UNKNOWN_TYPE` 是错的。
`list_storage_formats` 如实回空数组而不是伪造一个格式。

**验证**：

- `.venv\Scripts\python.exe -m unittest discover -s backend/tests -t . -v` → 92 个用例通过
- 端到端（`python -m backend.server --port 8791` + 真客户端）：
  `hello` → `list_plugins` = `[moving-average]` → `open_file` 摘要（温度 5 点、`x_range [0,400]`）
  → `query_range` `aggregated=true`、`ymin=[25.1, 26.0]`、`ymax=[25.3, 26.2]`；
  `resolution=0` 回 `INVALID_REQUEST`，`id` 原样回显
- 会话隔离：A 连接打开文件后，B 连接的 `query_range` 回 `INVALID_REQUEST`
- **滤波在聚合之前**：`set_filter_chain` 后同一视口的结果由 `[25.1, 26.0]` 变为 `[25.2, 26.1]`，
  说明滤波缓存与聚合缓存都失效了
- 一条坏 JSON 不会断连接：发完非法消息后，同连接上的下一条请求仍收到正常响应

**相关**：[guides/kickoff.md](guides/kickoff.md) §五 第 4 批、[modules/core.md](modules/core.md)、
[modules/server.md](modules/server.md)、[messages.md](messages.md)、[protocol.md](protocol.md) §6

### 2026-09-30 | 滤波与聚合 | 像素列 min/max 与处理链落地（第 3 批）

**改动**：

- 新增 `backend/aggregate/`：`aggregate_range(dataset, *, x0, x1, resolution, names=None)`，
  返回值**即** M 消息 `query_range` 的响应 payload。视口裁剪与列内 min/max 合并成一次遍历
- 新增 `backend/filters/`：`apply_chain` / `chain_key` / `get_plugin` / `list_plugins` / `register`，
  外加示例插件 `moving-average`（窗口居中、边界收缩、窗口含 `null` 则结果也是 `null`；
  前缀和实现，耗时与窗口大小无关）
- 新增用例 `backend/tests/test_aggregate.py`（23 个）与 `backend/tests/test_filters.py`（22 个）
- 同步 `docs/modules/aggregate.md`、`docs/modules/filter.md`、`docs/guides/add-filter-plugin.md`
  （从"待建"改为可执行步骤）、`docs/messages.md` M6 补一段说明

**原因**：kickoff §五 第 3 批。此前"禁止抽样""滤波在聚合之前"只有原则，没有可执行实现。
第 2 批（数据源与存储）是插件形态，按用户要求搁置——本批只依赖契约，不依赖数据源。

**影响面**：契约**结构未变**，`schema_version` 仍为 `1.0`，**无需迁移**。
两个模块的接口形状与 M6 / `set_filter_chain` 对齐，第 4 批核心直接调用，不必再改。
`messages.md` M6 补的是**说明**（聚合时 `x` 为像素列中心、空列 `ymin`/`ymax` 为 `null`），
不增删字段。滤波插件机制本批只做**显式登记**，"目录即插件"的扫描与 manifest 仍待插件机制批次；
聚合缓存按设计属核心层（第 4 批），本模块保持无状态。

**验证**：

- `.venv\Scripts\python.exe -m unittest discover -s backend/tests -t . -v` → 58 个用例通过
- 完成标志：点数超过分辨率 → 返回 min/max 对；未超过 → 原始点且 `ymin[i] == ymax[i]`
- **尖峰可见**：1000 个 0 里埋一个 999，`resolution=10` 全览时它出现在 `ymax` 中；
  视口外的极端值不参与（裁剪正确）
- **列边界**：`x0=0, x1=400, resolution=4` → `x=100` 属第 1 列、`x=400`（右端点）属最后一列，
  `ymin=[1,2,3,4]`、`ymax=[1,2,3,5]`
- 缺失值：`null` 不参与 min/max；整列无有效值时为 `null` 而不是 0
- 滤波：`[1,2,3,4,5]` 窗口 3 → `[1.5, 2, 3, 4, 4.5]`；窗口含 `null` → 结果 `null`
- 纯函数：滤波后入参深比较不变；`enabled: false` 时输出与入参逐字段一致；输出仍通过契约校验器
- 实测（100 万点）：聚合 293 ms；滑动平均窗口 5 / 101 / 999 均约 0.45 s
  （改前缀和之前，窗口 101 需 5.1 s——拖滑块会明显卡，故本批就换掉）

**相关**：[guides/kickoff.md](guides/kickoff.md) §五 第 3 批、[modules/aggregate.md](modules/aggregate.md)、
[modules/filter.md](modules/filter.md)、[ARCHITECTURE.md](ARCHITECTURE.md) §4、[DECISIONS.md](DECISIONS.md) D5

### 2026-09-30 | 契约 | 校验器落地：schema + 跨字段检查，接入 pre-commit 与 CI

**改动**：

- 新增 `backend/contract/`：`validator.py` 实现 `validate(data)` / `validate_file(path)`，
  `__init__.py` 导出 `ValidationResult` / `Violation`。违规项带字段路径（如 `series[0].unit`）、
  原因与触发关键字；`error_detail()` 直接对上 M 消息 `CONTRACT_VIOLATION` 的 `detail`
- 新增 `backend/tests/test_contract.py`（标准库 unittest，13 个用例）与 `backend/__init__.py`
- `scripts/check_docs.py` 的示例校验改走该校验器，并新增要求：
  `invalid-` 示例必须被拒绝**且给出字段路径**（原来只要求"被拒绝"）
- `contract/examples/` 补两份：`example-unknown-kind.json`（未知 `kind` + `numeric_values` 的**合法**例）、
  `invalid-length-mismatch.json`（`x.data` 与 `y.data` 不等长）
- 同步 `docs/modules/contract.md`（路径、接口表、第 5 条硬规则、坑表）、
  `contract/README.md`（示例清单 + 怎么校验）、`docs/overview.md` §3.3 检查项描述、
  `docs/acceptance.md` §6 勾选两项

**原因**：kickoff §五 第 1 批——把契约从"文档里的定义"变成"能执行的校验器"。
此前示例校验直接写在检查脚本里，没有跨字段检查；未知 `kind` 只有非法例、
没有合法例，无法证明校验器是"允许未知类型"而不是误拒（S6 的结构前提）。

**影响面**：契约**结构未变**，`schema_version` 仍为 `1.0`，**无需迁移**；
新增的是可执行校验，不含新规则——跨字段检查只实现契约已明示的 `x`/`y` 等长，
`annotation.series` 引用存在性、序列名唯一等**未实现**（那些属收紧契约，要走变更流程）。
`scripts/check_docs.py` 新增对 `backend/contract` 的导入（仓库根加入 `sys.path`），
缺 `jsonschema` 或导入失败仍判失败，不静默跳过。
后续模块（数据源自校验、后端错误提示）统一调用 `validate` / `validate_file`，不再各写一套。

**验证**：

- `.venv\Scripts\python.exe -m unittest discover -s backend/tests -t . -v` → 13 个用例通过
- `.venv\Scripts\python.exe scripts\check_docs.py` → 「文档与契约检查通过」（exit=0）
- 6 份示例：2 份合法通过，4 份非法被拒绝并给出路径
  （`series[0]`、`series[0].x`、`series[0].y.data`）
- 未知字段不丢：`example-basic.json` 的 `x.extensions` 在 JSON 往返后逐字段一致

**相关**：[guides/kickoff.md](guides/kickoff.md) §五 第 1 批、[modules/contract.md](modules/contract.md)、
[contract.md](contract.md) §8、[acceptance.md](acceptance.md) §6

### 2026-09-29 | 文档体系 | kickoff.md 改定位：从"开工入口"改为正式开发提示词

**改动**：重写 `docs/guides/kickoff.md`。标题改为《项目开发提示词》，
补上技术方案与模块地图，不可违反的约束从 5 条扩到 8 条；
各批次的「验证方式」改为「交付物 + 完成标志」。

**原因**：上一版按"怎么验证"组织，读起来像验收清单。
使用者要的是"这个项目做什么、怎么做、先写哪个模块"——
一份能**直接驱动开发**的正式任务书，而不是又一份检查表。

**影响面**：无契约变更、无代码影响。
内容仍全部指向 `docs/` 下的权威文档，**未新增任何规则**。

**验证**：

- 全量检查通过（exit=0）
- 模块地图与 [MODULES.md](MODULES.md) 逐行核对一致
- 六批顺序与 [MODULES.md](MODULES.md) §2 的依赖方向一致，无"后一批依赖前一批未做之物"

**相关**：[guides/kickoff.md](guides/kickoff.md)

### 2026-09-29 | 文档体系 | 新增开工提示词，新会话可一句话启动开发

**改动**：

- 新增 `docs/guides/kickoff.md`：项目要做什么、五条硬规则、动手前读什么、
  **分六批的开发顺序**（每批含位置、依据文档、内容、验证方式）
- `docs/guides/README.md`、`docs/README.md` 补入口

**原因**：此前新会话靠"自动注入 `AGENTS.md` + 自己摸索"起步——规则读得到，
但**不知道先写哪个模块**。文档齐全 ≠ 能开工，缺的是"从哪下手、按什么顺序、
每批怎么验证"这一层。

**影响面**：无契约变更、无代码影响。
与 `framework-test.md` 的分工：前者用于**开工**，后者用于**验收**。

**验证**：

- 全量检查通过（exit=0）
- 六批顺序逐条对照 `MODULES.md` §2 的依赖方向核对，未出现"后一批依赖前一批还没做的东西"
- 第 1 批的接口描述（`validate(data)` 必须带字段路径、只依赖 `jsonschema`）
  对照 `docs/modules/contract.md` §3 与 `requirements.txt` 确认一致

**相关**：[guides/kickoff.md](guides/kickoff.md)、[MODULES.md](MODULES.md) §2

### 2026-09-29 | 文档体系 | 新增框架自测手册，供全新会话验收

**改动**：

- 新增 `docs/guides/framework-test.md`：8 项自测（T1–T8），分**只读项 / 检查项 / 提交项**三层，
  含安全边界、判定记录方式与已知边界
- `docs/acceptance.md` §1 补登记两个此前遗漏的前缀：
  `C`（通信模块待办项，C1–C4）、`T`（框架自测项，T1–T8）
- `docs/guides/README.md` 区分「已建成」与「待建清单」；`docs/README.md` 补导航入口

**原因**：需要验证"换会话、换模型之后这套文档与规则还能不能干活"（S3）。
此前这件事只有一句标准，没有可执行步骤，每次都得临时想；而它恰恰是本项目
最容易被悄悄放弃的一环。

**根因（顺带发现的疏漏）**：`protocol.md` §6 一直在用 `C1`–`C4`，却从未登记。
它没被检查抓到，是因为编号检查**只校验已登记的前缀**——未登记前缀无法与
`UTF8`、`MD5` 这类普通词区分，强判会大量误报。
这条边界已写入手册 §7「已知边界」，不假装它不存在。

**影响面**：无契约变更、无代码影响。
`docs/guides/` 下首次出现一份**完整可执行**的手册，其余六份仍是骨架。

**验证**：

- 全量检查通过（exit=0）
- T1–T4 的判据逐条对照文档原文（`AGENTS.md`、`modules/source.md`、`acceptance.md`、
  `ARCHITECTURE.md` §2.4），确认文档里确实写了，不是凭空拟定
- T3 引用的五个编号确认全部有定义
- T5–T8 涉及的四项机制此前均已实测：探针验证、违规提交被拦、合规提交走通、钩子缺失自检

**相关**：[guides/framework-test.md](guides/framework-test.md)、[acceptance.md](acceptance.md) §1、[protocol.md](protocol.md) §6

### 2026-09-29 | 文档体系 | 补齐验收标准与编号体系，堵住编号悬空引用

**改动**：

- 新增 `docs/acceptance.md`：编号登记表（§1）+ 目标 G1–G5 + 成功标准 S1–S7 +
  功能范围 F1–F3 + 使用场景 SC1–SC7 + 验收清单
- 修复 3 处悬空引用：`ARCHITECTURE.md` 里的 `§4-F3` 与 `S5`、`overview.md` 里的 `S3`
- `check_docs.py` 新增 `check_id_references()`：编号引用必须落在登记范围内
- `check_docs.py` 的 `CODE_PREFIXES` 补上 `scripts/`；docstring 里过时的
  "jsonschema 缺失时跳过"改为与实际一致（早就改成判失败了）
- `AGENTS.md`、`docs/README.md`、`docs/overview.md` 同步

**原因**：核对压缩后的会话记录时发现，`ARCHITECTURE.md` 与 `overview.md` 引用了
`§4-F3`、`S5`、`S3` 三个编号，但**整个仓库没有任何地方定义它们**。
定义只存在于仓库外的草稿《数据可视化应用-需求规格.md》。

**根因**：需求从草稿搬进 `docs/` 时，搬的是**结论**（契约、架构、决策），
漏掉了**验收标准**这一层——而 `S3`、`S5`、`S7` 恰好是原草稿标注的核心验收项。
正文里的编号引用又照抄了旧草稿：节号（`§4`）在搬运后已不存在，
功能编号（`F1`–`F3`）从未搬入。**`check_docs.py` 只校验 markdown 链接，
编号是纯文本，悬空查不出来**——这是"检查通过"与"内容正确"之间的空隙。

**影响面**：无契约变更、无代码影响。
新增一项提交前检查：编号引用越界会拒绝提交。
`U` 前缀已被"UI 层约束"（[ARCHITECTURE.md](ARCHITECTURE.md) §5）占用，
故使用场景改用 `SC` 登记——同一前缀两套含义会让两套都无法解析。

**验证**（用一个临时探针文件，验证完已删除）：

```text
越界  S9  D99  M88  U9  SC8            → 5 条全部报出，exit=1
合法  S3  D5  M6  U2  SC1  F3  G4  L2  → 零误报
SC8 未被误判成 S 前缀越界
删除探针后全量检查通过（exit=0）
```

> 本条目最初的写法把越界编号写在了正文里，**结果是提交被自己的新检查拦下**——
> 检查本身没问题，是规则少了"代码块内不算引用"这一条。已补上。

**相关**：[acceptance.md](acceptance.md)、[ARCHITECTURE.md](ARCHITECTURE.md) §2.4、§6.4、[overview.md](overview.md) §3.3

### 2026-09-29 | 工具链 | 确定依赖管理：虚拟环境 + requirements.txt

**改动**：

- 新增 `requirements.txt`：只列**直接依赖**，版本写死（`jsonschema==4.26.0`）
- 新增 `.venv` 虚拟环境（`.gitignore` 已含 `.venv/`，无需改动）
- `.githooks/pre-commit` 改为**优先使用项目虚拟环境的解释器**
  （`.venv/Scripts/python.exe` 或 `.venv/bin/python`，都没有才退回系统 python）
- `scripts/setup.py` 扩展为三步：建虚拟环境 → 装依赖 → 启用钩子
- `.github/workflows/check.yml` 改用 `pip install -r requirements.txt`
- `README.md`、`docs/overview.md` 同步（新增 §3.5 依赖管理）

**原因**：程序依赖别人写的库，需要决定"记在哪"和"装在哪"。
机器全局环境已装 **89 个与本项目无关的包**，混用会导致版本冲突，
打包 exe 时也容易带上无关库。

**为什么不用 uv / poetry**：本项目后端依赖预计只有 3~5 个，手工钉版本足够可控，
额外工具只增加学习与打包成本。**升级触发条件**：依赖超过 10 个，或需要区分开发/运行依赖。

**影响面**：无契约变更。
**此后提交前检查会使用 `.venv` 里的解释器**——这修掉了一个隐患：
原钩子用全局 python，那里没有 `jsonschema`，会导致检查失败而拒绝提交。

**验证**：

- `python scripts/setup.py` 可重复执行（幂等），不会重复建环境或报错
- `.venv\Scripts\python.exe scripts\check_docs.py` 输出「文档与契约检查通过」
- 提交时钩子实际走的是虚拟环境解释器

**相关**：[overview.md](overview.md) §3.4、§3.5

### 2026-09-29 | 工具链 | 接入远端仓库与 CI

**改动**：

- 配置远端 `origin` = `git@github.com:Samviska/Base.git`
- 取回远端 `main` 上已有的 `LICENSE`（MIT, © 2026 Samviska），纳入本项目历史
- 新增 `.github/workflows/check.yml`：推送后跑同一套 `check_docs.py`，并检查本次提交的过程约束
- `check_docs.py` 新增 `--commit=<rev>`：CI 里没有暂存区，改为从提交读改动清单
- `README.md` 补"许可证"一节；`docs/overview.md` 更新目录树与已知限制

**原因**：本地钩子可被 `git commit --no-verify` 绕过，这是 git 的设计，本地无解。
配好远端后即可用 CI 补上——**这是唯一能覆盖该绕过路径的手段**。

**影响面**：无契约变更。
仓库原有的 `main`（仅含 GitHub 自动生成的 `LICENSE`）与本地 `master`（13 个提交）
是两段**互不相关**的历史，本次统一为 `main`。

**验证**：

- `python scripts/check_docs.py --commit=HEAD` 可在本地复现 CI 的过程约束检查
- 推送后 GitHub Actions 的实际运行结果（仓库 Actions 页）

**相关**：`.github/workflows/check.yml`、[overview.md](overview.md) §3.3

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
