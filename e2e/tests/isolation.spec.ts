// 两个演播厅同时打开，互不串内容

import { expect, test } from '@playwright/test'
import { createAndStart, detail, uttIdsOnPage, waitDone } from './helpers'

test('同时打开两个讨论的演播厅，互相不串内容', async ({ browser, request }) => {
  const a = await createAndStart(request, '城市应该限制网约车数量吗')
  const b = await createAndStart(request, '大学应该取消期末闭卷考试吗')

  const ctx = await browser.newContext()
  const pageA = await ctx.newPage()
  const pageB = await ctx.newPage()
  await Promise.all([pageA.goto(`/d/${a}`), pageB.goto(`/d/${b}`)])

  await expect(pageA.locator('.hostbar-topic')).toHaveText('城市应该限制网约车数量吗')
  await expect(pageB.locator('.hostbar-topic')).toHaveText('大学应该取消期末闭卷考试吗')

  // 两边都推进到至少 4 条发言时，对照接口数据检查
  for (const page of [pageA, pageB]) {
    await expect.poll(async () => (await uttIdsOnPage(page)).length, { timeout: 30_000 }).toBeGreaterThanOrEqual(4)
  }
  const [dA, dB] = await Promise.all([detail(request, a), detail(request, b)])
  const idsA = new Set(dA.utterances.map((u) => u.id))
  const idsB = new Set(dB.utterances.map((u) => u.id))

  const onA = await uttIdsOnPage(pageA)
  const onB = await uttIdsOnPage(pageB)
  expect(onA.every((x) => idsA.has(x)), `A 页面出现了不属于 A 的发言：${onA}`).toBe(true)
  expect(onB.every((x) => idsB.has(x)), `B 页面出现了不属于 B 的发言：${onB}`).toBe(true)
  expect(onA.some((x) => idsB.has(x))).toBe(false)
  expect(onB.some((x) => idsA.has(x))).toBe(false)

  await Promise.all([waitDone(request, a), waitDone(request, b)])
  await ctx.close()
})
