<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'

import { CLIENT_STATE, createClient } from '../api/client.js'
import { createViewportLoader } from '../api/viewport-loader.js'
import ChartView from './components/ChartView.vue'
import FileBrowser from './components/FileBrowser.vue'
import FilePanel from './components/FilePanel.vue'
import StatusBar from './components/StatusBar.vue'
import { strings } from './strings.js'

// 后端地址可用 URL 参数覆盖：?backend=ws://127.0.0.1:8791
const backendUrl =
  new URLSearchParams(window.location.search).get('backend') || 'ws://127.0.0.1:8765'
const client = createClient({ url: backendUrl })

const connection = ref(CLIENT_STATE.IDLE)
const filePath = ref('contract/examples/example-basic.json')
const sourcePlugins = ref([])
const pluginId = ref('')
const pluginOptions = ref({})
const warnings = ref([])
const seriesList = ref([])
const selected = ref([])
const axes = ref({})
const units = ref({})
const fullRange = ref(null)
const viewport = ref(null)
const aggregated = ref(false)
const dataPoints = ref(0) // 数据总量（M3 摘要给的是全量点数）
const drawPoints = ref(0) // 本次绘制点数（M6 响应里的点数，聚合时远小于总量）
const errorText = ref('')
const busy = ref(false)
const datasetId = ref(0)
const browserOpen = ref(false)
const chart = ref(null)

// 所有数据请求都从这里出去：按帧节流 + 代次作废，缩放时不会打出请求风暴
const loader = createViewportLoader({
  request: (job) => client.request('query_range', job),
  onData: (payload) => {
    aggregated.value = payload.aggregated
    drawPoints.value = payload.series.reduce((sum, item) => sum + item.x.length, 0)
    chart.value?.applyData(payload)
  },
  onError: showError,
})

function showError(error) {
  const base = strings.errorCodes[error?.code] || error?.message || String(error)
  // 契约违规必须给出字段路径，否则使用者只知道"哪儿都不对"
  const path = error?.detail?.path
  errorText.value = path ? `${base}（字段 ${path}）` : base
}

function applyViewport(next) {
  viewport.value = next
  chart.value?.setViewport(next)
  schedule()
}

function schedule() {
  if (!viewport.value || !seriesList.value.length || !selected.value.length) return
  loader.schedule({
    series: selected.value,
    x0: viewport.value.x0,
    x1: viewport.value.x1,
    // 目标分辨率由前端给出：画布像素宽度（M6）
    resolution: Math.max(1, Math.round(chart.value?.plotWidth() || 800)),
  })
}

async function connect() {
  errorText.value = ''
  try {
    await client.connect()
    await loadPlugins()
  } catch (error) {
    showError(error)
  }
}

// 插件清单与坏插件警告都来自后端：界面上不写死任何一个插件
async function loadPlugins() {
  const payload = await client.request('list_plugins')
  sourcePlugins.value = payload.plugins.filter((item) => item.type === 'source')
  warnings.value = payload.warnings || []
  if (!sourcePlugins.value.some((item) => item.id === pluginId.value)) {
    selectPlugin(sourcePlugins.value[0]?.id || '')
  }
}

function selectPlugin(id) {
  pluginId.value = id
  const plugin = sourcePlugins.value.find((item) => item.id === id)
  // 参数默认值同样来自声明：新增参数不需要改界面
  pluginOptions.value = Object.fromEntries(
    (plugin?.params || []).map((decl) => [decl.name, decl.default]),
  )
}

async function openFile() {
  errorText.value = ''
  busy.value = true
  try {
    const summary = await client.request('open_file', {
      path: filePath.value,
      source_plugin: pluginId.value || undefined,
      options: pluginOptions.value,
    })
    seriesList.value = summary.series
    // 轴描述与单位都来自数据本身：换一种日志，只要它按契约描述自己，界面就不用改
    axes.value = Object.fromEntries(summary.series.map((item) => [item.name, item.axis]))
    units.value = Object.fromEntries(summary.series.map((item) => [item.name, item.unit]))
    selected.value = summary.series.map((item) => item.name)
    aggregated.value = false
    drawPoints.value = 0
    dataPoints.value = summary.series.reduce((sum, item) => sum + (item.point_count || 0), 0)

    // 顺序要紧：渲染器在 mount 时读取 fullRange，先重建再赋值它就只能读到旧值
    // （"双击回不到全览"就是这么来的）
    const axisRange = summary.series[0]?.x_range
    fullRange.value = axisRange || null
    datasetId.value += 1
    await nextTick()
    applyViewport(axisRange ? { x0: axisRange[0], x1: axisRange[1] } : { x0: 0, x1: 1 })
  } catch (error) {
    showError(error)
  } finally {
    busy.value = false
  }
}

function onSelectionChange(next) {
  selected.value = next
  schedule()
}

// 与"双击画布"同一个动作：渲染器会自己发 zoom 回到完整范围
function resetView() {
  chart.value?.resetView()
}

onMounted(() => {
  client.onState((state) => {
    connection.value = state
  })
  client.on('error_notice', (payload) => {
    errorText.value = payload?.message || ''
  })
  connect()
})

onBeforeUnmount(() => {
  // 页面关闭要显式清理：作废在途请求并关掉连接，否则后端留下没人用的连接
  loader.cancel()
  client.close()
})
</script>

<template>
  <div class="app">
    <header class="head">
      <div>
        <h1>{{ strings.appTitle }}</h1>
        <p class="subtitle">{{ strings.subtitle }}</p>
      </div>
      <div class="conn">
        <span class="muted">{{ strings.backend }}：{{ backendUrl }}</span>
        <button data-testid="reset-view" :disabled="!fullRange" @click="resetView">
          {{ strings.resetView }}
        </button>
        <button :disabled="connection === 'connecting'" @click="connect">
          {{ strings.reconnect }}
        </button>
      </div>
    </header>

    <FilePanel
      v-model:path="filePath"
      :plugins="sourcePlugins"
      :plugin-id="pluginId"
      :options="pluginOptions"
      :series="seriesList"
      :selected="selected"
      :busy="busy"
      @update:pluginId="selectPlugin"
      @update:options="pluginOptions = $event"
      @update:selected="onSelectionChange"
      @browse="browserOpen = true"
      @open="openFile"
    />

    <!-- 浏览器给不出本机路径，所以"浏览文件"走后端的列目录命令 -->
    <FileBrowser
      v-model="browserOpen"
      :request="(type, payload) => client.request(type, payload)"
      :initial-path="filePath"
      @select="filePath = $event"
    />

    <main class="stage">
      <ChartView
        :key="datasetId"
        ref="chart"
        :axes="axes"
        :units="units"
        :full-range="fullRange"
        @zoom="applyViewport"
        @pan="applyViewport"
      />
    </main>

    <StatusBar
      :connection="connection"
      :aggregated="aggregated"
      :data-points="dataPoints"
      :draw-points="drawPoints"
      :viewport="viewport"
      :warnings="warnings"
      :error="errorText"
    />
  </div>
</template>

<style scoped>
.app {
  display: grid;
  grid-template-rows: auto auto 1fr auto;
  gap: var(--gap);
  height: 100vh;
  padding: var(--gap);
}

.head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--gap);
}

h1 {
  margin: 0;
  font-size: 16px;
}

.subtitle {
  margin: 2px 0 0;
  color: var(--muted);
  font-size: 12px;
}

.conn {
  display: flex;
  align-items: center;
  gap: var(--gap);
}

.muted {
  color: var(--muted);
  font-size: 12px;
}

.stage {
  min-height: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--panel);
  overflow: hidden;
}
</style>
