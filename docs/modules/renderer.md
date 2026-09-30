# 模块：渲染器（Renderer）

## 1. 一句话职责

把**绘制数据**（后端聚合后的点）画到画布上，并处理画布内的交互。

**不负责**：读文件、滤波、聚合、界面面板、插件发现。
这些分别属于[数据源](source.md)、[滤波](filter.md)、[聚合](aggregate.md)、[UI 外壳](ui-shell.md)、[后端核心](core.md)。

## 2. 代码位置

| 内容 | 路径 |
| --- | --- |
| 接口约定 | `frontend/renderers/interface.js` |
| 内置折线图（Canvas 2D，无框架） | `frontend/renderers/builtin/line.js` |
| 内置柱状图 | 待做（第 6 批） |
| 使用者 / 第三方插件 | `plugins/renderers/` |
| 用例 | `frontend/tests/renderer-interface.test.js` |

## 3. 对外接口

```js
const renderer = createRenderer({ container, options: { axes } })

renderer.mount() / unmount()
renderer.setData(payload)        // 整体替换：payload 就是 M6 query_range 的响应
renderer.appendData(chunk)       // 追加同名序列的数据（实时推送将来走这里）
renderer.setViewport({ x0, x1 }) // 数据坐标
renderer.setAnnotations(list)
renderer.on(event, handler)      // 返回取消订阅函数
```

| 事件 | payload | 含义 |
| --- | --- | --- |
| `zoom` | `{ x0, x1 }` | 用户滚轮缩放后的视口（已按鼠标位置为锚点换算） |
| `pan` | `{ x0, x1 }` | 拖拽平移后的视口 |
| `hover` | `{ x, pixel }` | 鼠标位置的数据坐标；**无人订阅时不算** |
| `mark-add` / `mark-remove` | — | 第 6 批（标注） |

`options.axes`：序列名 → 轴描述（[contract.md](../contract.md) §4.2），
渲染器据此判断轴类型是否认识，**不认识就降级绘制并在画布上标注**——不崩、不静默。

数据入口是**绘制数据**：聚合时 `x[i]` 是像素列中心，某列没有数据点时 `ymin[i]`、`ymax[i]` 为
`null`（不是 0），渲染器**跳过该列**。

接口只认两样东西：**契约数据** + **一个挂载容器**。

## 4. 依赖规则

| | |
| --- | --- |
| 可以依赖 | 契约的数据结构（[contract.md](../contract.md)）、浏览器原生 API（Canvas / WebGL / DOM） |
| **禁止依赖** | Vue 或任何 UI 框架、后端代码、其他渲染器的内部实现 |

**为什么禁止接口依赖 UI 框架**：接口一旦绑框架，"渲染器可整块替换"就失效——
将来换框架时，**所有渲染插件（含第三方）全部作废**。

**实现内部**可以用任何技术（包括框架、第三方图表库）；但**内置实现不用框架**，
原因是示范效应：内置实现是第三方渲染插件的模板，它用裸 Canvas，渲染生态就保持框架无关。

## 5. 扩展点

新增一个渲染器 = 在 `plugins/renderers/<名字>/` 放一个实现文件 + 一份 manifest。
见 [guides/add-renderer.md](../guides/add-renderer.md)。

## 6. 本模块的硬规则

1. **内置实现走与第三方完全相同的接口**，不得有特权通道。
   - 反例：内置折线图直接读核心内部状态，而插件必须通过参数拿数据。
   - 验证方式：删掉内置实现，核心应不报错，只是少一个选项。
2. **必须实现全部交互语义**（缩放、平移、标记），只换视觉形态。不满足者不合格。
3. **必须支持 `appendData`**，即使本期只被调用一次。
4. **不得为了画得快而丢弃极值**。可见点数超过像素列数时，按像素列取 min/max；
   禁止等间隔抽样、均值抽样。
5. **遇到不认识的轴类型要降级并标注**，不得崩溃、不得静默。
6. 画布内的附属元素（坐标轴、图例、tooltip、选区框）由渲染器自己用原生 DOM 创建，
   **不推给 UI 层**。
   - 原因：它们都依赖数据坐标与命中测试，推给 UI 层等于把渲染逻辑泄漏出去。

## 7. 已知的坑

| 坑 | 现象 | 应对 |
| --- | --- | --- |
| Canvas 不是响应式的 | 改了数据图没变，画面与状态不一致 | 数据变化后**显式重绘**。不要套用 Vue 的响应式思维 |
| 用 SVG 扛大数据 | 点一多就卡死 | 大数据一律 Canvas / WebGL |
| 请求风暴 | 连续缩放时每秒发出几十次数据请求，交互反而更卡 | 按帧节流 + 代次作废，见 [protocol.md](../protocol.md) §4 |
| 每帧重建全部绘图对象 | 高频重绘时 CPU 占用高 | 复用对象、只更新属性 |
| 坐标换算写在多处 | 缩放与 tooltip 的坐标对不上 | 坐标变换只在渲染器内部做一次，对外只暴露数据坐标 |
| 高分屏线条发虚 | Canvas 按 CSS 像素绘制，实际被拉伸 | 按 `devicePixelRatio` 放大画布并 `setTransform` 缩放 |
| 空列的 `null` 当成 0 画 | 图上出现一段不存在的平线 | 明确跳过 `ymin`/`ymax` 为 `null` 的列 |
| 缩放到跨度为 0 | 坐标换算除零，画面崩掉 | 视口最小跨度保护（`MIN_SPAN`） |

## 8. 相关

- 数据结构：[contract.md](../contract.md)
- 怎么加渲染器：[guides/add-renderer.md](../guides/add-renderer.md)
- 大数据显示策略与 UI 约束：[ARCHITECTURE.md](../ARCHITECTURE.md) §4、§5
- 决策背景：[DECISIONS.md](../DECISIONS.md) D3
