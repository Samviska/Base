// 渲染器交互用例：事件真的接上了吗、滚轮真的改变了视口吗。
//
// 为什么必须有这份用例：曾经 `zoomRange` 的字段名不匹配（拿 {x0, x1} 当 {lo, hi}），
// NaN 参与比较恒为 false —— 滚轮完全没反应，却不报任何错，
// 而当时的纯函数用例全绿。**光有正确的算法不够，事件路径必须被真正跑一遍。**
//
// 这里用最小假 DOM：canvas、ResizeObserver、requestAnimationFrame 全部 stub。

import assert from 'node:assert/strict'
import test from 'node:test'

import { createRenderer, zoomRange } from '../renderers/builtin/line.js'

const SIZE = { width: 800, height: 400 }
const MARGIN_LEFT = 60
const MARGIN_TOP = 14
const MARGIN_BOTTOM = 30

function fakeContext(record) {
  let stroke = ''
  return {
    // 每次绘制都从 clearRect 开始，因此它也是"清空上一次记录"的时机
    clearRect() {
      record.length = 0
    },
    fillRect() {},
    beginPath() {},
    moveTo(x, y) {
      record.push(['move', x, y, stroke])
    },
    lineTo(x, y) {
      record.push(['line', x, y, stroke])
    },
    stroke() {},
    fillText() {},
    setTransform() {},
    setLineDash() {},
    measureText: (text) => ({ width: String(text).length * 6 }),
    fillStyle: '',
    get strokeStyle() {
      return stroke
    },
    set strokeStyle(value) {
      stroke = value
    },
    lineWidth: 1,
    font: '',
    textAlign: '',
  }
}

function setupDom() {
  const record = []
  const listeners = new Map()
  const frames = []
  const canvas = {
    style: {},
    width: SIZE.width,
    height: SIZE.height,
    getContext: () => fakeContext(record),
    addEventListener: (type, handler) => listeners.set(type, handler),
    removeEventListener: (type) => listeners.delete(type),
    setPointerCapture() {},
    releasePointerCapture() {},
    hasPointerCapture: () => false,
    remove() {},
  }
  globalThis.ResizeObserver = class {
    observe() {}
    disconnect() {}
  }
  // 必须**异步**语义：同步执行会让 requestDraw 里"赋值 frameId"发生在回调之后，
  // 于是 frameId 永远非 0、后续重绘全被挡掉——真实浏览器不是这样
  globalThis.requestAnimationFrame = (callback) => {
    frames.push(callback)
    return frames.length
  }
  globalThis.cancelAnimationFrame = () => {}

  const container = {
    ownerDocument: { createElement: () => canvas },
    appendChild() {},
    getBoundingClientRect: () => SIZE,
  }
  const flush = () => {
    while (frames.length) frames.shift()()
  }
  return { record, listeners, canvas, container, flush }
}

function wheel(overrides = {}) {
  return {
    offsetX: 400,
    offsetY: 200,
    deltaY: -100,
    shiftKey: false,
    preventDefault() {},
    ...overrides,
  }
}

function wheelDown(overrides = {}) {
  return wheel({ deltaY: 100, ...overrides })
}

// 绘制记录里**数据折线**的纵向跨度：纵轴被放大时它应该变大。
// 必须按颜色筛掉网格线——网格竖线正好是整幅绘图区的高度，会把效果完全淹没。
const SERIES_COLOR = '#1e88e5'

function dataYs(record) {
  return record
    .filter(([kind, , , color]) => kind === 'line' && color === SERIES_COLOR)
    .map(([, , y]) => y)
}

function paintedSpanY(record) {
  const ys = dataYs(record)
  return ys.length ? Math.max(...ys) - Math.min(...ys) : 0
}

function paintedCenterY(record) {
  const ys = dataYs(record)
  return ys.length ? (Math.max(...ys) + Math.min(...ys)) / 2 : 0
}

function mounted() {
  const dom = setupDom()
  const renderer = createRenderer({ container: dom.container, options: {} })
  renderer.mount()
  renderer.setData({
    aggregated: false,
    series: [{ name: 's', x: [0, 1, 2], ymin: [0, 10, 20], ymax: [0, 10, 20] }],
  })
  renderer.setViewport({ x0: 0, x1: 2 })
  dom.flush()
  return { dom, renderer }
}

