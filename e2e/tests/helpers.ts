import { expect, type APIRequestContext, type Page } from '@playwright/test'

export interface Utt {
  id: number
  participant_id: string
  act: string
}
export interface Detail {
  id: string
  topic: string
  status: string
  utterances: Utt[]
  participants: { id: string; role: string; name: string }[]
  summary: string | null
}

export async function createAndStart(request: APIRequestContext, topic: string): Promise<string> {
  const r = await request.post('/api/discussions', { data: { topic, expert_count: 4 } })
  expect(r.status()).toBe(201)
  const id = (await r.json()).id as string
  expect((await request.post(`/api/discussions/${id}/start`)).status()).toBe(202)
  return id
}

export async function detail(request: APIRequestContext, id: string): Promise<Detail> {
  return (await request.get(`/api/discussions/${id}`)).json()
}

/** 等后端里这场讨论到达终态 */
export async function waitDone(request: APIRequestContext, id: string) {
  await expect.poll(async () => (await detail(request, id)).status, { timeout: 60_000 }).toBe('done')
}

/** 页面上出现过的全部发言 id（舞台 + 记录） */
export async function uttIdsOnPage(page: Page): Promise<number[]> {
  return page.locator('[data-utt-id]').evaluateAll((els) => els.map((e) => Number(e.getAttribute('data-utt-id'))))
}

/**
 * 讨论进行中检查「不丢」：页面上已显示的最大发言 id 之前，接口里的每条发言都应已在页面上。
 * 必须在结束前检查，因为结束时页面会重拉一次完整快照，会掩盖 SSE 续传时丢掉的消息。
 */
export async function gapsWhileLive(page: Page, request: APIRequestContext, id: string): Promise<number[]> {
  const onPage = new Set(await uttIdsOnPage(page))
  if (onPage.size === 0) return []
  const maxShown = Math.max(...onPage)
  const api = await detail(request, id)
  return api.utterances.map((u) => u.id).filter((x) => x <= maxShown && !onPage.has(x))
}

/** 禁止项：内部事件文字、意图字段、JSON 原文 */
export async function expectNoForbiddenText(page: Page) {
  const text = await page.locator('body').innerText()
  expect(text).not.toContain('举手')
  expect(text).not.toContain('抢话')
  expect(text).not.toContain('raise_hand')
  expect(text).not.toContain('urgency')
  // 任何一行以 { 或 [ 开头并紧跟引号，视为 JSON 原文
  expect(text).not.toMatch(/(^|\n)\s*[{[]\s*"/)
}

/** 页面本身不滚动：文档高度不超过视口 */
export async function expectNoPageScroll(page: Page) {
  const m = await page.evaluate(() => ({
    doc: document.documentElement.scrollHeight,
    body: document.body.scrollHeight,
    vh: window.innerHeight,
  }))
  expect(m.doc, `documentElement ${m.doc} > 视口 ${m.vh}`).toBeLessThanOrEqual(m.vh)
  expect(m.body, `body ${m.body} > 视口 ${m.vh}`).toBeLessThanOrEqual(m.vh)
}
