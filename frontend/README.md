# 前端（Vue 3 + Vite）

## 职责

界面外壳、与后端通信、画布内的图形绘制与交互。

## 目录

| 目录 | 模块 | 开发文档 |
| --- | --- | --- |
| `ui/` | 面板、控件、对话框、状态提示 | [docs/modules/ui-shell.md](../docs/modules/ui-shell.md) |
| `api/` | 通信客户端（WebSocket、节流、代次作废） | [docs/modules/api-client.md](../docs/modules/api-client.md) |
| `renderers/` | 渲染器接口与内置实现 | [docs/modules/renderer.md](../docs/modules/renderer.md) |
| `tests/` | 测试（Node 内置 test runner，+ 可选的真后端联通用例） | — |

## 怎么跑

```powershell
# 1) 先起后端（另开一个终端，仓库根目录）
.venv\Scripts\python.exe -m backend.server

# 2) 起前端 dev server（本目录）
npm install          # 首次
npm run dev          # → http://127.0.0.1:5173/

# 3) 测试
npm test             # 单元与交互用例（Node 内置 test runner，假 DOM）
npm run e2e          # 真实浏览器内测（Playwright + 系统 Edge），需先起好后端与 dev server
npm run build        # 只在交付时用；开发期改完即见
```

**内测**（`npm run e2e`）会把"选日志 → 出图 → 缩放 / 平移 / 双击 / 全览"整条路走一遍，
并截图到 `_local/e2e-*.png`。它用**系统自带的 Edge**，不需要下载浏览器。

> **跑内测前先重启 dev server**：Vite 的 HMR 会累积状态，页面可能仍停留在旧代码上
> （表现为"改了没效果"）。这类假象会浪费很多时间。

后端换端口时，页面用 `?backend=ws://127.0.0.1:8791` 指定，不必改代码。

## 规则

1. **渲染器的接口层面不得引用 Vue**——它只认「契约数据 + 一个挂载容器」。
   接口一旦绑框架，"渲染器可整块替换"就作废。
2. **界面不含业务逻辑**。界面只做两件事：渲染状态、转发命令。
   **验收方法：新增一个界面面板，核心代码应零改动。**
3. **开发期用 dev server，改完即见**。构建只发生在交付环节。
4. 视觉值集中到 CSS 变量，不要散落硬编码。
5. 改完任何模块，**同步更新对应的模块文档**，并在 [DEVLOG](../docs/DEVLOG.md) 追加一条。
