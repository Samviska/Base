# 模块：数据源（Source）

## 1. 一句话职责

把**任意格式的输入**（文件，或将来的数据流）转换成符合契约的数据。

**不负责**：滤波、聚合、绘制、界面操作。

## 2. 代码位置

| 内容 | 路径 |
| --- | --- |
| 接口定义与注册机制 | `backend/sources/registry.py`、`backend/sources/__init__.py` |
| 内置实现（直接读契约 JSON） | `backend/sources/contract_json.py` |
| 使用者 / 第三方插件 | `plugins/sources/<名字>/`（`manifest.json` + 入口模块） |
| 实例：JP18 心电日志 | `plugins/sources/jp18/`（含格式说明 README） |
| 用例 | `backend/tests/test_sources.py` |

## 3. 对外接口

两种模式，同一类插件：

| 模式 | 接口形态 | 本期 |
| --- | --- | --- |
| **一次性** | `extract(path, options) -> 契约数据` | **已实现** |
| **持续** | `open_stream(config) -> 句柄 { 取数据块(), 关闭() }` | **只留接口**（`manifest.mode = "stream"`） |

> 将来的实时数据更新就是"写一个持续模式的插件"，核心不需要改动。

插件对外只有这些成员：

| 成员 | 作用 |
| --- | --- |
| `manifest.json` | 声明 `id` / `display_name` / `version` / `entry` / `mode`；**参数在代码里声明**，避免两处重复 |
| `extract(path, options) -> dict` | 把输入变成契约数据；**必须自校验** |
| `declare_params() -> list[dict]` | 参数声明，界面据此自动生成控件 |

核心侧（`backend/core/dispatch.py`）负责：

| 情形 | 行为 |
| --- | --- |
| `source_plugin` 省略 | 用内置的 `contract-json`（直接读契约 JSON） |
| 插件不存在 | `PLUGIN_NOT_FOUND`，消息里列出可用插件 |
| 插件抛 `FileNotFoundError` | `FILE_NOT_FOUND` |
| 插件抛其它异常 | `PLUGIN_FAILED` + 可读原因；**不向主流程传播** |
| 插件输出不合规 | 核心**兜底再校验一次** → `CONTRACT_VIOLATION` 并给出字段路径 |
| 插件目录里的坏插件 | 加载失败只记警告，服务照常启动；警告随 `list_plugins` 回给界面（S4） |

## 4. 依赖规则

| | |
| --- | --- |
| 可以依赖 | 契约 |
| **禁止依赖** | 核心内部实现、其他插件、界面 |

**不得直接操作界面**：它只做"输入 → 契约数据"这一件事。
需要用户输入选项时，通过 `options` 由核心传入。

## 5. 扩展点

新增一种日志格式 = 在 `plugins/sources/<名字>/` 放一个实现文件 + 一份 manifest。
见 [guides/add-source-plugin.md](../guides/add-source-plugin.md)。

## 6. 本模块的硬规则

1. **必须自校验**输出是否符合契约；不合规时报错并**指出出错字段路径**。
2. **结果必须可复现**：同一输入 + 同一插件版本 = 同一输出。
3. **必须声明它产出的 x 轴描述**，包括自己声明的扩展 `kind`（若用扩展类型，必须同时给 `numeric_values`）。
4. **时钟跳变 / 回绕必须显式处理**并记入 `meta.notes`。
   - 反例：设备时钟重置后产生一条 x 非单调的曲线，图形含义彻底失效。

## 7. 已知的坑

| 坑 | 现象 | 应对 |
| --- | --- | --- |
| 日志只有相对上电时间 | 硬凑绝对时间导致错乱 | 用 `origin: start`，不要伪造日期 |
| 微秒被当毫秒 | 波形被压缩 1000 倍 | 声明精度并统一换算 |
| 日志存在乱序行 | x 非单调，缩放与聚合行为异常 | 显式排序，并在 `meta.notes` 记录 |
| 单位缺失 | 界面无法显示单位 | 无量纲写 `"1"` |
| 提取过程中丢弃异常点 | 尖峰消失，问题被藏起来 | 保留原始值；用 `null` 表示缺失，不要跳过 |
| 解析失败直接抛出原始异常 | 使用者看不懂 | 转成"第几个文件、第几行、什么格式期望"的可读错误 |
| 十六进制文本日志 | 当二进制读会得到一堆 ASCII 码 | 先按十六进制 token 解析成字节，再按包结构切分（见 JP18 插件） |
| 数据里出现"像包头"的字节 | 全流搜索 `0x88` 会在数据中间误判包边界 | 用**固定包长**切分并校验首字节；不要靠搜索包头 |
| 数据中间混入填充 | 样本数不是整数、波形出现满量程跳变 | 显式跳过 `80 80 80` 组；**样本数正好是整数**才说明切分对了 |
| 日志没有采样率 | 硬凑毫秒会让波形含义失真 | 横轴默认采样序号，采样率做成插件参数 |

## 8. 相关

- 数据结构：[contract.md](../contract.md)
- 怎么加插件：[guides/add-source-plugin.md](../guides/add-source-plugin.md)
- 两种模式的由来：[DECISIONS.md](../DECISIONS.md) D12、[roadmap.md](../roadmap.md) §3
