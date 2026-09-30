// 与真后端的联通用例：验证前端通信层与后端协议**字段级**匹配。
//
// 默认跳过（`npm test` 不该依赖外部服务）。要跑它，先起后端再给地址：
//   .venv\Scripts\python.exe -m backend.server --port 8792
//   $env:BACKEND_URL = "ws://127.0.0.1:8792"; npm test
//
// 为什么值得单独测：前后端两侧的字段名必须完全一致（messages.md §5），
// 而这种错在浏览器里表现为"图不出来"，排查成本远高于一条断言。

import assert from 'node:assert/strict'
import test from 'node:test'

import { CLIENT_STATE, createClient } from '../api/client.js'

const BACKEND_URL = process.env.BACKEND_URL || ''
const skip = BACKEND_URL ? false : '需要真实后端：设置 BACKEND_URL 后再跑'

const EXAMPLE = 'contract/examples/example-basic.json'

test('连接后收到 hello，随后能打开文件并取到视口数据', { skip }, async () => {
  const client = createClient({ url: BACKEND_URL })
  const hello = new Promise((resolve) => client.on('hello', resolve))

  await client.connect()
  assert.equal(client.state, CLIENT_STATE.OPEN)

  const greeting = await hello
  assert.equal(greeting.protocol_version, '1.0')
  assert.match(greeting.backend_version, /^\d+\.\d+\.\d+$/)

  const summary = await client.request('open_file', { path: EXAMPLE })
  assert.deepEqual(
    summary.series.map((item) => item.name),
    ['温度', '状态计数'],
  )
  assert.deepEqual([0, 400], summary.series[0].x_range)

  const payload = await client.request('query_range', { x0: 0, x1: 400, resolution: 2 })
  assert.equal(payload.aggregated, true)
  assert.deepEqual([25.1, 26.0], payload.series[0].ymin)
  assert.deepEqual([25.3, 26.2], payload.series[0].ymax)

  client.close()
  assert.equal(client.state, CLIENT_STATE.CLOSED)
})

test('失败响应被还原成带错误码的异常', { skip }, async () => {
  const client = createClient({ url: BACKEND_URL })
  await client.connect()

  await assert.rejects(
    () => client.request('open_file', { path: '不存在的文件.json' }),
    (error) => error.code === 'FILE_NOT_FOUND',
  )

  await assert.rejects(
    () => client.request('open_file', { path: 'contract/examples/invalid-missing-unit.json' }),
    (error) => error.code === 'CONTRACT_VIOLATION' && error.detail.path === 'series[0]',
  )

  client.close()
})
