// 界面内测：用**真实浏览器**（系统 Edge）把"选日志 → 出图 → 交互"整条路走一遍。
//
// 为什么需要它：滚轮、指针拖拽、双击、Canvas 绘制在假 DOM 里测不出真行为——
// 之前三个 bug（滚轮静默失效、拖拽被中断、双击回不到全览）全是在这里才暴露的。
//
// 前置：后端与 dev server 已在跑（各一个终端）：
//   .venv\Scripts\python.exe -m backend.server
//   cd frontend; npm run dev
// 然后：cd frontend; npm run e2e
//
// 截图输出在 _local/e2e-*.png，供人工复核。

import { spawnSync } from 'node:child_process'
import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { chromium } from 'playwright'

const HERE = dirname(fileURLToPath(import.meta.url))
const FRONTEND = resolve(HERE, '..')
const ROOT = resolve(FRONTEND, '..')
const LOCAL = resolve(ROOT, '_local')
const WEB_URL = process.env.E2E_URL || 'http://127.0.0.1:5173'
const BACKEND_URL = process.env.E2E_BACKEND || 'ws://127.0.0.1:8765'
const SAMPLE_COUNT = 10000

const failures = []
let checks = 0

function check(condition, message) {
  checks += 1
  if (condition) {
    console.log(`  ✔ ${message}`)
    return true
  }
  failures.push(message)
  console.log(`  ✖ ${message}`)
  return false
}

// ---------- 造一份真格式的日志 ----------
// 包结构与真实设备一致：0x88 + 66 组 3 字节大端有符号 + 末尾 4 字节，不足用 80 80 80 补。
// 中间埋一个尖峰：聚合之后它必须还在（这是本项目的核心承诺）。
function makeJp18Log(count) {
  const bytes = []
  const spikeAt = Math.floor(count / 2)
  let written = 0
  while (written < count) {
    const inside = Math.min(66, count - written)
    bytes.push(0x88)
    for (let i = 0; i < 66; i += 1) {
      if (i >= inside) {
        bytes.push(0x80, 0x80, 0x80)
        continue
      }
      const index = written + i
      const value = index === spikeAt ? 900000 : Math.round(200000 * Math.sin(index / 250))
      bytes.push((value >> 16) & 0xff, (value >> 8) & 0xff, value & 0xff)
    }
    bytes.push(0x00, 0x02, 0x80, 0xa0)
    written += inside
  }
  return bytes.map((byte) => byte.toString(16).padStart(2, '0').toUpperCase()).join(' ')
}

// ---------- 页面读取小工具 ----------

async function text(page, testId) {
  return (await page.getByTestId(testId).innerText()).trim()
}

async function viewport(page) {
  const raw = await text(page, 'status-viewport')
  const match = raw.match(/([-0-9.eE+]+)\s*→\s*([-0-9.eE+]+)/)
  return match ? [Number(match[1]), Number(match[2])] : null
}

async function numberFrom(page, testId) {
  const match = (await text(page, testId)).match(/(\d+)/)
  return match ? Number(match[1]) : 0
}

// 数据总量（全量）与本次绘制点数必须分开看：聚合时后者远小于前者
function dataPoints(page) {
  return numberFrom(page, 'status-data-points')
}

function drawPoints(page) {
  return numberFrom(page, 'status-draw-points')
}

async function waitFor(predicate, timeout = 15000, interval = 120) {
  const deadline = Date.now() + timeout
  for (;;) {
    if (await predicate()) return true
    if (Date.now() > deadline) return false
    await new Promise((resolve) => setTimeout(resolve, interval))
  }
}

function near(a, b, tolerance = 1e-6) {
  return Math.abs(a - b) <= tolerance * Math.max(1, Math.abs(a), Math.abs(b))
}

// ---------- 主流程 ----------

