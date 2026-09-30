// 按帧节流 + 代次作废的用例（protocol.md §4 的硬规则）。
//
// 用假帧驱动，不依赖浏览器：这段逻辑最容易写成"每个 mousemove 发一次请求"，
// 而那种错误在真机上表现为"越缩放越卡"，很难回头定位。

import assert from 'node:assert/strict'
import test from 'node:test'

import { createViewportLoader } from '../api/viewport-loader.js'

// 假 rAF：手动 flush，测试因此不需要计时器
function fakeFrame() {
  let pending = new Map()
  let nextId = 0
  return {
    raf(callback) {
      nextId += 1
      pending.set(nextId, callback)
      return nextId
    },
    cancelRaf(handle) {
      pending.delete(handle)
    },
    flush() {
      const callbacks = [...pending.values()]
      pending.clear()
      callbacks.forEach((callback) => callback())
    },
  }
}

function tick() {
  return new Promise((resolve) => setImmediate(resolve))
}

test('同一帧内多次 schedule 只发一次请求，且用最后一次的视口', async () => {
  const frame = fakeFrame()
  const sent = []
  const loader = createViewportLoader({
    raf: frame.raf,
    cancelRaf: frame.cancelRaf,
    request: async (job) => {
      sent.push(job)
      return { aggregated: false, series: [] }
    },
    onData: () => {},
    onError: () => {},
  })

  loader.schedule({ x0: 0, x1: 1 })
  loader.schedule({ x0: 0, x1: 2 })
  loader.schedule({ x0: 0, x1: 3 })
  frame.flush()
  await tick()

  assert.equal(sent.length, 1)
  assert.equal(sent[0].x1, 3)
})

test('旧代次的响应被丢弃，不覆盖新数据', async () => {
  const frame = fakeFrame()
  const resolvers = []
  const received = []
  const loader = createViewportLoader({
    raf: frame.raf,
    cancelRaf: frame.cancelRaf,
    request: () => new Promise((resolve) => resolvers.push(resolve)),
    onData: (payload) => received.push(payload),
    onError: () => {},
  })

  loader.schedule({ x0: 0, x1: 1 })
  frame.flush()
  loader.schedule({ x0: 0, x1: 2 })
  frame.flush()

  resolvers[1]({ aggregated: true, tag: 'new' })
  resolvers[0]({ aggregated: true, tag: 'old' })
  await tick()

  assert.deepEqual(received, [{ aggregated: true, tag: 'new' }])
})

test('cancel 之后在途响应不再回调', async () => {
  const frame = fakeFrame()
  let resolveRequest = null
  const received = []
  const loader = createViewportLoader({
    raf: frame.raf,
    cancelRaf: frame.cancelRaf,
    request: () => new Promise((resolve) => (resolveRequest = resolve)),
    onData: (payload) => received.push(payload),
    onError: () => {},
  })

  loader.schedule({ x0: 0, x1: 1 })
  frame.flush()
  loader.cancel()
  resolveRequest({ aggregated: false })
  await tick()

  assert.deepEqual(received, [])
})

test('错误也按代次过滤，并且只有最新一次的错误会被上报', async () => {
  const frame = fakeFrame()
  const failures = []
  const resolvers = []
  const loader = createViewportLoader({
    raf: frame.raf,
    cancelRaf: frame.cancelRaf,
    request: () => new Promise((_, reject) => resolvers.push(reject)),
    onData: () => {},
    onError: (error) => failures.push(error.message),
  })

  loader.schedule({ x0: 0, x1: 1 })
  frame.flush()
  loader.schedule({ x0: 0, x1: 2 })
  frame.flush()

  resolvers[0](new Error('过期请求失败'))
  resolvers[1](new Error('最新请求失败'))
  await tick()

  assert.deepEqual(failures, ['最新请求失败'])
})

test('flush 之后可以继续调度新的请求', async () => {
  const frame = fakeFrame()
  const sent = []
  const loader = createViewportLoader({
    raf: frame.raf,
    cancelRaf: frame.cancelRaf,
    request: async (job) => {
      sent.push(job.x1)
      return { aggregated: false, series: [] }
    },
    onData: () => {},
    onError: () => {},
  })

  loader.schedule({ x0: 0, x1: 1 })
  frame.flush()
  await tick()
  loader.schedule({ x0: 0, x1: 5 })
  frame.flush()
  await tick()

  assert.deepEqual(sent, [1, 5])
})
