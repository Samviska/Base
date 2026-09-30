# 模块：通信客户端（API Client，前端侧）

## 1. 一句话职责

前端侧的消息收发：建连、发命令、**按 `id` 配对响应**、分发服务端事件。

**不负责**：业务判断（那是[核心](core.md)）、界面渲染（那是 [UI 外壳](ui-shell.md)）。

## 2. 代码位置

| 内容 | 路径 |
| --- | --- |
| 连接、请求、事件分发 | `frontend/api/client.js` |
| 按帧节流 + 代次作废 | `frontend/api/viewport-loader.js` |
| 用例 | `frontend/tests/viewport-loader.test.js`（假帧）、`frontend/tests/backend-integration.test.js`（真后端，默认跳过） |

## 3. 对外接口

```js
import { createClient } from './api/client.js'
import { createViewportLoader } from './api/viewport-loader.js'

const client = createClient({ url: 'ws://127.0.0.1:8765' })
await client.connect()                      // 建连；失败 reject 并进入 closed
await client.request('query_range', job)    // 按 id 配对；失败抛带 code / detail 的 Error
client.on('hello', handler)                 // 订阅服务端事件（无 id 的消息）
client.onState(handler)                     // 连接状态：idle / connecting / open / closed
client.close()                              // 页面卸载时显式关闭

// 所有数据请求都从这里出去：每帧最多一次，只保留最新视口
const loader = createViewportLoader({ request, onData, onError })
loader.schedule({ series: ['温度'], x0: 0, x1: 400, resolution: 1920 })
loader.cancel()                             // 作废在途请求（关数据源、卸载时）
```

| 项 | 约定 |
| --- | --- |
| 请求与响应的配对 | 按 `id`；**有 `id` 的是响应，没有的是服务端事件** |
| 响应迟到 | 代次作废后直接丢弃，**不覆盖新数据** |
| 失败响应 | 还原成 `Error`，保留 `code` 与 `detail`（契约违规带字段路径） |
| 断线 | 在途请求全部 reject 并进入 `closed`，**不留"界面停在加载中"的状态** |
| 重连 | **手动**（界面上的"重新连接"）。自动重连策略待定（C4） |
| 文案 | 本模块不产生界面文案，只给 `code`；显示由 UI 按文案表映射 |

## 4. 依赖规则

| | |
| --- | --- |
| 可以依赖 | 契约（消息结构） |
| **禁止依赖** | UI 组件、渲染器 |

## 5. 扩展点

新增消息类型 = 登记清单 + 加发送或处理逻辑。

## 6. 本模块的硬规则

1. **必须实现按帧节流**：数据请求走 `requestAnimationFrame`，**每帧最多一次**。
2. **必须实现代次作废**：请求带单调递增代次号，响应回来时若已有更新的请求，**直接丢弃旧响应**。
   - 反例：在每个 `mousemove` / `wheel` 事件里直接发请求 → **请求风暴**，交互反而更卡。
3. **连接状态必须可见**：断线要有明确提示与重连策略，不得静默失败。
4. **不得发送未登记的消息类型。**

## 7. 已知的坑

| 坑 | 现象 | 应对 |
| --- | --- | --- |
| **请求风暴** | 连续缩放时后端堆积，响应回来时数据已过期 | 已做：`viewport-loader.js` 按帧节流 + 代次作废，用例覆盖 |
| 响应顺序错乱 | 旧数据覆盖新数据，图形跳回 | 已做：代次校验，旧代次响应直接丢 |
| 断线后静默 | 界面看似正常但不再更新 | 已做：状态可见（`onState`）+ 在途请求失败；自动重连待定（C4） |
| 页面关闭未清理连接 | 后端残留连接 | 已做：组件卸载时 `loader.cancel()` + `client.close()` |
| 在事件回调里直接发请求 | 越缩放越卡 | 事件只更新视口状态，请求一律走 `schedule()` |

## 8. 相关

- 协议全文：[protocol.md](../protocol.md)
- 后端侧：[server.md](server.md)
- 示例代码要求：[guides/ai-coding-rules.md](../guides/ai-coding-rules.md)
