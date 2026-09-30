<script setup>
import { computed } from 'vue'

import { strings } from '../strings.js'

const props = defineProps({
  connection: { type: String, default: 'idle' },
  aggregated: { type: Boolean, default: false },
  dataPoints: { type: Number, default: 0 },
  drawPoints: { type: Number, default: 0 },
  viewport: { type: Object, default: null },
  warnings: { type: Array, default: () => [] },
  error: { type: String, default: '' },
})

const stateText = computed(() => strings.connection[props.connection] || props.connection)

const viewportText = computed(() => {
  if (!props.viewport) return '—'
  return `${format(props.viewport.x0)} → ${format(props.viewport.x1)}`
})

function format(value) {
  return Number.isFinite(value) ? value.toFixed(2) : '—'
}
</script>

<template>
  <footer class="bar">
    <span :class="['dot', connection]" data-testid="status-connection">{{ stateText }}</span>
    <!-- 是否处于聚合显示必须看得见：否则会把 min/max 线段误当成原始波形 -->
    <span :class="['tag', aggregated ? 'on' : '']" data-testid="status-aggregated">
      {{ aggregated ? strings.aggregatedOn : strings.aggregatedOff }}
    </span>
    <!-- 两个点数必须分开写：聚合时"本次绘制"远小于数据总量，混在一起会让人以为数据丢了 -->
    <span data-testid="status-data-points">{{ strings.dataPoints }}：{{ dataPoints }}</span>
    <span data-testid="status-draw-points">{{ strings.drawPoints }}：{{ drawPoints }}</span>
    <span data-testid="status-viewport">{{ strings.viewport }}：{{ viewportText }}</span>
    <!-- 坏插件不该让应用起不来，但使用者必须知道它坏了（S4） -->
    <span v-if="warnings.length" class="warn" data-testid="status-warnings">
      {{ warnings.join('；') }}
    </span>
    <span v-if="error" class="error" data-testid="status-error">{{ error }}</span>
  </footer>
</template>

<style scoped>
.bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--gap);
  padding: 6px var(--gap);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--panel);
  font-size: 12px;
}

.dot::before {
  content: "●";
  margin-right: 4px;
  color: var(--muted);
}

.dot.open::before {
  color: var(--ok);
}

.dot.connecting::before {
  color: var(--warn);
}

.dot.closed::before {
  color: var(--danger);
}

.tag {
  padding: 1px 8px;
  border: 1px solid var(--border);
  border-radius: 10px;
  color: var(--muted);
}

.tag.on {
  border-color: var(--accent);
  color: var(--accent);
}

.error {
  color: var(--danger);
}

.warn {
  color: var(--warn);
}
</style>
