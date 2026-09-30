// 渲染器接口约定的用例。
//
// "接口不绑定 UI 框架"这条规则一旦破了，所有渲染插件（含第三方）作废，
// 而破法往往很安静：某个实现顺手 import 了框架。这里至少在接口层面把它钉住：
// 必需方法齐全、未挂载时也能安全接收数据。

import assert from 'node:assert/strict'
import test from 'node:test'

import { createRenderer, formatTick, zoomRange } from '../renderers/builtin/line.js'
import { VIEW_EVENTS, assertRenderer } from '../renderers/interface.js'

test('内置折线图满足渲染器接口约定', () => {
  const renderer = createRenderer({ container: {}, options: {} })
  assert.equal(assertRenderer(renderer), renderer)
})

test('缺少必需方法的实现会被拒绝', () => {
  assert.throws(() => assertRenderer({ mount() {} }), /缺少方法/)
})

test('未挂载时也能安全设置数据、视口与标注', () => {
  const renderer = createRenderer({ container: {}, options: { axes: { 温度: { kind: 'time' } } } })
  renderer.setData({
    aggregated: true,
    series: [{ name: '温度', x: [0, 1], ymin: [1, 2], ymax: [3, 4] }],
  })
  renderer.appendData({
    aggregated: true,
    series: [{ name: '温度', x: [2], ymin: [5], ymax: [6] }],
  })
  renderer.setViewport({ x0: 0, x1: 2 })
  renderer.setAnnotations([{ series: '温度', kind: 'point', x: 1 }])
})

test('事件订阅返回可用的取消函数', () => {
  const renderer = createRenderer({ container: {}, options: {} })
  const seen = []
  const off = renderer.on('zoom', (view) => seen.push(view))
  assert.equal(typeof off, 'function')
  off()
  assert.deepEqual(seen, [])
})

test('事件类型清单是接口的一部分', () => {
  assert.deepEqual(VIEW_EVENTS, ['zoom', 'pan', 'mark-add', 'mark-remove', 'hover'])
})

test('缩放以鼠标位置为锚点，缩到极限时返回 null', () => {
  // 锚点 50 在缩放前后落在同一个数据位置，这样"指着哪就放大哪"
  assert.deepEqual(zoomRange({ lo: 0, hi: 100 }, 0.5, 50), { lo: 25, hi: 75 })
  assert.deepEqual(zoomRange({ lo: 25, hi: 75 }, 2, 50), { lo: 0, hi: 100 })
  // 锚点在边缘时，另一侧被拉长
  assert.deepEqual(zoomRange({ lo: 0, hi: 100 }, 0.5, 0), { lo: 0, hi: 50 })
  assert.equal(zoomRange({ lo: 0, hi: 1 }, 1e-12, 0.5, 1e-9), null)
})

test('刻度按轴描述格式化：数据说自己是什么，就显示成什么', () => {
  assert.equal(formatTick(12.5, { kind: 'sequence' }), '13') // 序号轴给整数
  assert.equal(formatTick(0, { kind: 'sequence' }), '0')
  assert.equal(formatTick(12500, { kind: 'time', tick_format: 'offset_seconds' }), '+12.5s')
  assert.equal(formatTick(-1500, { kind: 'time', tick_format: 'offset_seconds' }), '-1.5s')
  assert.equal(formatTick(2000, { kind: 'time', tick_format: 'offset_seconds' }), '+2s')
  assert.equal(formatTick(250, {}), '250.0') // 没有轴描述时退回普通数值格式
})