test('绘图区滚轮发出 zoom 事件，横轴被缩窄', () => {
  const { dom, renderer } = mounted()
  const zooms = []
  renderer.on('zoom', (view) => zooms.push(view))

  dom.listeners.get('wheel')(wheel())

  assert.equal(zooms.length, 1, '滚轮没有产生 zoom 事件')
  const [view] = zooms
  assert.ok(view.x1 - view.x0 < 2, `横轴没有被缩窄：${JSON.stringify(view)}`)
  assert.ok(view.x0 < view.x1)
})

test('绘图区滚轮向下是放大范围（缩小图形）', () => {
  const { dom, renderer } = mounted()
  const zooms = []
  renderer.on('zoom', (view) => zooms.push(view))

  dom.listeners.get('wheel')(wheelDown())

  assert.equal(zooms.length, 1)
  assert.ok(zooms[0].x1 - zooms[0].x0 > 2, '向下滚动没有放大范围')
})

test('纵轴带滚轮只缩放纵轴：不发 zoom 事件，但画面被拉伸', () => {
  const { dom, renderer } = mounted()
  const zooms = []
  renderer.on('zoom', (view) => zooms.push(view))

  const before = paintedSpanY(dom.record)
  assert.ok(before > 0, '前置条件：数据已经画出来了')

  dom.listeners.get('wheel')(wheel({ offsetX: MARGIN_LEFT - 20 }))
  dom.flush()
  const after = paintedSpanY(dom.record)

  assert.equal(zooms.length, 0, '缩放纵轴不该触发数据请求')
  assert.ok(after > before * 1.1, `纵轴没有被拉伸：${before} -> ${after}`)
})

test('双击恢复纵轴自动适应', () => {
  const { dom } = mounted()
  const before = paintedSpanY(dom.record)

  dom.listeners.get('wheel')(wheel({ offsetX: MARGIN_LEFT - 20 }))
  dom.flush()
  const zoomed = paintedSpanY(dom.record)
  assert.ok(zoomed > before * 1.1, '前置条件：纵轴已被缩放')

  dom.listeners.get('dblclick')({})
  dom.flush()
  assert.equal(paintedSpanY(dom.record), before, '双击没有恢复自动适应')
})

test('Shift + 绘图区滚轮缩放纵轴', () => {
  const { dom, renderer } = mounted()
  const zooms = []
  renderer.on('zoom', (view) => zooms.push(view))
  const before = paintedSpanY(dom.record)

  dom.listeners.get('wheel')(wheel({ shiftKey: true }))
  dom.flush()

  assert.equal(zooms.length, 0)
  assert.ok(paintedSpanY(dom.record) > before * 1.1)
})

test('底部横轴带滚轮一样缩放横轴', () => {
  const { dom, renderer } = mounted()
  const zooms = []
  renderer.on('zoom', (view) => zooms.push(view))

  const axisBandY = MARGIN_TOP + (SIZE.height - MARGIN_TOP - MARGIN_BOTTOM) + 10
  dom.listeners.get('wheel')(wheel({ offsetY: axisBandY }))

  assert.equal(zooms.length, 1)
  assert.ok(zooms[0].x1 - zooms[0].x0 < 2)
})

test('光标提示当前能缩放哪条轴', () => {
  const { dom } = mounted()

  dom.listeners.get('pointermove')({ offsetX: MARGIN_LEFT - 20, offsetY: 200 })
  assert.equal(dom.canvas.style.cursor, 'ns-resize')

  dom.listeners.get('pointermove')({ offsetX: 400, offsetY: 390 })
  assert.equal(dom.canvas.style.cursor, 'ew-resize')

  dom.listeners.get('pointermove')({ offsetX: 400, offsetY: 200 })
  assert.equal(dom.canvas.style.cursor, 'crosshair')
})

test('zoomRange 参数不对就抛错，不要静默失效', () => {
  // 就是这条：把 {x0, x1} 当 {lo, hi} 传进来时，必须当场炸，而不是让滚轮悄悄失灵
  assert.throws(() => zoomRange({ x0: 0, x1: 1 }, 1.1, 0.5), TypeError)
  assert.throws(() => zoomRange({ lo: 0, hi: 1 }, 1.1, Number.NaN), TypeError)
})

test('缩到极限不再发出 zoom 事件', () => {
  const { dom, renderer } = mounted()
  const zooms = []
  renderer.on('zoom', (view) => zooms.push(view))

  for (let i = 0; i < 400; i += 1) dom.listeners.get('wheel')(wheel())
  const last = zooms[zooms.length - 1]

  assert.ok(zooms.length > 0)
  assert.ok(last.x1 > last.x0, '视口跨度不能变成 0 或负数')
})

