<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { createRenderer } from '../../renderers/builtin/line.js'

const props = defineProps({
  axes: { type: Object, default: () => ({}) },
  units: { type: Object, default: () => ({}) },
  // 数据完整范围（来自 M3 摘要）：渲染器靠它实现"双击回到全览"
  fullRange: { type: Array, default: null },
  cursors: { type: Array, default: () => [] },
})
const emit = defineEmits(['zoom', 'pan', 'cursorMove'])

const host = ref(null)
let renderer = null

onMounted(() => {
  // UI 只把容器交出去：渲染器内部不引用 Vue，两者之间只有数据与事件（renderer.md 硬规则 1）
  renderer = createRenderer({
    container: host.value,
    options: { axes: props.axes, units: props.units, fullRange: props.fullRange },
  })
  renderer.mount()
  renderer.setCursors(props.cursors)
  renderer.on('zoom', (view) => emit('zoom', view))
  renderer.on('pan', (view) => emit('pan', view))
  renderer.on('cursor-move', (payload) => emit('cursorMove', payload))
})

// 新增 / 删除光标由上层决定，这里只同步下去
watch(
  () => props.cursors,
  (list) => renderer?.setCursors(list),
  { deep: true },
)

onBeforeUnmount(() => {
  renderer?.unmount()
  renderer = null
})

// 对外只暴露"喂数据、设视口、量宽度"，渲染细节不出这个组件
defineExpose({
  applyData: (payload) => renderer?.setData(payload),
  appendData: (payload) => renderer?.appendData(payload),
  setViewport: (view) => renderer?.setViewport(view),
  setAnnotations: (list) => renderer?.setAnnotations(list),
  resetView: () => renderer?.resetView(),
  plotWidth: () => host.value?.clientWidth || 0,
})
</script>

<template>
  <div ref="host" class="chart" data-testid="chart"></div>
</template>

<style scoped>
.chart {
  width: 100%;
  height: 100%;
  min-height: 0;
}
</style>