async function main() {
  mkdirSync(LOCAL, { recursive: true })
  const logPath = resolve(LOCAL, 'e2e-jp18.txt')
  writeFileSync(logPath, makeJp18Log(SAMPLE_COUNT), 'utf8')
  console.log(`合成日志：${logPath}（${SAMPLE_COUNT} 个样本，含一个 900000 的尖峰）\n`)

  const browser = await chromium.launch({ channel: 'msedge' })
  const page = await browser.newPage({ viewport: { width: 1280, height: 820 } })

  // 页面上任何未捕获异常与控制台错误都要算失败：静默失效正是之前踩过的坑
  page.on('pageerror', (error) => {
    failures.push(`页面异常：${error.message}`)
    console.log(`  ✖ 页面异常：${error.message}`)
  })
  page.on('console', (message) => {
    if (message.type() !== 'error') return
    const url = message.location()?.url || ''
    if (url.includes('favicon')) return // 缺图标与功能无关
    failures.push(`控制台错误：${message.text()}`)
    console.log(`  ✖ 控制台错误：${message.text()}`)
  })

  console.log('【1】连接与插件清单')
  await page.goto(`${WEB_URL}/?backend=${encodeURIComponent(BACKEND_URL)}`, {
    waitUntil: 'domcontentloaded',
  })
  const connected = await waitFor(async () => (await text(page, 'status-connection')).includes('已连接'))
  check(connected, '页面连上后端')
  const options = await page.getByTestId('source-plugin').locator('option').allInnerTexts()
  check(options.some((item) => item.includes('JP18')), `插件下拉里有 JP18（实际：${options.join(' / ')}`)

  console.log('\n【2】打开日志（JP18 插件 + 采样率 250）')
  await page.getByTestId('source-plugin').selectOption('jp18-ecg')
  await page.getByTestId('file-path').fill(logPath)
  await page.getByTestId('param-sample_rate').fill('250')
  await page.getByTestId('open-file').click()

  const loaded = await waitFor(async () => (await dataPoints(page)) === SAMPLE_COUNT)
  check(loaded, `数据总量 ${SAMPLE_COUNT}（实际 ${await dataPoints(page)}）`)
  const drawnAll = await drawPoints(page)
  check(
    drawnAll > 600 && drawnAll < 2500,
    `全览时本次绘制点数≈画布宽度（实际 ${drawnAll}，不是 ${SAMPLE_COUNT}——聚合本来就该这样）`,
  )

  const full = await viewport(page)
  check(full !== null, `读到视口：${JSON.stringify(full)}`)
  // 250 Hz、10000 点 → 0 ~ 39996 ms
  check(full !== null && near(full[0], 0, 1e-9) && near(full[1], 39996, 1e-6), '初始视口是数据完整范围')
  check((await text(page, 'status-aggregated')).includes('聚合'), '全览时标注为聚合显示')
  await page.screenshot({ path: resolve(LOCAL, 'e2e-01-全览.png') })

  const box = await page.getByTestId('chart').boundingBox()
  const plot = { x: box.x + box.width * 0.55, y: box.y + box.height * 0.45 }
  const yAxisBand = { x: box.x + 20, y: box.y + box.height * 0.45 }
  const xAxisBand = { x: box.x + box.width * 0.55, y: box.y + box.height - 10 }

  console.log('\n【3】绘图区滚轮 = 缩放横轴')
  const beforeZoom = await viewport(page)
  await page.mouse.move(plot.x, plot.y)
  await page.mouse.wheel(0, -240)
  await page.waitForTimeout(400)
  const afterZoom = await viewport(page)
  check(
    afterZoom[1] - afterZoom[0] < beforeZoom[1] - beforeZoom[0] - 1,
    `滚轮缩小了横轴范围：${(beforeZoom[1] - beforeZoom[0]).toFixed(0)} → ${(afterZoom[1] - afterZoom[0]).toFixed(0)}`,
  )

  console.log('\n【4】左侧纵轴带滚轮 = 只缩放纵轴')
  const viewBeforeY = await viewport(page)
  await page.mouse.move(yAxisBand.x, yAxisBand.y)
  await page.mouse.wheel(0, -240)
  await page.waitForTimeout(300)
  const viewAfterY = await viewport(page)
  check(
    near(viewBeforeY[0], viewAfterY[0], 1e-9) && near(viewBeforeY[1], viewAfterY[1], 1e-9),
    `纵轴缩放没有动横轴：${JSON.stringify(viewAfterY)}`,
  )
  await page.screenshot({ path: resolve(LOCAL, 'e2e-02-纵轴缩放.png') })

  console.log('\n【5】绘图区拖拽 = 平移横轴（拖到画布外也不该中断）')
  const beforePan = await viewport(page)
  await page.mouse.move(plot.x, plot.y)
  await page.mouse.down()
  await page.mouse.move(plot.x - 200, plot.y, { steps: 8 })
  await page.mouse.move(box.x + box.width + 120, box.y + box.height + 60, { steps: 4 })
  await page.mouse.up()
  await page.waitForTimeout(400)
  const afterPan = await viewport(page)
  check(
    !near(beforePan[0], afterPan[0], 1e-6),
    `拖拽平移了横轴：${beforePan[0].toFixed(0)} → ${afterPan[0].toFixed(0)}`,
  )

  console.log('\n【6】双击 = 回到全览')
  await page.mouse.dblclick(plot.x, plot.y)
  await page.waitForTimeout(500)
  const afterReset = await viewport(page)
  check(near(afterReset[0], 0, 1e-9) && near(afterReset[1], 39996, 1e-6), `双击回到完整范围：${JSON.stringify(afterReset)}`)
  await page.screenshot({ path: resolve(LOCAL, 'e2e-03-双击复位.png') })

  console.log('\n【7】「全览」按钮')
  await page.mouse.move(plot.x, plot.y)
  await page.mouse.wheel(0, -240)
  await page.waitForTimeout(300)
  await page.getByTestId('reset-view').click()
  await page.waitForTimeout(500)
  const afterButton = await viewport(page)
  check(near(afterButton[0], 0, 1e-9) && near(afterButton[1], 39996, 1e-6), `按钮回到完整范围：${JSON.stringify(afterButton)}`)

  console.log('\n【8】放大到点数少于分辨率 = 回到原始点')
  // 视口收窄到约 200 ms（50 个样本），远少于画布宽度
  await page.mouse.move(plot.x, plot.y)
  for (let i = 0; i < 40; i += 1) await page.mouse.wheel(0, -240)
  const becameRaw = await waitFor(async () => (await text(page, 'status-aggregated')).includes('原始点'), 8000)
  check(becameRaw, `放大后标注为原始点显示（${await text(page, 'status-aggregated')}）`)
  const zoomed = await viewport(page)
  check(zoomed[1] - zoomed[0] < 2000, `视口已收窄：${(zoomed[1] - zoomed[0]).toFixed(2)} ms`)
  const fewPoints = await drawPoints(page)
  check(fewPoints < 400, `原始点模式下绘制点数变小（实际 ${fewPoints}）`)
  await page.screenshot({ path: resolve(LOCAL, 'e2e-04-原始点.png') })

  console.log('\n【9】勾掉曲线 = 图上少一条')
  const folder = resolve(ROOT, 'contract', 'examples', 'example-basic.json')
  await page.getByTestId('source-plugin').selectOption('contract-json')
  await page.getByTestId('file-path').fill(folder)
  await page.getByTestId('open-file').click()
  await waitFor(async () => (await drawPoints(page)) === 9, 8000)
  check((await drawPoints(page)) === 9, `契约示例的两条曲线共 9 点（实际 ${await drawPoints(page)}）`)
  await page.getByTestId('series-温度').uncheck()
  await page.waitForTimeout(400)
  check((await drawPoints(page)) === 4, `取消「温度」后只剩 4 点（实际 ${await drawPoints(page)}）`)
  await page.screenshot({ path: resolve(LOCAL, 'e2e-05-曲线勾选.png') })

  await browser.close()
}

main()
  .then(() => {
    console.log(`\n${'='.repeat(60)}`)
    if (failures.length) {
      console.log(`内测未通过：${checks - failures.length}/${checks} 项，${failures.length} 项失败`)
      for (const item of failures) console.log(`  - ${item}`)
      process.exit(1)
    }
    console.log(`内测通过：${checks} 项全部通过`)
    console.log(`截图见 ${LOCAL}\\e2e-*.png`)
  })
  .catch((error) => {
    console.error('\n内测脚本自己出错了：', error)
    process.exit(2)
  })
