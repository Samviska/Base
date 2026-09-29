# 前端（Vue 3 + Vite）

## 职责

界面外壳、与后端通信、画布内的图形绘制与交互。

## 目录

| 目录 | 模块 | 开发文档 |
| --- | --- | --- |
| `ui/` | 面板、控件、对话框、状态提示 | [docs/modules/ui-shell.md](../docs/modules/ui-shell.md) |
| `api/` | 通信客户端（WebSocket、节流、代次作废） | [docs/modules/api-client.md](../docs/modules/api-client.md) |
| `renderers/` | 渲染器接口与内置实现 | [docs/modules/renderer.md](../docs/modules/renderer.md) |
| `tests/` | 测试 | — |

## 规则

1. **渲染器的接口层面不得引用 Vue**——它只认「契约数据 + 一个挂载容器」。
   接口一旦绑框架，"渲染器可整块替换"就作废。
2. **界面不含业务逻辑**。界面只做两件事：渲染状态、转发命令。
   **验收方法：新增一个界面面板，核心代码应零改动。**
3. **开发期用 dev server，改完即见**。构建只发生在交付环节。
4. 视觉值集中到 CSS 变量，不要散落硬编码。
5. 改完任何模块，**同步更新对应的模块文档**，并在 [DEVLOG](../docs/DEVLOG.md) 追加一条。
