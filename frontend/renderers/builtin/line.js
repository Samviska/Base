// 内置折线图（Canvas 2D）。**不引用任何 UI 框架**：内置实现是第三方插件的模板，
// 它用裸 Canvas，渲染生态才会保持框架无关（renderer.md §4）。
//
// 两种画法共用一条数据路径，由后端的 aggregated 标志决定，前端不为数据量分支：
//   aggregated=false → 折线（此时 ymin[i] === ymax[i]）
//   aggregated=true  → 每个像素列一条 min→max 的竖线段
//
// Canvas 不是响应式的：任何数据或视口变化都必须显式重绘（本文件统一走 requestDraw）。

const COLORS = ['#1e88e5', '#e53935', '#43a047', '#fb8c00', '#8e24aa', '#00acc1']
const CURSOR_COLOR = '#d81b60'
// 绘图区边距：导出给内测脚本用——它要精确点在光标线上，靠猜坐标会点偏
export const LAYOUT = { left: 60, right: 16, top: 14, bottom: 44 }
const MARGIN = LAYOUT
const TICKS = 4 // 每条轴的刻度段数

// 核心认识的四类轴；其余按数值轴降级显示并标注（contract.md §4.2）
const KNOWN_KINDS = new Set(['numeric', 'sequence', 'time', 'categorical'])
const MIN_SPAN = 1e-9 // 视口最小跨度：缩到 0 宽会让坐标换算除零

export { assertRenderer } from '../interface.js'

import { snapToSeries } from '../cursor.js'

