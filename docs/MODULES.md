# 模块地图

> 用途：**定位**。想知道"要改的东西在哪儿、属于哪个模块、该读哪份文档"，看这一页。
> 每个模块的具体规则在它自己的 `modules/*.md` 里，本页不重复。
> **代码目录为规划结构，尚未创建。**

---

## 一、模块清单

| 模块 | 一句话职责 | 代码位置 | 开发文档 | 可替换性 |
| --- | --- | --- | --- | --- |
| **契约** | 定义数据长什么样，并提供校验 | `contract/`、`backend/contract/` | [modules/contract.md](modules/contract.md) | **冻结**，变更走专门流程 |
| **数据源** | 日志 / 数据流 → 契约数据 | `backend/sources/` | [modules/source.md](modules/source.md) | **插件**，可无限新增 |
| **滤波** | 全量数据 → 全量数据 | `backend/filters/` | [modules/filter.md](modules/filter.md) | **插件** |
| **聚合** | 全量数据 + 视口 → 绘制数据 | `backend/aggregate/` | [modules/aggregate.md](modules/aggregate.md) | 内部模块，可换策略 |
| **存储** | 契约数据的读写 | `backend/storage/` | [modules/storage.md](modules/storage.md) | **多实现**，可加格式 |
| **后端核心** | 编排各环节、会话状态、缓存失效 | `backend/core/` | [modules/core.md](modules/core.md) | 稳定，很少改动 |
| **通信服务** | WebSocket 服务端 | `backend/server/` | [modules/server.md](modules/server.md) | 稳定 |
| **通信客户端** | 前端侧的消息收发与配对 | `frontend/api/` | [modules/api-client.md](modules/api-client.md) | 稳定 |
| **渲染器** | 绘制数据 → 画布上的图形与交互 | `frontend/renderers/` | [modules/renderer.md](modules/renderer.md) | **插件** |
| **UI 外壳** | 面板、控件、对话框、状态提示 | `frontend/ui/` | [modules/ui-shell.md](modules/ui-shell.md) | **可整块重做** |

> **"可替换性"列是这份地图的重点**：它直接回答"改这个模块要不要担心牵连别处"。
> 标 **插件** 的，新增能力只需新增文件；标 **可整块重做** 的，连根换掉都不影响其他模块。

---

## 二、依赖方向

```
                    ┌──────────────┐
                    │     契约      │  ← 不依赖任何模块
                    └──────────────┘
                    ↑  ↑  ↑  ↑  ↑  ↑
        ┌───────────┘  │  │  │  │  └───────────┐
   数据源插件       滤波插件 │  存储实现      渲染器插件
                    ┌──────┘                  ↑
                 聚合模块                     │
                    ↑                        │
                ┌────────┐                   │
                │ 后端核心 │                  │
                └────────┘                   │
                    ↕                        │
                ┌────────┐    WebSocket    ┌─┴────────┐
                │ 通信服务 │ ←───────────→  │ 通信客户端 │
                └────────┘                 └──────────┘
                                                ↑
                                           ┌────────┐
                                           │ UI 外壳 │
                                           └────────┘
```

**三条硬规则**：

1. **契约不依赖任何模块。** 谁都可以依赖它，它不可以依赖任何人。
2. **插件只依赖契约**，不得依赖核心内部实现，也不得互相调用。
3. **前端不直连后端内部**，只能通过通信层；且**拿不到全量数据**（聚合在服务端完成）。

---

## 三、改动前的自检

| 问题 | 若答案为"是" |
| --- | --- |
| 我改的文件，属于上表里的**同一个**模块吗？ | 说明改动跨模块了，需要分别更新各自的文档 |
| 我的改动，需要**修改插件接口**吗？ | 停下：接口属于契约，要走契约变更流程 |
| 我的改动，会让**其他模块的文档失效**吗？ | 那些文档必须一起改，`DEVLOG.md` 要写明影响面 |

---

## 四、模块文档的写法

- 模块文档统一放 `docs/modules/`，文件名用小写英文，与模块名一致。
- **新建模块文档时复制 [`modules/_template.md`](modules/_template.md)**，不要另创格式。
- `modules/` 与 `guides/` 的分工：
  - `modules/renderer.md` 讲**渲染器是什么、受什么规则约束**
  - `guides/add-renderer.md` 讲**怎么加一个渲染器**
