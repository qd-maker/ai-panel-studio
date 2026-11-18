// 禁止项（P-05 / P-06）和页面不滚动（P-09）

import { expect, test } from '@playwright/test'
import { createAndStart, expectNoForbiddenText, expectNoPageScroll } from './helpers'

test('整个流程里任何页面都找不到「举手」「raise_hand」和 JSON 原文', async ({ page, request }) => {
  await page.goto('/')
  await expectNoForbiddenText(page)

  const id = await createAndStart(request, '公司应该强制员工每周到岗三天吗')
  await page.goto(`/d/${id}`)
  await expect(page.locator('.studio')).toBeVisible()

  // 讨论进行中每秒检查一次，直到出现总结
  const summary = page.locator('.summary-text .summary-p').first()
  for (let i = 0; i < 60 && !(await summary.isVisible()); i++) {
    await expectNoForbiddenText(page)
    await page.waitForTimeout(1000)
  }
  await expect(summary).toBeVisible()
  await expectNoForbiddenText(page)
})

const VIEWPORTS = [
  { name: '超宽屏', width: 2560, height: 1440 },
  { name: '普通桌面', width: 1440, height: 900 },
  { name: '手机', width: 390, height: 844 },
]

for (const vp of VIEWPORTS) {
  test(`${vp.name} ${vp.width}×${vp.height} 下各页面 body 都不出现滚动条`, async ({ browser, request }) => {
    const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height } })
    const page = await ctx.newPage()

    await page.goto('/')
    await expect(page.locator('.composer')).toBeVisible()
    await expectNoPageScroll(page)

    // 阵容页
    const r = await request.post('/api/discussions', { data: { topic: `${vp.name}视口下的阵容页测试话题`, expert_count: 6 } })
    const lineupId = (await r.json()).id
    await page.goto(`/d/${lineupId}`)
    await expect(page.locator('.guest:not(.is-skeleton)').first()).toBeVisible()
    await expectNoPageScroll(page)

    // 演播厅（进行中）和总结页
    const id = await createAndStart(request, `${vp.name}视口下的演播厅测试话题`)
    await page.goto(`/d/${id}`)
    await expect(page.locator('.studio')).toBeVisible()
    await expect.poll(async () => page.locator('[data-utt-id]').count(), { timeout: 30_000 }).toBeGreaterThanOrEqual(4)
    await expectNoPageScroll(page)
    await page.screenshot({ path: `test-results/viewport-${vp.width}-studio.png` })

    await expect(page.locator('.summary-text .summary-p').first()).toBeVisible({ timeout: 60_000 })
    await expectNoPageScroll(page)
    await ctx.close()
  })
}