export function createRenderer({ container, options = {} }) {
  const axes = options.axes || {}
  const units = options.units || {}
  const handlers = new Map()

  let canvas = null
  let ctx = null
  let observer = null
  let frameId = 0
  let drag = null
  let cssWidth = 0
  let cssHeight = 0

  // 数据完整范围（来自 M3 摘要的 x_range）：双击"回到全览"要用它。
  // 渲染器拿不到全量数据，所以这个范围只能由上层传进来。
  const fullRange = Array.isArray(options.fullRange) ? options.fullRange : null

  const state = {
    series: [],
    aggregated: false,
    viewport: null,
    yView: null, // 手动缩放后的纵轴范围；null = 自动适应可见数据
    annotations: [],
    cursors: [], // [{ id, series, x }]：x 是数据坐标，y 由吸附得到
  }

  // ---------- 生命周期 ----------

  function mount() {
    canvas = container.ownerDocument.createElement('canvas')
    canvas.style.display = 'block'
    canvas.style.width = '100%'
    canvas.style.height = '100%'
    canvas.style.cursor = 'crosshair'
    canvas.style.touchAction = 'none'
    container.appendChild(canvas)
    ctx = canvas.getContext('2d')

    observer = new ResizeObserver(() => {
      resize()
      requestDraw()
    })
    observer.observe(container)

    canvas.addEventListener('wheel', onWheel, { passive: false })
    canvas.addEventListener('dblclick', onDoubleClick)
    canvas.addEventListener('pointerdown', onPointerDown)
    canvas.addEventListener('pointermove', onPointerMove)
    canvas.addEventListener('pointerup', onPointerUp)
    canvas.addEventListener('pointercancel', onPointerUp)
    // 不监听 pointerleave：指针捕获已经在工作，拖出画布不该中断这次拖拽——
    // 以前那次"拖拽突然没了"就是这么来的（拖快一点，指针出了边界）

    resize()
    requestDraw()
  }

  function unmount() {
    if (frameId) cancelAnimationFrame(frameId)
    frameId = 0
    observer?.disconnect()
    observer = null
    if (canvas) {
      canvas.removeEventListener('wheel', onWheel)
      canvas.removeEventListener('dblclick', onDoubleClick)
      canvas.removeEventListener('pointerdown', onPointerDown)
      canvas.removeEventListener('pointermove', onPointerMove)
      canvas.removeEventListener('pointerup', onPointerUp)
      canvas.removeEventListener('pointercancel', onPointerUp)
      canvas.remove()
    }
    canvas = null
    ctx = null
    handlers.clear()
  }

  // ---------- 数据入口 ----------

  function setData(payload) {
    state.aggregated = Boolean(payload?.aggregated)
    state.series = (payload?.series || []).map((series, index) => ({
      ...series,
      color: COLORS[index % COLORS.length],
    }))
    requestDraw()
  }

  function appendData(chunk) {
    // 追加语义：同名的序列往后接。静态加载走 setData，实时推送将来走这里
    state.aggregated = Boolean(chunk?.aggregated ?? state.aggregated)
    for (const incoming of chunk?.series || []) {
      const existing = state.series.find((item) => item.name === incoming.name)
      if (!existing) {
        state.series.push({ ...incoming, color: COLORS[state.series.length % COLORS.length] })
        continue
      }
      existing.x = existing.x.concat(incoming.x)
      existing.ymin = existing.ymin.concat(incoming.ymin)
      existing.ymax = existing.ymax.concat(incoming.ymax)
    }
    requestDraw()
  }

  function setViewport(range) {
    if (!range) return
    state.viewport = { x0: Number(range.x0), x1: Number(range.x1) }
    requestDraw()
  }

  function setAnnotations(list) {
    state.annotations = Array.isArray(list) ? list : []
    requestDraw()
  }

  function setCursors(list) {
    state.cursors = Array.isArray(list) ? list.map((item) => ({ ...item })) : []
    requestDraw()
  }

  function on(event, handler) {
    if (!handlers.has(event)) handlers.set(event, new Set())
    handlers.get(event).add(handler)
    return () => handlers.get(event)?.delete(handler)
  }

  function emit(event, payload) {
    handlers.get(event)?.forEach((handler) => handler(payload))
  }

  // ---------- 交互 ----------

  function onWheel(event) {
    const view = state.viewport
    if (!view) return
    event.preventDefault() // 否则整页跟着滚

    const rect = plotRect()
    const factor = event.deltaY > 0 ? 1.15 : 1 / 1.15
    const zone = zoneAt(event.offsetX, event.offsetY, rect)

    // 鼠标停在哪条轴上就缩放哪条：这是 TradingView / SciChart 一类软件的通行做法。
    // 绘图区内默认缩放横轴（横轴决定要向后端请求哪段数据），Shift 时改缩放纵轴。
    if (zone === 'y' || (zone === 'plot' && event.shiftKey)) {
      const next = zoomRange(paintRange(), factor, toDataY(event.offsetY, rect, paintRange()), MIN_SPAN)
      if (next) {
        state.yView = next
        requestDraw()
      }
      return
    }

    const next = zoomRange(
      { lo: view.x0, hi: view.x1 },
      factor,
      toDataX(event.offsetX, rect, view),
      MIN_SPAN,
    )
    if (next) emit('zoom', { x0: next.lo, x1: next.hi })
  }

  // 轴带：左侧留给纵轴，底部留给横轴。判断用 CSS 像素，与绘制时的边距一致
  function zoneAt(px, py, rect) {
    if (px < rect.left) return 'y'
    if (py > rect.top + rect.height) return 'x'
    return 'plot'
  }

  // 重置视图：纵轴回自动适应，横轴回**数据完整范围**（完整范围由上层经 options.fullRange 给）。
  // 双击与界面上的「全览」按钮走同一条路径，行为不会分叉。
  function resetView() {
    const view = state.viewport
    const yIsAuto = state.yView === null
    const xIsFull = !fullRange || !view || (view.x0 === fullRange[0] && view.x1 === fullRange[1])
    if (yIsAuto && xIsFull) return

    state.yView = null
    if (!xIsFull && fullRange) emit('zoom', { x0: fullRange[0], x1: fullRange[1] })
    requestDraw()
  }

  function onDoubleClick() {
    resetView()
  }

  function onPointerDown(event) {
    const view = state.viewport
    if (!view) return
    const rect = plotRect()

    // 光标线优先命中：它很细，命中范围给 6px——比"平移"更该被选中
    const hit = state.cursors.find(
      (cursor) => Math.abs(toPixelX(cursor.x, rect, view) - event.offsetX) <= 6,
    )
    if (hit) {
      drag = { zone: 'cursor', id: hit.id }
    } else {
      // 记下按下时在哪条轴上：轴带上拖拽平移该轴，绘图区内拖拽平移横轴
      drag = {
        zone: zoneAt(event.offsetX, event.offsetY, rect),
        pixel: event.offsetX,
        pixelY: event.offsetY,
        view: { ...view },
        range: paintRange(),
      }
    }
    canvas.setPointerCapture(event.pointerId)
  }

  function onPointerMove(event) {
    const rect = plotRect()
    const zone = state.viewport ? zoneAt(event.offsetX, event.offsetY, rect) : 'plot'
    const overCursor = state.viewport
      ? state.cursors.some(
          (cursor) => Math.abs(toPixelX(cursor.x, rect, state.viewport) - event.offsetX) <= 6,
        )
      : false
    canvas.style.cursor = drag ? 'grabbing' : overCursor ? 'col-resize' : cursorFor(zone, false)

    if (drag) {
      if (drag.zone === 'cursor') {
        moveCursor(drag.id, toDataX(event.offsetX, rect, state.viewport))
        return
      }
      if (drag.zone === 'y') {
        // 纵轴带上拖拽 = 平移纵轴（与在纵轴带上滚轮缩放配对）
        const shift = ((event.offsetY - drag.pixelY) / rect.height) * (drag.range.hi - drag.range.lo)
        state.yView = { lo: drag.range.lo + shift, hi: drag.range.hi + shift }
        requestDraw()
        return
      }
      const shift = ((event.offsetX - drag.pixel) / rect.width) * (drag.view.x1 - drag.view.x0)
      emit('pan', { x0: drag.view.x0 - shift, x1: drag.view.x1 - shift })
      return
    }
    // 没有订阅者就不算坐标：hover 跟着每次鼠标移动，白算没意义
    if (state.viewport && handlers.get('hover')?.size) {
      emit('hover', { x: toDataX(event.offsetX, rect, state.viewport), pixel: event.offsetX })
    }
  }

  function cursorFor(zone, dragging) {
    if (dragging) return 'grabbing'
    if (zone === 'y') return 'ns-resize'
    if (zone === 'x') return 'ew-resize'
    return 'crosshair'
  }

  // 拖动光标：吸附到最近的数据点，并把吸附结果报给界面
  function moveCursor(id, x) {
    const cursor = state.cursors.find((item) => item.id === id)
    if (!cursor) return
    const snap = snapToSeries(state.series, cursor.series, x)
    if (!snap) return
    cursor.x = snap.x
    cursor.series = snap.series
    emit('cursor-move', { id, ...snap })
    requestDraw()
  }

  function onPointerUp(event) {
    if (!drag) return
    drag = null
    if (canvas.hasPointerCapture?.(event.pointerId)) canvas.releasePointerCapture(event.pointerId)
  }

  // ---------- 绘制 ----------

  function requestDraw() {
    if (frameId || !ctx) return
    frameId = requestAnimationFrame(draw)
  }

  function resize() {
    const rect = container.getBoundingClientRect()
    const ratio = globalThis.devicePixelRatio || 1
    cssWidth = Math.max(1, rect.width)
    cssHeight = Math.max(1, rect.height)
    canvas.width = Math.round(cssWidth * ratio)
    canvas.height = Math.round(cssHeight * ratio)
    // 按设备像素比缩放，否则高分屏上线条发虚
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0)
  }

  function plotRect() {
    return {
      left: MARGIN.left,
      top: MARGIN.top,
      width: Math.max(1, cssWidth - MARGIN.left - MARGIN.right),
      height: Math.max(1, cssHeight - MARGIN.top - MARGIN.bottom),
    }
  }

  function draw() {
    frameId = 0
    if (!ctx) return
    ctx.clearRect(0, 0, cssWidth, cssHeight)
    ctx.fillStyle = '#ffffff'
    ctx.fillRect(0, 0, cssWidth, cssHeight)

    const view = state.viewport
    if (!view || !state.series.length) {
      drawText('打开一份数据后这里会显示波形', MARGIN.left, MARGIN.top + 18, '#90a4ae')
      return
    }

    const rect = plotRect()
    const range = paintRange()
    const axis = currentXAxis()
    drawGrid(rect, view, range, axis)
    drawAxisTitles(rect, axis)

    for (const series of state.series) drawSeries(series, rect, view, range)
    for (const annotation of state.annotations) drawAnnotation(annotation, rect, view)
    drawCursors(rect, view, range)
    drawNotices()
    drawZoomHint()
  }

  // 横轴描述来自契约（series[].x）。多序列共享 x 轴时，取第一条序列的作为整张图的横轴
  function currentXAxis() {
    const first = state.series[0]
    return (first && axes[first.name]) || {}
  }

  // 纵轴范围：默认自动适应可见数据；用户手动缩放过就用手动的那个
  function paintRange() {
    return state.yView ? { ...state.yView } : autoRange()
  }

  function autoRange() {
    let lo = Infinity
    let hi = -Infinity
    for (const series of state.series) {
      for (let i = 0; i < series.x.length; i += 1) {
        const low = series.ymin[i]
        const high = series.ymax[i]
        if (low !== null && low !== undefined) {
          if (low < lo) lo = low
          if (low > hi) hi = low
        }
        if (high !== null && high !== undefined) {
          if (high < lo) lo = high
          if (high > hi) hi = high
        }
      }
    }
    if (!Number.isFinite(lo) || !Number.isFinite(hi)) return { lo: 0, hi: 1 }
    if (lo === hi) return { lo: lo - 1, hi: hi + 1 } // 一条平线也要有高度
    const pad = (hi - lo) * 0.05
    return { lo: lo - pad, hi: hi + pad }
  }

  function drawGrid(rect, view, range, axis) {
    ctx.strokeStyle = '#eceff1'
    ctx.fillStyle = '#78909c'
    ctx.font = '11px system-ui, sans-serif'
    ctx.lineWidth = 1

    for (let i = 0; i <= TICKS; i += 1) {
      const px = rect.left + (rect.width * i) / TICKS
      ctx.beginPath()
      ctx.moveTo(px, rect.top)
      ctx.lineTo(px, rect.top + rect.height)
      ctx.stroke()
      const value = view.x0 + ((view.x1 - view.x0) * i) / TICKS
      // 首尾刻度贴边对齐，否则文字会溢出绘图区、压到轴标题上
      ctx.textAlign = i === 0 ? 'left' : i === TICKS ? 'right' : 'center'
      ctx.fillText(formatTick(value, axis), px, rect.top + rect.height + 16)
    }

    for (let i = 0; i <= TICKS; i += 1) {
      const py = rect.top + rect.height - (rect.height * i) / TICKS
      ctx.beginPath()
      ctx.moveTo(rect.left, py)
      ctx.lineTo(rect.left + rect.width, py)
      ctx.stroke()
      const value = range.lo + ((range.hi - range.lo) * i) / TICKS
      ctx.textAlign = 'right'
      ctx.fillText(formatNumber(value), rect.left - 6, py + 4)
    }
  }

  // 轴标题与纵轴单位都来自契约：数据说自己是什么，界面就显示什么
  function drawAxisTitles(rect, axis) {
    const first = state.series[0]
    const title = [axis.display_name || first?.name || '', axis.unit ? `（${axis.unit}）` : ''].join('')
    if (title) {
      // 左对齐：右端留给最后一个刻度标签，两者不再叠在一起
      ctx.fillStyle = '#546e7a'
      ctx.textAlign = 'left'
      ctx.fillText(title, rect.left, cssHeight - 10)
    }
    const unit = first ? units[first.name] : ''
    if (unit) {
      ctx.textAlign = 'left'
      ctx.fillText(`单位：${unit}`, MARGIN.left, 12)
    }
  }

  function drawSeries(series, rect, view, range) {
    ctx.strokeStyle = series.color
    ctx.lineWidth = 1
    ctx.beginPath()

    if (state.aggregated) {
      // 每列一条竖线段：极小与极大都画出来，尖峰因此必然可见
      ctx.beginPath()
      for (let i = 0; i < series.x.length; i += 1) {
        const x = series.x[i]
        if (!inView(x, view)) continue
        const low = series.ymin[i]
        const high = series.ymax[i]
        if (low === null || high === null) continue // 空列：没有数据，不画
        const px = toPixelX(x, rect, view)
        ctx.moveTo(px, toPixelY(low, rect, range))
        ctx.lineTo(px, toPixelY(high, rect, range))
      }
      ctx.stroke()

      // 再把各列中点连成折线。只有竖线时，每列点少的情况下波形看着像一片毛刺；
      // 中点线把趋势接起来，极值仍然由竖线表达——不丢任何东西
      ctx.beginPath()
      let linked = false
      for (let i = 0; i < series.x.length; i += 1) {
        const x = series.x[i]
        const low = series.ymin[i]
        const high = series.ymax[i]
        if (!inView(x, view) || low === null || high === null) {
          linked = false
          continue
        }
        const px = toPixelX(x, rect, view)
        const py = toPixelY((low + high) / 2, rect, range)
        if (linked) ctx.lineTo(px, py)
        else ctx.moveTo(px, py)
        linked = true
      }
      ctx.stroke()
    } else {
      // 折线：缺失值断线，不跨过去连
      let drawing = false
      for (let i = 0; i < series.x.length; i += 1) {
        const x = series.x[i]
        const low = series.ymin[i]
        if (!inView(x, view) || low === null || low === undefined) {
          drawing = false
          continue
        }
        const px = toPixelX(x, rect, view)
        const py = toPixelY(low, rect, range)
        if (drawing) ctx.lineTo(px, py)
        else ctx.moveTo(px, py)
        drawing = true
      }
    }
    ctx.stroke()
  }

  function drawAnnotation(annotation, rect, view) {
    // 第 5 批只画位置，编辑与命中测试属第 6 批
    ctx.strokeStyle = '#ff6d00'
    ctx.fillStyle = '#ff6d00'
    ctx.lineWidth = 1
    ctx.setLineDash([4, 3])
    const points = Array.isArray(annotation.x) ? annotation.x : [annotation.x]
    for (const value of points) {
      if (typeof value !== 'number' || !inView(value, view)) continue
      const px = toPixelX(value, rect, view)
      ctx.beginPath()
      ctx.moveTo(px, rect.top)
      ctx.lineTo(px, rect.top + rect.height)
      ctx.stroke()
    }
    ctx.setLineDash([])
  }

  // 测量光标：竖线 + 编号标签 + 与数据线的交点。
  // 交点吸附到最近的数据点；聚合模式下它就是该像素列的极值——
  // 界面会把这一点标出来，不让人误以为是原始采样值。
  function drawCursors(rect, view, range) {
    for (const [index, cursor] of state.cursors.entries()) {
      const snap = snapToSeries(state.series, cursor.series, cursor.x)
      if (!snap || !inView(snap.x, view)) continue
      const px = toPixelX(snap.x, rect, view)

      ctx.strokeStyle = CURSOR_COLOR
      ctx.lineWidth = 1
      ctx.setLineDash([3, 3])
      ctx.beginPath()
      ctx.moveTo(px, rect.top)
      ctx.lineTo(px, rect.top + rect.height)
      ctx.stroke()
      ctx.setLineDash([])

      ctx.fillStyle = CURSOR_COLOR
      ctx.fillRect(px - 9, rect.top, 18, 15)
      ctx.fillStyle = '#ffffff'
      ctx.font = '11px system-ui, sans-serif'
      ctx.textAlign = 'center'
      ctx.fillText(cursor.label || `C${index + 1}`, px, rect.top + 11)

      ctx.fillStyle = CURSOR_COLOR
      ctx.beginPath()
      ctx.arc(px, toPixelY(snap.y, rect, range), 3, 0, Math.PI * 2)
      ctx.fill()
    }
  }

  function drawNotices() {
    const notices = collectNotices()
    // 从 22 起步：左上角那一行留给纵轴单位
    let offset = 22
    for (const notice of notices) {
      ctx.fillStyle = '#fff8e1'
      const width = ctx.measureText(notice).width + 16
      ctx.fillRect(MARGIN.left, MARGIN.top + offset, width, 20)
      drawText(notice, MARGIN.left + 8, MARGIN.top + offset + 14, '#8d6e63')
      offset += 22
    }
  }

  // 降级必须说出来：静默降级会让人误判图形含义（contract.md §4.2）
  function collectNotices() {
    const notices = new Set()
    for (const [name, axis] of Object.entries(axes)) {
      if (axis?.kind && !KNOWN_KINDS.has(axis.kind)) {
        notices.add(`${name}：轴类型 ${axis.kind} 不认识，按数值方式显示`)
      }
      if (axis?.scale === 'log') {
        notices.add(`${name}：对数轴尚未实现，按线性方式显示`)
      }
    }
    return [...notices]
  }

  function drawText(text, x, y, color) {
    ctx.fillStyle = color
    ctx.font = '12px system-ui, sans-serif'
    ctx.textAlign = 'left'
    ctx.fillText(text, x, y)
  }

  // 手动缩放必须看得见，还得告诉人怎么退回去——否则图形含义会变得可疑
  function drawZoomHint() {
    if (!state.yView) return
    const text = '纵轴：手动缩放（双击恢复自动）'
    ctx.font = '12px system-ui, sans-serif'
    const width = ctx.measureText(text).width + 16
    const left = Math.max(MARGIN.left, cssWidth - width - 8)
    ctx.fillStyle = '#fff8e1'
    ctx.fillRect(left, MARGIN.top, width, 20)
    drawText(text, left + 8, MARGIN.top + 14, '#8d6e63')
  }

  // ---------- 坐标换算：只在渲染器内部做一次 ----------

  function toPixelX(x, rect, view) {
    return rect.left + ((x - view.x0) / (view.x1 - view.x0)) * rect.width
  }

  function toPixelY(y, rect, range) {
    return rect.top + rect.height - ((y - range.lo) / (range.hi - range.lo)) * rect.height
  }

  function toDataX(pixel, rect, view) {
    return view.x0 + ((pixel - rect.left) / rect.width) * (view.x1 - view.x0)
  }

  function toDataY(pixel, rect, range) {
    return range.lo + ((rect.top + rect.height - pixel) / rect.height) * (range.hi - range.lo)
  }

  function inView(x, view) {
    return typeof x === 'number' && x >= view.x0 && x <= view.x1
  }

  return {
    mount,
    unmount,
    setData,
    appendData,
    setViewport,
    setAnnotations,
    setCursors,
    resetView,
    on,
  }
}