test('绘图区拖拽平移横轴', () => {
  const { dom, renderer } = mounted()
  const pans = []
  renderer.on('pan', (view) => pans.push(view))

  dom.listeners.get('pointerdown')({ offsetX: 400, offsetY: 200, pointerId: 1 })
  dom.listeners.get('pointermove')({ offsetX: 460, offsetY: 200, pointerId: 1 })

  assert.equal(pans.length, 1, '拖拽没有产生 pan 事件')
  assert.ok(pans[0].x0 < 0, `向右拖拽应让视口左移：${JSON.stringify(pans[0])}`)
})

test('拖出画布不中断拖拽', () => {
  // 以前这里挂了 pointerleave，指针一离开画布就把拖拽清掉——拖快一点就"拖不动了"
  const { dom, renderer } = mounted()
  const pans = []
  renderer.on('pan', (view) => pans.push(view))

  dom.listeners.get('pointerdown')({ offsetX: 400, offsetY: 200, pointerId: 1 })
  dom.listeners.get('pointermove')({ offsetX: 460, offsetY: 200, pointerId: 1 })
  dom.listeners.get('pointermove')({ offsetX: 900, offsetY: 600, pointerId: 1 })

  assert.equal(pans.length, 2, '指针移出画布后拖拽被中断了')
})

test('纵轴带上拖拽平移纵轴：跨度不变、位置移动', () => {
  const { dom } = mounted()
  const before = paintedCenterY(dom.record)
  const span = paintedSpanY(dom.record)
  const drawn = dataYs(dom.record).length

  dom.listeners.get('pointerdown')({ offsetX: 20, offsetY: 200, pointerId: 1 })
  dom.listeners.get('pointermove')({ offsetX: 20, offsetY: 240, pointerId: 1 })
  dom.flush()

  const moved = paintedSpanY(dom.record)
  // 平移不改跨度，但像素换算会带来 1e-14 级的浮点误差
  assert.ok(
    Math.abs(moved - span) < 1e-9,
    `平移不该改变跨度：${span}（${drawn} 点）-> ${moved}（${dataYs(dom.record).length} 点）`,
  )
  assert.ok(paintedCenterY(dom.record) > before, '向下拖拽应让图形下移')
})

test('双击重置：只拖拽过横轴也能一键回全览', () => {
  const dom = setupDom()
  const renderer = createRenderer({ container: dom.container, options: { fullRange: [0, 2] } })
  renderer.mount()
  renderer.setData({
    aggregated: false,
    series: [{ name: 's', x: [0, 1, 2], ymin: [0, 10, 20], ymax: [0, 10, 20] }],
  })
  renderer.setViewport({ x0: 0, x1: 2 })
  dom.flush()

  const pans = []
  // 模拟 App 的行为：收到 pan 就更新视口，否则渲染器仍以为自己在全览状态
  renderer.on('pan', (view) => {
    pans.push(view)
    renderer.setViewport(view)
  })
  const zooms = []
  renderer.on('zoom', (view) => zooms.push(view))

  // 只拖拽横轴，不碰纵轴
  dom.listeners.get('pointerdown')({ offsetX: 400, offsetY: 200, pointerId: 1 })
  dom.listeners.get('pointermove')({ offsetX: 300, offsetY: 200, pointerId: 1 })
  dom.listeners.get('pointerup')({ offsetX: 300, offsetY: 200, pointerId: 1 })
  dom.flush()
  assert.equal(pans.length, 1, '前置条件：横轴已经平移过')

  // 关键：这里**没有**手动缩放过纵轴，双击同样要生效
  dom.listeners.get('dblclick')({})
  assert.deepEqual(zooms, [{ x0: 0, x1: 2 }], '双击没有回到完整范围')
})

test('已经在全览且纵轴自动时，双击不做事', () => {
  const dom = setupDom()
  const renderer = createRenderer({ container: dom.container, options: { fullRange: [0, 2] } })
  renderer.mount()
  renderer.setData({
    aggregated: false,
    series: [{ name: 's', x: [0, 1, 2], ymin: [0, 10, 20], ymax: [0, 10, 20] }],
  })
  renderer.setViewport({ x0: 0, x1: 2 })
  dom.flush()

  const zooms = []
  renderer.on('zoom', (view) => zooms.push(view))
  dom.listeners.get('dblclick')({})

  assert.deepEqual(zooms, [])
})
