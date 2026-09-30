<script setup>
import { strings } from '../strings.js'

const props = defineProps({
  readings: { type: Array, default: () => [] },
  max: { type: Number, default: 8 },
})
const emit = defineEmits(['add', 'remove'])

function fmt(value) {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—'
  const abs = Math.abs(value)
  if (abs >= 1e4) return value.toFixed(0)
  if (abs >= 1) return value.toFixed(3)
  return value.toPrecision(3)
}
</script>

<template>
  <aside class="panel">
    <header>
      <strong>{{ strings.cursor.title }}</strong>
      <button
        data-testid="cursor-add"
        :disabled="readings.length >= max"
        :title="strings.cursor.add"
        @click="emit('add')"
      >
        ＋
      </button>
    </header>

    <ul v-if="readings.length" data-testid="cursor-list">
      <li v-for="(item, index) in readings" :key="item.id" :data-testid="`cursor-${index}`">
        <span class="badge">C{{ index + 1 }}</span>
        <span class="values">
          <em>X</em>&nbsp;{{ fmt(item.x) }}<br />
          <em>Y</em>&nbsp;{{ fmt(item.y) }}
        </span>
        <button class="remove" :title="strings.cursor.remove" @click="emit('remove', item.id)">
          ✕
        </button>
      </li>
    </ul>
    <p v-else class="hint" data-testid="cursor-empty">{{ strings.cursor.empty }}</p>

    <section v-if="readings.length > 1" data-testid="cursor-deltas">
      <h4>{{ strings.cursor.delta }}</h4>
      <div
        v-for="(item, index) in readings.slice(1)"
        :key="item.id"
        class="delta"
        :data-testid="`delta-${index}`"
      >
        <span class="badge">C{{ index }}→C{{ index + 1 }}</span>
        <span>ΔX&nbsp;{{ fmt(item.x - readings[index].x) }}</span>
        <span>ΔY&nbsp;{{ fmt(item.y - readings[index].y) }}</span>
      </div>
    </section>

    <!-- 聚合显示时光标落在像素列上，Y 是极值而非采样值：这件事必须说出来 -->
    <p
      v-if="readings.some((item) => item.aggregated)"
      class="warn"
      data-testid="cursor-aggregated-note"
    >
      {{ strings.cursor.aggregatedNote }}
    </p>
  </aside>
</template>

<style scoped>
.panel {
  display: flex;
  flex-direction: column;
  gap: var(--gap);
  padding: var(--gap);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--panel);
  overflow: auto;
}

header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

ul {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin: 0;
  padding: 0;
  list-style: none;
}

li,
.delta {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  font-size: 12px;
}

.badge {
  padding: 1px 6px;
  border-radius: 8px;
  background: #d81b60;
  color: #fff;
  font-size: 11px;
}

.values {
  flex: 1;
  font-variant-numeric: tabular-nums;
}

em {
  color: var(--muted);
  font-style: normal;
}

.remove {
  padding: 0 6px;
  color: var(--muted);
}

h4 {
  margin: 0 0 6px;
  color: var(--muted);
  font-size: 12px;
}

.delta {
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  margin-bottom: 6px;
  font-variant-numeric: tabular-nums;
}

.hint,
.warn {
  margin: 0;
  color: var(--muted);
  font-size: 12px;
}

.warn {
  color: var(--warn);
}
</style>