// 以 anchor 为锚点缩放一个范围。返回 null 表示已缩到最小跨度，调用方应忽略本次操作。
//
// 参数不对时**抛错而不是返回 null**：曾经把 {x0, x1} 当成 {lo, hi} 传进来，
// NaN 参与比较恒为 false，滚轮就这样静默失灵了——这类错误必须立刻暴露。
export function zoomRange(range, factor, anchor, minSpan = 1e-9) {
  const lo = range?.lo
  const hi = range?.hi
  if (!Number.isFinite(lo) || !Number.isFinite(hi) || !Number.isFinite(anchor)) {
    throw new TypeError(
      `zoomRange 需要 {lo, hi} 与数值锚点，收到 ${JSON.stringify(range)} / ${anchor}`,
    )
  }
  const nextLo = anchor - (anchor - lo) * factor
  const nextHi = anchor + (hi - anchor) * factor
  if (!(nextHi - nextLo > minSpan)) return null
  return { lo: nextLo, hi: nextHi }
}

// 刻度怎么显示由**轴描述**决定：时间轴显示相对基准的偏移，序号轴显示整数。
// 这是"数据自描述"落到界面上的那一环——换一种数据，只要它按契约描述自己的轴，这里就不用改。
export function formatTick(value, axis = {}) {
  if (axis.kind === 'time' && axis.tick_format === 'offset_seconds') {
    const seconds = value / 1000
    return `${seconds >= 0 ? '+' : ''}${Number.isInteger(seconds) ? seconds : seconds.toFixed(1)}s`
  }
  if (axis.kind === 'sequence') return String(Math.round(value))
  return formatNumber(value)
}

function formatNumber(value) {
  if (!Number.isFinite(value)) return '-'
  const abs = Math.abs(value)
  // 刻度标签要能一眼读出来：六位数写成 882k，比 882134 好认
  if (abs >= 1e6) return `${(value / 1e6).toFixed(1)}M`
  if (abs >= 1e4) return `${Math.round(value / 1e3)}k`
  if (abs >= 1000) return value.toFixed(0)
  if (abs >= 10) return value.toFixed(1)
  return value.toFixed(2)
}
