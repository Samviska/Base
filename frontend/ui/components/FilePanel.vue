<script setup>
import { strings } from '../strings.js'

const props = defineProps({
  path: { type: String, default: '' },
  series: { type: Array, default: () => [] },
  selected: { type: Array, default: () => [] },
  busy: { type: Boolean, default: false },
})
const emit = defineEmits(['update:path', 'update:selected', 'open'])

function toggle(name) {
  const next = props.selected.includes(name)
    ? props.selected.filter((item) => item !== name)
    : [...props.selected, name]
  emit('update:selected', next)
}
</script>

<template>
  <section class="panel">
    <div class="row">
      <span class="label">{{ strings.filePath }}</span>
      <input
        type="text"
        :value="path"
        :disabled="busy"
        @input="emit('update:path', $event.target.value)"
        @keyup.enter="emit('open')"
      />
      <button :disabled="busy" @click="emit('open')">{{ strings.open }}</button>
    </div>
    <p class="hint">{{ strings.fileHint }}</p>

    <div v-if="series.length" class="row">
      <span class="label">{{ strings.series }}</span>
      <label v-for="item in series" :key="item.name" class="check">
        <input
          type="checkbox"
          :checked="selected.includes(item.name)"
          @change="toggle(item.name)"
        />
        <span>{{ item.name }}</span>
        <em>{{ item.unit }}</em>
      </label>
    </div>
    <p v-else class="hint">{{ strings.noSeries }}</p>
  </section>
</template>

<style scoped>
.panel {
  padding: var(--gap);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--panel);
}

.row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--gap);
}

.row input[type="text"] {
  flex: 1;
  min-width: 240px;
}

.label {
  color: var(--muted);
}

.check {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.check em {
  color: var(--muted);
  font-style: normal;
}

.hint {
  margin: 6px 0 0;
  color: var(--muted);
  font-size: 12px;
}
</style>
