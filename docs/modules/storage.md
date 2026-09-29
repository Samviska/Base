# 模块：存储（Storage）

## 1. 一句话职责

契约数据的读写。

**接口按"使用数据的需求"定义，不按文件格式定义。**

**不负责**：数据的语义（那是[契约](contract.md)）、滤波、聚合。

## 2. 代码位置

| 内容 | 路径（规划） |
| --- | --- |
| 接口定义与格式注册 | `backend/storage/` |
| JSON 实现 | `backend/storage/` |
| 测试数据 | `contract/examples/` |

## 3. 对外接口

```
open_source(path, format=auto) -> 句柄

句柄：
  meta()                        读取元信息
  series_info()                 序列列表（名称、单位、点数、轴描述、x 范围）
  read_range(series, x0, x1)    按 x 范围读取点     ← 关键能力
  read_all(series)              按序列读取全部点（滤波用）
  write(data)                   写入
  annotations()                 读取注解
  set_annotations(list)         写入注解
```

## 4. 依赖规则

| | |
| --- | --- |
| 可以依赖 | 契约 |
| **禁止依赖** | 界面、聚合、渲染器 |

## 5. 扩展点

新增一种存储格式 = 实现同一套接口 + 在格式表里登记一行。
见 [guides/add-storage-format.md](../guides/add-storage-format.md)。

## 6. 本模块的硬规则

1. **接口名里不得出现格式名。**
   - 反例：`load_json_file(path)`
   - 正例：`open_source(path, format=auto)`
2. **必须实现 `read_range`**，即使某些实现只能"先全读再切片"。
   这是[聚合](aggregate.md)能高效工作的前提。
3. **读取方向允许自动探测格式；写入方向必须显式指定格式。**
   - 理由：读错可以补救，写错是使用者的选择，应当一目了然。
4. **未知字段原样保留**（见[契约模块](contract.md) §6）。
5. 读取失败要**明确报错并说明试过哪些格式**，不要猜。

## 7. 已知的坑

| 坑 | 现象 | 应对 |
| --- | --- | --- |
| **接口对齐 ≠ 性能对齐** | 换实现后上层代码不用改，但 JSON 实现的 `read_range` 实际是全读后切片，大文件下很慢 | 文档里写清各实现的性能特征，别让人误以为等价。**接口解决的是"代码不改"，不是"性能一样"** |
| 格式探测误判 | 恰好整个文件能解析成 JSON 的 JSONL 被当成 JSON | 探测顺序：显式指定 > 扩展名 > 内容；都失败就报错 |
| 大文件全量载入内存 | 内存峰值高 | 用 `read_range` 而非 `read_all`；体量大时换 SQLite 实现 |
| 二进制格式可读性下降 | 不能用记事本检查数据 | 这是选 SQLite 时的已知代价，需在决策时权衡 |

## 8. 相关

- 数据结构：[contract.md](../contract.md)
- 怎么加格式：[guides/add-storage-format.md](../guides/add-storage-format.md)
- 为什么 V1 只用 JSON：[DECISIONS.md](../DECISIONS.md) D6
