// 中途加入和断线重连：不重复、不丢消息。
// E2E 环境里服务端每 3 秒主动断开一次 SSE（SSE_MAX_STREAM_S=3），断线重连在每场讨论中都会真实发生。

import { expect, test, type Page } from '@playwright/test'
import { createAndStart, detail, gapsWhileLive, uttIdsOnPage, waitDone } from './helpers'

/** 讨论结束后，切到「回看现场记录」，读出页面上全部发言 id */
async function allIdsAfterDone(page: Page) {
  await expect(page.locator('.summary-text .summary-p').first()).toBeVisible({ timeout: 60_000 })
  await page.getByRole('button', { name: '回看现场记录' }).click()
  await expect(page.locator('.studio')).toBeVisible()
  return uttIdsOnPage(page)
}

test('中途加入：先拿历史再接 SSE，发言不重复不丢', async ({ page, request }) => {
  const id = await createAndStart(request, '短视频平台应该限制未成年人使用时长吗')
  // 等讨论已经进行了一段再进入
  await expect.poll(async () => (await detail(request, id)).utterances.length, { timeout: 30_000 }).toBeGreaterThanOrEqual(4)

  await page.goto(`/d/${id}`)
  // 进行中：历史和新消息之间没有空洞
  await expect.poll(async () => (await uttIdsOnPage(page)).length).toBeGreaterThanOrEqual(5)
  expect(await gapsWhileLive(page, request, id)).toEqual([])

  const onPage = await allIdsAfterDone(page)
  const expected = (await detail(request, id)).utterances.map((u) => u.id)
  expect(new Set(onPage).size, '页面上有重复的发言').toBe(onPage.length)
  expect([...onPage].sort((x, y) => x - y)).toEqual(expected)
})

test('断线重连：带 Last-Event-ID 续传，发言不重复不丢', async ({ page, request }) => {
  // Last-Event-ID 是浏览器在网络层追加的请求头，request.headers() 里没有，要用 allHeaders()
  const streamRequests: { lastEventId: string | undefined }[] = []
  page.on('request', async (r) => {
    if (r.url().includes('/stream')) streamRequests.push({ lastEventId: (await r.allHeaders())['last-event-id'] })
  })

  const id = await createAndStart(request, '城市应该全面推广无人驾驶出租车吗')
  await page.goto(`/d/${id}`)

  // 等到至少发生过一次重连
  await expect.poll(() => streamRequests.length, { timeout: 20_000 }).toBeGreaterThanOrEqual(2)
  expect(streamRequests.slice(1).every((r) => r.lastEventId && Number(r.lastEventId) > 0), '重连请求都应带 Last-Event-ID').toBe(true)

  // 重连之后、讨论结束之前：已显示的发言之间没有空洞（必须在进行中检查，结束时的整页重拉会掩盖丢失）
  await page.waitForTimeout(1000)
  expect(['running', 'summarizing'], '重连发生时讨论应仍在进行').toContain(await page.locator('[data-status]').first().getAttribute('data-status'))
  expect(await gapsWhileLive(page, request, id)).toEqual([])

  const onPage = await allIdsAfterDone(page)
  await waitDone(request, id)
  const expected = (await detail(request, id)).utterances.map((u) => u.id)
  expect(new Set(onPage).size, '页面上有重复的发言').toBe(onPage.length)
  expect([...onPage].sort((x, y) => x - y)).toEqual(expected)
})
