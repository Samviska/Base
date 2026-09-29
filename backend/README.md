# 后端（Python）

## 职责

数据提取、滤波、聚合、存储、通信服务，以及插件注册与编排。

## 目录

| 目录 | 模块 | 开发文档 |
| --- | --- | --- |
| `core/` | 编排、会话状态、缓存失效 | [docs/modules/core.md](../docs/modules/core.md) |
| `contract/` | 契约实现与校验器 | [docs/modules/contract.md](../docs/modules/contract.md) |
| `sources/` | 数据源插件 | [docs/modules/source.md](../docs/modules/source.md) |
| `filters/` | 滤波插件 | [docs/modules/filter.md](../docs/modules/filter.md) |
| `storage/` | 存储实现 | [docs/modules/storage.md](../docs/modules/storage.md) |
| `aggregate/` | 聚合（视口裁剪 + 像素列 min/max） | [docs/modules/aggregate.md](../docs/modules/aggregate.md) |
| `server/` | WebSocket 服务 | [docs/modules/server.md](../docs/modules/server.md) |
| `tests/` | 测试 | — |

## 规则

1. **只依赖契约**，不依赖前端，不依赖具体插件的实现。
2. **不得把界面相关内容写进后端**（文案、布局、控件逻辑）。
3. **数据流顺序固定**：提取 → 滤波 → 聚合。滤波必须在聚合之前，且都拿全量数据。
4. **开发期直接运行源码，不要打包**。
5. 改完任何模块，**同步更新对应的模块文档**，并在 [DEVLOG](../docs/DEVLOG.md) 追加一条。
