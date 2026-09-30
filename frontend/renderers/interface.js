// 渲染器接口约定。
//
// 接口只认两样东西：**契约数据 + 一个挂载容器**，不得引用 Vue 或任何 UI 框架——
// 一旦绑上框架，"渲染器可整块替换"就作废，所有渲染插件（含第三方）一起失效（D3）。
//
// 数据入口是**绘制数据**（后端聚合后的 min/max 对），不是原始点：
// 渲染器拿不到全量数据，这是分层纪律的一部分。

// 画布内的交互事件。mark-add / mark-remove 属第 6 批（标注）
export const VIEW_EVENTS = ['zoom', 'pan', 'mark-add', 'mark-remove', 'hover']

// 事件 payload：zoom / pan 都是 { x0, x1 }（数据坐标），由 UI 决定要不要据此请求数据。
// hover 是 { x, pixel }。
//
// resetView()：把视图复位（纵轴回自动适应、横轴回数据完整范围），
// 与"双击画布"是同一个动作——界面上的「全览」按钮调它，行为不会与双击分叉。
const REQUIRED_METHODS = [
  'mount',
  'unmount',
  'setData',
  'appendData',
  'setViewport',
  'setAnnotations',
  'resetView',
  'on',
]

export function assertRenderer(renderer) {
  const missing = REQUIRED_METHODS.filter((name) => typeof renderer?.[name] !== 'function')
  if (missing.length) {
    throw new TypeError(`渲染器不符合接口，缺少方法：${missing.join(', ')}`)
  }
  return renderer
}
