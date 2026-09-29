# 消息清单

> 本文件列出**前后端之间有哪些消息、各自长什么样**。
> 通信规则与设计理由见 [protocol.md](protocol.md)，本文件不重复。
>
> **新增消息必须登记到这里**，前后端都不得在业务代码里临时拼装未登记的类型。

---

## 1. 三种消息形态

| 形态 | 结构 | 说明 |
| --- | --- | --- |
| **请求** | `{ "id": 42, "type": "...", "payload": { } }` | 有 `id` |
| **响应** | `{ "id": 42, "type": "...", "ok": true, "payload": { } }` | `id` 与请求相同，`type` 回显 |
| **失败响应** | `{ "id": 42, "type": "...", "ok": false, "error": { } }` | 见 §2 |
| **事件** | `{ "type": "...", "payload": { } }` | **无 `id`**，服务端主动发出 |

> 响应回显 `type` 是为了让日志可读——只看 `id` 数字无法判断是哪条请求。

---

## 2. 错误对象与错误码

```json
{
  "code": "CONTRACT_VIOLATION",
  "message": "插件输出不符合契约",
  "detail": { "path": "series[0].unit", "reason": "缺少必填字段" }
}
```

| 错误码 | 含义 |
| --- | --- |
| `INVALID_REQUEST` | 消息结构不合法（缺字段、类型错） |
| `UNKNOWN_TYPE` | 消息类型未登记 |
| `FILE_NOT_FOUND` | 指定的文件不存在 |
| `PLUGIN_NOT_FOUND` | 指定的插件不存在 |
| `PLUGIN_FAILED` | 插件执行时抛出异常 |
| `CONTRACT_VIOLATION` | 插件输出不符合契约（`detail` 必须给出字段路径） |
| `INTERNAL` | 未归类的内部错误 |

**要求**：`detail` 能定位问题时必须给。只给一句"出错了"等于没给。

---

## 3. 消息总表（速查）

### 3.1 连接与插件

