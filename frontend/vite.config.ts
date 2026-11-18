import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// 开发时把 /api 转发给后端（含 SSE）。后端地址可用 API_TARGET 覆盖，E2E 测试用它指向独立端口。
const target = process.env.API_TARGET ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    proxy: { '/api': { target, changeOrigin: true } },
  },
})
