// 主流程：首页发起 → 阵容 → 确认 → 演播厅 → 开场 → 专家发言 → 共识分歧在结束前出现 → 自然语言总结

import { expect, test } from '@playwright/test'
import { detail, expectNoForbiddenText } from './helpers'

test('首页发起讨论，一路看到结束后的自然语言总结', async ({ page, request }) => {
  // 1. 首页发起
  await page.goto('/')
  await page.locator('#new-topic').fill('远程办公会降低团队创造力吗')
  await page.getByRole('button', { name: '生成嘉宾阵容' }).click()

  // 2. 阵容：1 位主持人 + 4 位专家
  await expect(page).toHaveURL(/\/d\/[0-9a-f]+$/)
  const id = page.url().split('/d/')[1]
  await expect(page.locator('.guest:not(.is-skeleton)')).toHaveCount(5)
  await expect(page.locator('.guest.is-host')).toHaveCount(1)
  await expectNoForbiddenText(page)

  // 3. 确认 → 演播厅
  await page.getByRole('button', { name: /开始讨论/ }).click()
  const studio = page.locator('.studio')
  await expect(studio).toBeVisible()
  await expect(page.locator('.hostbar-live')).toContainText('LIVE')

  // 4. 主持人开场：第一条发言来自主持人，act 为 opening
  await expect(page.locator('[data-utt-id]').first()).toBeVisible()
  const first = (await detail(request, id)).utterances[0]
  expect(first.act).toBe('opening')
  const host = (await detail(request, id)).participants.find((p) => p.role === 'host')!
  expect(first.participant_id).toBe(host.id)

  // 5. 共识/分歧区在讨论结束前就有内容
  await expect(page.locator('.insights .ins-item').first()).toBeVisible()
  expect(['running', 'summarizing']).toContain(await studio.getAttribute('data-status'))

  // 6. 至少 3 条专家发言出现在记录里
  await expect
    .poll(async () => page.locator('.transcript .utt .utt-title').evaluateAll((els) => els.filter((e) => e.textContent !== '主持人').length))
    .toBeGreaterThanOrEqual(3)
  await expectNoForbiddenText(page)

  // 7. 结束后出现自然语言总结
  const summary = page.locator('.summary-text .summary-p').first()
  await expect(summary).toBeVisible({ timeout: 60_000 })
  const text = (await page.locator('.summary-text').innerText()).trim()
  expect(text.length).toBeGreaterThan(10)
  expect(text).not.toMatch(/^[{[]/)
  expect(text).not.toContain('```')
  expect(() => JSON.parse(text)).toThrow()
  await expectNoForbiddenText(page)
})
