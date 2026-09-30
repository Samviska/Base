<script setup>
import { ref, watch } from 'vue'

import { strings } from '../strings.js'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  // 由外部注入请求函数：本组件不认识通信客户端，便于单独调试
  request: { type: Function, required: true },
  initialPath: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue', 'select'])

const ABSOLUTE = /^(?:[A-Za-z]:[\\/]|[\\/])/

const current = ref('')
const typed = ref('')
const parent = ref(null)
const roots = ref([])
const shortcuts = ref([])
const entries = ref([])
const truncated = ref(false)
const picked = ref('')
const busy = ref(false)
const error = ref('')

async function load(path) {
  busy.value = true
  error.value = ''
  try {
    const payload = await props.request('browse', path ? { path } : {})
    current.value = payload.path
    typed.value = payload.path
    parent.value = payload.parent
    roots.value = payload.roots || []
    shortcuts.value = payload.shortcuts || []
    entries.value = payload.entries
    truncated.value = payload.truncated
    picked.value = ''
  } catch (err) {
    error.value = err?.message || String(err)
  } finally {
    busy.value = false
  }
}

watch(
  () => props.modelValue,
  (open) => {
    if (!open) return
    // 只有绝对路径才当起点：相对路径（如 contract/examples/x.json）会把浏览困在项目目录里，
    // 而使用者要的是"整块硬盘都能去"
    load(ABSOLUTE.test(props.initialPath || '') ? props.initialPath : '')
  },
)

// 单击目录就进去，单击文件先选中；双击文件等于"选中并确认"
function activate(entry) {
  if (entry.type === 'dir') load(entry.path)
  else picked.value = entry.path
}

function confirm() {
  if (!picked.value) return
  emit('select', picked.value)
  emit('update:modelValue', false)
}

function close() {
  emit('update:modelValue', false)
}

function sizeText(size) {
  if (size === null || size === undefined) return ''
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${Math.round(size / 1024)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}
</script>

<template>
  <div v-if="modelValue" class="mask" @click.self="close">
    <section class="dialog">
      <header>
        <strong>{{ strings.browser.title }}</strong>
        <span class="where">{{ current }}</span>
      </header>

      <div class="toolbar">
        <button :disabled="!parent || busy" @click="load(parent)">↑ {{ strings.browser.parent }}</button>
        <input
          v-model="typed"
          type="text"
          :disabled="busy"
          placeholder="粘贴绝对路径后回车"
          @keyup.enter="load(typed)"
        />
        <button :disabled="busy" @click="load(typed)">前往</button>
      </div>

      <!-- 各盘符与常用目录：整块硬盘都能去 -->
      <div class="toolbar">
        <button v-for="root in roots" :key="root" :disabled="busy" @click="load(root)">
          {{ root }}
        </button>
        <button
          v-for="item in shortcuts"
          :key="item.path"
          :disabled="busy"
          @click="load(item.path)"
        >
          {{ item.name }}
        </button>
        <span v-if="truncated" class="note">{{ strings.browser.truncated }}</span>
      </div>

      <ul class="list">
        <li
          v-for="entry in entries"
          :key="entry.path"
          :class="{ dir: entry.type === 'dir', picked: picked === entry.path }"
          @click="activate(entry)"
          @dblclick="entry.type === 'file' && confirm()"
        >
          <span class="name">{{ entry.type === 'dir' ? '📁' : '📄' }} {{ entry.name }}</span>
          <span class="size">{{ sizeText(entry.size) }}</span>
        </li>
        <li v-if="!entries.length && !busy" class="empty">（空目录）</li>
      </ul>

      <p v-if="error" class="error">{{ error }}</p>

      <footer>
        <span class="picked">{{ picked || '未选择文件' }}</span>
        <button :disabled="!picked" @click="confirm">{{ strings.browser.confirm }}</button>
        <button @click="close">{{ strings.browser.cancel }}</button>
      </footer>
    </section>
  </div>
</template>

<style scoped>
.mask {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(38, 50, 56, 0.35);
  z-index: 10;
}

.dialog {
  display: flex;
  flex-direction: column;
  width: min(760px, 92vw);
  height: min(600px, 88vh);
  padding: var(--gap);
  gap: var(--gap);
  border-radius: var(--radius);
  background: var(--panel);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.25);
}

header {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.where {
  color: var(--muted);
  font-size: 12px;
  word-break: break-all;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.toolbar input[type="text"] {
  flex: 1;
  min-width: 200px;
}

.note {
  color: var(--warn);
  font-size: 12px;
}

.list {
  flex: 1;
  margin: 0;
  padding: 0;
  overflow: auto;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  list-style: none;
}

.list li {
  display: flex;
  justify-content: space-between;
  gap: var(--gap);
  padding: 4px 8px;
  cursor: pointer;
}

.list li:hover {
  background: #f0f4f7;
}

.list li.picked {
  background: #e3f2fd;
}

.list li.dir .name {
  color: var(--accent);
}

.size {
  color: var(--muted);
  font-size: 12px;
}

.empty {
  color: var(--muted);
  justify-content: center;
  cursor: default;
}

.error {
  margin: 0;
  color: var(--danger);
  font-size: 12px;
}

footer {
  display: flex;
  align-items: center;
  gap: var(--gap);
}

.picked {
  flex: 1;
  overflow: hidden;
  color: var(--muted);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
