import { authenticatePage } from './helpers/client'
import { expect, test } from '@playwright/test'

test('search uses API slots and selection requires explicit booking confirmation', async ({
  page,
  request,
}, testInfo) => {
  let bookings = 0
  page.on('request', (r) => {
    if (r.method() === 'POST' && r.url().endsWith('/bookings')) bookings++
  })
  await page.goto('/s/fixture')
  await page.getByRole('button', { name: 'Подобрать по описанию' }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('Пожелания ко времени').fill('Завтра с 10:00 до 12:00')
  const response = page.waitForResponse((r) => r.url().endsWith('/specialists/fixture/search'))
  await dialog.getByRole('button', { name: 'Найти время', exact: true }).click()
  const data = await (await response).json()
  expect(data.status).toBe('found')
  expect(data.items).toHaveLength(4)
  await expect(dialog.getByRole('button', { name: 'Выбрать 10:00', exact: true })).toBeVisible()
  for (const width of [390, 768, 1440]) {
    await page.setViewportSize({ width, height: 1000 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.screenshot({ path: testInfo.outputPath(`ai-search-${width}.png`), fullPage: true })
  }
  expect(bookings).toBe(0)
  await dialog.getByRole('button', { name: 'Выбрать 10:00', exact: true }).focus()
  await page.keyboard.press('Enter')
  await expect(dialog).toHaveCount(0)
  await expect(page.getByRole('heading', { name: 'Данные для записи' })).toBeVisible()
  expect(bookings).toBe(0)

  const created = page.waitForResponse((r) => r.url().endsWith('/bookings') && r.status() === 201)
  await page.getByRole('button', { name: 'Подтвердить запись' }).click()
  const booking = await (await created).json()
  await expect(page.getByText('Вы записаны', { exact: true })).toBeVisible()
  expect(bookings).toBe(1)
  expect(
    (
      await request.post(`/api/v1/bookings/${booking.id}/cancel`, {
        headers: { Authorization: `Bearer ${booking.manage_token}` },
      })
    ).status(),
  ).toBe(200)
})

test('ambiguous request can be clarified; provider failure offers the calendar', async ({
  page,
}) => {
  await page.goto('/s/fixture')
  await page.getByRole('button', { name: 'Подобрать по описанию' }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('Пожелания ко времени').fill('Завтра после трёх')
  await dialog.getByRole('button', { name: 'Найти время', exact: true }).click()
  await expect(dialog.getByText('Уточните время', { exact: false })).toBeVisible()
  await expect(
    dialog.getByRole('group', { name: 'Найденное время' }).getByRole('button'),
  ).toHaveCount(0)
  await dialog.getByLabel('Пожелания ко времени').fill('Завтра с 10:00 до 12:00')
  await dialog.getByRole('button', { name: 'Найти время', exact: true }).click()
  await expect(dialog.getByRole('button', { name: 'Выбрать 10:30' })).toBeVisible()
  await dialog.getByLabel('Пожелания ко времени').fill('Сбой провайдера')
  await expect(dialog.getByRole('group', { name: 'Найденное время' })).toHaveCount(0)
  await dialog.getByRole('button', { name: 'Найти время', exact: true }).click()
  await expect(
    dialog.getByText('Поиск по описанию сейчас недоступен.', { exact: false }),
  ).toBeVisible()
  await dialog.getByRole('button', { name: 'Выбрать в календаре' }).click()
  await expect(page.getByRole('button', { name: 'Подобрать по описанию' })).toBeFocused()
  await page.getByRole('button', { name: 'Завтра', exact: true }).click()
  await expect(page.getByRole('group', { name: 'Доступное время', exact: true })).toBeVisible()
})

test('closing an in-flight search discards the late result', async ({ page }) => {
  await page.goto('/s/fixture')
  await page.getByRole('button', { name: 'Подобрать по описанию' }).click()
  await page.getByLabel('Пожелания ко времени').fill('Медленный ответ')
  await page.getByRole('button', { name: 'Найти время', exact: true }).click()
  await expect(
    page.getByRole('status', { name: '' }).filter({ hasText: 'Проверяем пожелания' }),
  ).toBeVisible()
  await page.keyboard.press('Escape')
  await page.getByRole('button', { name: 'Подобрать по описанию' }).click()
  await page.getByLabel('Пожелания ко времени').fill('Сбой провайдера')
  await page.getByRole('button', { name: 'Найти время', exact: true }).click()
  await expect(
    page.getByText('Поиск по описанию сейчас недоступен.', { exact: false }),
  ).toBeVisible()
  await expect(
    page.getByRole('group', { name: 'Найденное время' }).getByRole('button'),
  ).toHaveCount(0)
})

test.beforeEach(async ({ page }) => {
  await authenticatePage(page)
})
