import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// root 就是 frontend/：目录按业务用途分（ui / api / renderers），不套一层 src/
// strictPort：端口被占用时直接失败，避免 dev server 悄悄换端口后前端连错后端
export default defineConfig({
  plugins: [vue()],
  server: {
    // 显式绑 IPv4：只写 localhost 时，Windows 上常绑到 ::1，用 127.0.0.1 反而连不上
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
