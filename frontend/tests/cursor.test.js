// 光标吸附的用例：它是"读数"的唯一来源，渲染器画交点与界面显示数值都用它。
//
// 最容易错的是聚合模式：此时前端拿到的是每像素列的 min/max，
// 不是原始采样点——返回的 aggregated 就是用来把这件事说出来的。

import assert from 'node:assert/strict'
import test from 'node:test'

import { nearestIndex, snapToSeries } from '../renderers/cursor.js'

function series(name, x, ymin, ymax = ymin) {
  return { name, x, ymin, ymax }
}

test('nearestIndex 找到最近的下标', () => {
  assert.equal(nearestIndex([0, 10, 20, 30], 14), 1)
  assert.equal(nearestIndex([0, 10, 20, 30], 16), 2)
  assert.equal(nearestIndex([0, 10, 20, 30], -5), 0)
  assert.equal(nearestIndex([0, 10, 20, 30], 999), 3)
  assert.equal(nearestIndex([], 1), -1)
})

test('snapToSeries 返回吸附点：原始点模式下 ymin 等于 ymax', () => {
  const list = [series('a', [0, 1, 2], [5, 6, 7])]
  const snap = snapToSeries(list, 'a', 1.4)

  assert.equal(snap.series, 'a')
  assert.equal(snap.index, 1)
  assert.equal(snap.x, 1)
  assert.equal(snap.y, 6)
  assert.equal(snap.aggregated, false)
})

test('聚合模式下标出"这是像素列的极值"', () => {
  const list = [series('a', [0, 1, 2], [5, 6, 7], [9, 8, 7])]
  const snap = snapToSeries(list, 'a', 0.9)

  assert.equal(snap.x, 1)
  assert.equal(snap.ymin, 6)
  assert.equal(snap.ymax, 8)
  assert.equal(snap.y, 8, '取值取极大值，界面上会说明它来自聚合列')
  assert.equal(snap.aggregated, true)
})

test('找不到序列名时退回第一条序列', () => {
  const list = [series('a', [0, 1], [5, 6]), series('b', [0, 1], [7, 8])]
  assert.equal(snapToSeries(list, '不存在', 1).series, 'a')
})

test('没有数据时返回 null，不抛异常', () => {
  assert.equal(snapToSeries([], 'a', 1), null)
  assert.equal(snapToSeries(null, 'a', 1), null)
  assert.equal(snapToSeries([{ name: 'a', x: [] }], 'a', 1), null)
})

test('缺失值原样带出，不编造数值', () => {
  const list = [series('a', [0, 1], [5, null], [null, null])]
  const snap = snapToSeries(list, 'a', 1)
  assert.equal(snap.x, 1)
  assert.equal(snap.y, null)
})
