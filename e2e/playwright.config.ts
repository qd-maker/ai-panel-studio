// E2E：同时拉起后端（LLM_MODE=mock，每次一个全新数据库）和前端 dev server，用本机 Chrome 跑。

import { defineConfig } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(here, '..')
const backend = path.join(root, 'backend')
const python = process.platform === 'win32' ? path.join(backend, '.venv', 'Scripts', 'python.exe') : path.join(backend, '.venv', 'bin', 'python')
const db = path.join(here, '.tmp', `e2e-${Date.now()}.db`).replace(/\\/g, '/')

const API_PORT = 8010
const WEB_PORT = 5274

export default defineConfig({
  testDir: './tests',
  timeout: 90_000,
  expect: { timeout: 30_000 },
  fullyParallel: true,
  workers: 2,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: `http://127.0.0.1:${WEB_PORT}`,
    channel: 'chrome', // 用本机安装的 Chrome，不另外下载浏览器
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  webServer: [
    {
      command: `"${python}" -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port ${API_PORT}`,
      cwd: backend,
      url: `http://127.0.0.1:${API_PORT}/api/health`,
      reuseExistingServer: false,
      timeout: 60_000,
      env: {
        LLM_MODE: 'mock',
        APS_DATABASE_URL: `sqlite:///${db}`,
        TURN_DELAY_S: '0.8', // 节奏放慢一点，让测试能看到「进行中」的各个阶段
        MAX_EXPERT_TURNS: '10', // 约 15 秒一场，保证重连发生时讨论还在进行
        MAX_RUNNING: '20',
        // 每条 SSE 连接 3 秒后由服务端断开：让「断线 → 带 Last-Event-ID 重连 → 续传」在测试里真实发生
        SSE_MAX_STREAM_S: '3',
      },
    },
    {
      command: `npm run dev -- --port ${WEB_PORT} --strictPort`,
      cwd: path.join(root, 'frontend'),
      url: `http://127.0.0.1:${WEB_PORT}`,
      reuseExistingServer: false,
      timeout: 60_000,
      env: { API_TARGET: `http://127.0.0.1:${API_PORT}` },
    },
  ],
})