| 消息 | 方向 | 用途 |
| --- | --- | --- |
| [`hello`](#m1-hello) | 后端 → 前端（事件） | 服务就绪、协议版本 |
| [`list_plugins`](#m2-list_plugins) | 前端 → 后端 | 取可用插件清单 |

### 3.2 数据源

| 消息 | 方向 | 用途 |
| --- | --- | --- |
| [`open_file`](#m3-open_file) | 前端 → 后端 | 用指定数据源插件打开文件 |
| [`close_source`](#m4-close_source) | 前端 → 后端 | 关闭当前数据源 |
| [`list_storage_formats`](#m5-list_storage_formats) | 前端 → 后端 | 列出可用存储格式 |

### 3.3 数据查询（高频）

| 消息 | 方向 | 用途 |
| --- | --- | --- |
| [`query_range`](#m6-query_range) | 前端 → 后端 | **请求视口范围内的绘制数据** |

### 3.4 滤波

| 消息 | 方向 | 用途 |
| --- | --- | --- |
| [`get_filter_chain`](#m7-get_filter_chain) | 前端 → 后端 | 取当前处理链 |
| [`set_filter_chain`](#m8-set_filter_chain) | 前端 → 后端 | 设置处理链（顺序、启用、参数） |

### 3.5 标注

| 消息 | 方向 | 用途 |
| --- | --- | --- |
| [`list_annotations`](#m9-list_annotations) | 前端 → 后端 | 列出全部标注 |
| [`add_annotation`](#m10-add_annotation) | 前端 → 后端 | 新增 |
| [`update_annotation`](#m11-update_annotation) | 前端 → 后端 | 修改 |
| [`remove_annotation`](#m12-remove_annotation) | 前端 → 后端 | 删除 |

### 3.6 会话

| 消息 | 方向 | 用途 |
| --- | --- | --- |
| [`save_session`](#m13-save_session) | 前端 → 后端 | 保存会话 |
| [`load_session`](#m14-load_session) | 前端 → 后端 | 载入会话 |

### 3.7 服务端事件（无 `id`）

| 消息 | 方向 | 用途 |
| --- | --- | --- |
| [`progress`](#m15-progress) | 后端 → 前端 | 长任务进度 |
| [`error_notice`](#m16-error_notice) | 后端 → 前端 | 主动上报的问题（如插件异常） |
| [`stream_data`](#m17-stream_data-预留) | 后端 → 前端 | **预留**：实时数据推送 |

---

## 4. 明细

### M1 `hello`

| 项 | 内容 |
| --- | --- |
| 方向 | 后端 → 前端 |
| 形态 | 事件（无 `id`） |
| payload | `{ "protocol_version": "1.0", "backend_version": "0.1.0" }` |

**什么时候发**：服务就绪后立即发。前端据此确认后端可用，并校对协议版本。

---

### M2 `list_plugins`

| 项 | 内容 |
| --- | --- |
| 方向 | 前端 → 后端 |
| 形态 | 请求 |
| payload | `{ "type": "source" \| "renderer" \| "filter" }`（可省略，省略即全部） |
| 响应 payload | 见下 |

```json
{
  "plugins": [
    {
      "id": "demo-log",
      "type": "source",
      "mode": "oneshot",
      "version": "1.0.0",
      "display_name": "示例日志解析",
      "params": [
        { "name": "encoding", "type": "enum", "values": ["utf-8", "gbk"], "default": "utf-8" }
      ]
    },
    {
      "id": "line",
      "type": "renderer",
      "version": "1.0.0",
      "display_name": "折线图"
    },
    {
      "id": "moving-average",
      "type": "filter",
      "version": "1.0.0",
      "display_name": "滑动平均",
      "params": [
        { "name": "window", "type": "int", "min": 1, "max": 1000, "default": 5 }
      ]
    }
  ]
}
```

**界面的参数控件由 `params` 自动生成**，不得为某个插件写死控件。

---

### M3 `open_file`

| 项 | 内容 |
| --- | --- |
| 方向 | 前端 → 后端 |
| 形态 | 请求 |
| payload | `{ "path": "...", "source_plugin": "demo-log", "options": { } }` |
| 响应 payload | `{ "meta": { }, "series": [ ] }` |

响应**只给摘要，不给数据**：

```json
{
  "meta": { "source": "a.log", "extractor": "demo-log@1.0.0", "sample_count": 12345 },
  "series": [
    {
      "name": "温度",
      "unit": "°C",
      "axis": { "kind": "time", "origin": "start", "unit": "ms", "scale": "linear" },
      "point_count": 12345,
      "x_range": [0, 400000]
    }
  ]
}
```

> **数据不在这个响应里**，必须通过 `query_range` 取。这是分层纪律的体现——前端永远不接触全量数据。

**可能失败**：`FILE_NOT_FOUND`、`PLUGIN_NOT_FOUND`、`PLUGIN_FAILED`、`CONTRACT_VIOLATION`。
其中 `CONTRACT_VIOLATION` 必须给出出错字段路径。

---

### M4 `close_source`

| 项 | 内容 |
| --- | --- |
| 方向 | 前端 → 后端 |
| 形态 | 请求 |
| payload | `{ }` |
| 响应 payload | `{ "closed": true }` |

关闭后，缓存的提取结果、滤波结果、聚合结果全部失效。

---

### M5 `list_storage_formats`

| 项 | 内容 |
| --- | --- |
| 方向 | 前端 → 后端 |
| 形态 | 请求 |
| payload | `{ }` |
| 响应 payload | `{ "formats": [ { "id": "json", "display_name": "JSON", "can_read": true, "can_write": true, "notes": "文本格式，可直接用记事本查看" } ] }` |

**`notes` 必填**：不同存储格式的性能与可读性差异明显，使用者需要据此选择。

---

### M6 `query_range`

**这是最高频的消息**，也是[protocol.md §4](protocol.md) 的节流与代次作废所针对的对象。

| 项 | 内容 |
| --- | --- |
| 方向 | 前端 → 后端 |
| 形态 | 请求 |
| payload | `{ "series": ["温度"], "x0": 0, "x1": 400000, "resolution": 1920 }` |
| 响应 payload | 见下 |

- `series` 省略或为空数组 = 全部序列
- `resolution` = 目标分辨率，**由前端给出画布像素宽度**

```json
{
  "aggregated": true,
  "series": [
    {
      "name": "温度",
      "x":    [0, 200, 400],
      "ymin": [25.1, 25.0, 25.9],
      "ymax": [25.1, 26.4, 26.2]
    }
  ]
}
```

**结构统一，只有绘制模式不同**：

| `aggregated` | 含义 | 渲染器怎么画 |
| --- | --- | --- |
| `false` | 范围内点数未超过分辨率，返回**原始点** | 此时 `ymin[i] === ymax[i]`，按折线画 |
| `true` | 发生了像素列 min/max 聚合 | 每列画一条 `ymin → ymax` 的竖线段 |

> 前端**不需要为数据量分支写代码**：它总是发同样的请求，按返回的标志选择绘制模式。
> 界面还必须据此**标注"当前处于聚合显示状态"**（见 [ARCHITECTURE.md](ARCHITECTURE.md) §4）。

**节流要求**：此消息必须按帧节流 + 代次作废发送。见 [protocol.md](protocol.md) §4。

---

### M7 `get_filter_chain`

| 项 | 内容 |
| --- | --- |
| 方向 | 前端 → 后端 |
| payload | `{ }` |
| 响应 payload | `{ "chain": [ { "plugin": "moving-average", "enabled": true, "params": { "window": 5 } } ] }` |

---

### M8 `set_filter_chain`

| 项 | 内容 |
| --- | --- |
| 方向 | 前端 → 后端 |
| payload | `{ "chain": [ { "plugin": "moving-average", "enabled": true, "params": { "window": 5 } } ] }` |
| 响应 payload | `{ "applied": true }` |

**链的顺序即数组顺序**。
设置成功后，滤波缓存与聚合缓存必须失效（见 [modules/core.md](modules/core.md) §6）。

---

### M9 `list_annotations`

| 项 | 内容 |
| --- | --- |
| 方向 | 前端 → 后端 |
| payload | `{ }` |
| 响应 payload | `{ "annotations": [ { "id": "a1", ... } ] }` |

字段定义见 [contract.md](contract.md) §5。

---

### M10 `add_annotation`

| 项 | 内容 |
| --- | --- |
| 方向 | 前端 → 后端 |
| payload | `{ "series": "温度", "kind": "point", "x": 300, "label": "疑似异常", "note": "..." }` |
| 响应 payload | `{ "id": "a2" }` |

**`id` 由后端生成**，前端不得自行编号。

---

### M11 `update_annotation`

| 项 | 内容 |
| --- | --- |
| 方向 | 前端 → 后端 |
| payload | `{ "id": "a2", "label": "已确认异常" }`（只传要改的字段） |
| 响应 payload | `{ "updated": true }` |

---

### M12 `remove_annotation`

| 项 | 内容 |
| --- | --- |
| 方向 | 前端 → 后端 |
| payload | `{ "id": "a2" }` |
| 响应 payload | `{ "removed": true }` |

---

### M13 `save_session`

| 项 | 内容 |
| --- | --- |
| 方向 | 前端 → 后端 |
| payload | `{ "path": "..." }` |
| 响应 payload | `{ "saved": true, "path": "..." }` |

**会话内容**：数据源引用 + 滤波链参数 + 标注 + 视图状态。
**会话里不得包含数据本身**（见 [modules/core.md](modules/core.md) §7）。

---

### M14 `load_session`

| 项 | 内容 |
| --- | --- |
| 方向 | 前端 → 后端 |
| payload | `{ "path": "..." }` |
| 响应 payload | `{ "source": { }, "chain": [ ], "annotations": [ ], "view": { } }` |

载入后，前端应据 `source` 重新触发一次 `open_file`，再据其余字段恢复状态。

---

### M15 `progress`

| 项 | 内容 |
| --- | --- |
| 方向 | 后端 → 前端 |
| 形态 | **事件（无 `id`）** |
| payload | `{ "task": "open_file", "current": 30, "total": 100, "message": "解析中" }` |

用于长任务（大文件解析、大范围聚合）的进度反馈。
**大文件加载不得阻塞界面**，必须有进度反馈。

---

### M16 `error_notice`

| 项 | 内容 |
| --- | --- |
| 方向 | 后端 → 前端 |
| 形态 | **事件（无 `id`）** |
| payload | `{ "source": "plugin:demo-log", "code": "PLUGIN_FAILED", "message": "...", "detail": { } }` |

**用于"没有对应请求"的错误**，典型是插件在后台抛异常。
有对应请求的错误应走失败响应，不要用这个事件。

---

### M17 `stream_data`（预留）

| 项 | 内容 |
| --- | --- |
| 方向 | 后端 → 前端 |
| 形态 | 事件（无 `id`） |
| payload | `{ "source_id": "...", "chunks": [ ] }` |

**本期不实现。** 为将来的实时数据更新预留——数据源插件的"持续模式"产出数据块后，由此消息推给前端。

**现在必须保留的是**：渲染接口支持 `appendData`，使这条消息将来接得上。

---

## 5. 新增消息的流程

1. 在本文件登记（类型名、方向、payload、响应）。
2. 判断是不是契约变更：若影响数据结构，先走 [guides/contract-change.md](guides/contract-change.md)。
3. 前后端同时实现，**两侧的字段名必须完全一致**。
4. 在 [DEVLOG.md](DEVLOG.md) 追加一条。
