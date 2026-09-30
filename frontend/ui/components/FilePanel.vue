<script setup>
import { computed } from 'vue'

import { strings } from '../strings.js'

const props = defineProps({
  path: { type: String, default: '' },
  plugins: { type: Array, default: () => [] },
  pluginId: { type: String, default: '' },
  options: { type: Object, default: () => ({}) },
  series: { type: Array, default: () => [] },
  selected: { type: Array, default: () => [] },
  busy: { type: Boolean, default: false },
})
const emit = defineEmits([
  'update:path',
  'update:pluginId',
  'update:options',
  'update:selected',
  'browse',
  'open',
])

const current = computed(() => props.plugins.find((item) => item.id === props.pluginId) || null)

function setOption(decl, raw) {
  // 数值型参数要按声明转成数字：后端按类型校验，传字符串会被判为非法请求
  const value = decl.type === 'int' ? parseInt(raw, 10) : decl.type === 'float' ? Number(raw) : raw
  emit('update:options', { ...props.options, [decl.name]: value })
}

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
      <button :disabled="busy" @click="emit('browse')">{{ strings.browse }}</button>
      <span class="label">{{ strings.sourcePlugin }}</span>
      <select
        :value="pluginId"
        :disabled="busy || !plugins.length"
        @change="emit('update:pluginId', $event.target.value)"
      >
        <option v-for="item in plugins" :key="item.id" :value="item.id">
          {{ item.display_name }}
        </option>
      </select>
      <button :disabled="busy || !plugins.length" @click="emit('open')">{{ strings.open }}</button>
    </div>

    <!-- 参数控件由插件的参数声明生成：新增插件、新增参数都不需要改这里 -->
    <div v-if="current && current.params.length" class="row">
      <span class="label">{{ strings.params }}</span>
      <label v-for="decl in current.params" :key="decl.name" class="param">
        <span>{{ decl.display_name || decl.name }}</span>
        <select
          v-if="decl.type === 'enum'"
          :value="options[decl.name]"
          :disabled="busy"
          @change="setOption(decl, $event.target.value)"
        >
          <option v-for="value in decl.values || []" :key="value" :value="value">{{ value }}</option>
        </select>
        <input
          v-else
          :type="decl.type === 'int' || decl.type === 'float' ? 'number' : 'text'"
          :value="options[decl.name]"
          :disabled="busy"
          @input="setOption(decl, $event.target.value)"
        />
      </label>
    </div>

    <p v-if="current && current.notes" class="hint">{{ current.notes }}</p>

    <div v-if="series.length" class="row">
      <span class="label">{{ strings.series }}</span>
      <em class="note">{{ strings.seriesHint }}</em>
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
  min-width: 200px;
}

select {
  font: inherit;
  padding: 5px 8px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--panel);
  color: var(--text);
}

.label {
  color: var(--muted);
}

.param {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.param input {
  width: 90px;
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

.note {
  color: var(--muted);
  font-size: 12px;
  font-style: normal;
}

.hint {
  margin: 6px 0 0;
  color: var(--muted);
  font-size: 12px;
}
</style>
