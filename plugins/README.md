# 插件目录

这里放**内置之外**的插件，由使用者或 AI 新增。

## 目录

| 目录 | 插件类型 | 开发文档 |
| --- | --- | --- |
| `sources/` | 数据源（日志解析；将来的实时数据流） | [docs/modules/source.md](../docs/modules/source.md) |
| `filters/` | 滤波 | [docs/modules/filter.md](../docs/modules/filter.md) |
| `renderers/` | 渲染 | [docs/modules/renderer.md](../docs/modules/renderer.md) |

## 规则

1. **一个插件一个独立文件夹**，可整目录增删。
2. 每个插件**必须带 manifest**，声明名称、类型、模式、版本、入口、参数、文案。
3. 插件**只依赖契约**；不得依赖核心内部实现，也不得互相直接调用。
4. **接入插件不需要编译**。往目录里放文件即可被识别。
5. 插件异常**不得导致应用崩溃**——错误会被捕获并呈现。
6. 新增插件后，界面上应自动出现对应选项，**不需要手工编辑任何配置文件**。

> 完整的新增步骤见 [docs/guides/](../docs/guides/) 下对应手册。
