// 内置折线图（Canvas 2D）。**不引用任何 UI 框架**：内置实现是第三方插件的模板，
// 它用裸 Canvas，渲染生态才会保持框架无关（renderer.md §4）。
//
// 两种画法共用一条数据路径，由后端的 aggregated 标志决定，前端不为数据量分支：
//   aggregated=false → 折线（此时 ymin[i] === ymax[i]）
//   aggregated=true  → 每个像素列一条 min→max 的竖线段
//
// Canvas 不是响应式的：任何数据或视口变化都必须显式重绘（本文件统一走 requestDraw）。

const COLORS = ['#1e88e5', '#e53935', '#43a047', '#fb8c00', '#8e24aa', '#00acc1']
const MARGIN = { left: 60, right: 16, top: 14, bottom: 30 }
const TICKS = 4 // 每条轴的刻度段数

// 核心认识的四类轴；其余按数值轴降级显示并标注（contract.md §4.2）
const KNOWN_KINDS = new Set(['numeric', 'sequence', 'time', 'categorical'])
const MIN_SPAN = 1e-9 // 视口最小跨度：缩到 0 宽会让坐标换算除零

export { assertRenderer } from '../interface.js'

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

  const state = {
    series: [],
    aggregated: false,
    viewport: null,
    annotations: [],
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
    canvas.addEventListener('pointerdown', onPointerDown)
    canvas.addEventListener('pointermove', onPointerMove)
    canvas.addEventListener('pointerup', onPointerUp)
    canvas.addEventListener('pointercancel', onPointerUp)
    canvas.addEventListener('pointerleave', onPointerLeave)

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
      canvas.removeEventListener('pointerdown', onPointerDown)
      canvas.removeEventListener('pointermove', onPointerMove)
      canvas.removeEventListener('pointerup', onPointerUp)
      canvas.removeEventListener('pointercancel', onPointerUp)
      canvas.removeEventListener('pointerleave', onPointerLeave)
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
    const anchor = toDataX(event.offsetX, rect, view)
    const factor = event.deltaY > 0 ? 1.15 : 1 / 1.15
    const x0 = anchor - (anchor - view.x0) * factor
    const x1 = anchor + (view.x1 - anchor) * factor
    if (!(x1 - x0 > MIN_SPAN)) return
    emit('zoom', { x0, x1 })
  }

  function onPointerDown(event) {
    if (!state.viewport) return
    drag = { pixel: event.offsetX, view: { ...state.viewport } }
    canvas.setPointerCapture(event.pointerId)
  }

  function onPointerMove(event) {
    if (drag) {
      const rect = plotRect()
      const shift = ((event.offsetX - drag.pixel) / rect.width) * (drag.view.x1 - drag.view.x0)
      emit('pan', { x0: drag.view.x0 - shift, x1: drag.view.x1 - shift })
      return
    }
    // 没有订阅者就不算坐标：hover 跟着每次鼠标移动，白算没意义
    if (state.viewport && handlers.get('hover')?.size) {
      emit('hover', { x: toDataX(event.offsetX, plotRect(), state.viewport), pixel: event.offsetX })
    }
  }

  function onPointerUp(event) {
    if (!drag) return
    drag = null
    if (canvas.hasPointerCapture?.(event.pointerId)) canvas.releasePointerCapture(event.pointerId)
  }

  function onPointerLeave() {
    drag = null
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
    const range = yRange()
    const axis = currentXAxis()
    drawGrid(rect, view, range, axis)
    drawAxisTitles(rect, axis)

    for (const series of state.series) drawSeries(series, rect, view, range)
    for (const annotation of state.annotations) drawAnnotation(annotation, rect, view)
    drawNotices()
  }

  // 横轴描述来自契约（series[].x）。多序列共享 x 轴时，取第一条序列的作为整张图的横轴
  function currentXAxis() {
    const first = state.series[0]
    return (first && axes[first.name]) || {}
  }

  function yRange() {
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
      ctx.textAlign = 'center'
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
      ctx.fillStyle = '#546e7a'
      ctx.textAlign = 'right'
      ctx.fillText(title, rect.left + rect.width, cssHeight - 8)
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
    on,
  }
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
  if (abs >= 1e6 || (abs > 0 && abs < 1e-3)) return value.toExponential(1)
  if (abs >= 1000) return value.toFixed(0)
  if (abs >= 10) return value.toFixed(1)
  return value.toFixed(2)
}
