import { expect, test } from '@playwright/test'
import { addDays, dateLabel, todayIn } from '../src/lib/dates'

const tomorrow = () => addDays(todayIn('Asia/Omsk'), 1)

test('real profile and slots, date changes, selection and responsive layout', async ({
  page,
  request,
}, testInfo) => {
  const errors: string[] = []
  page.on('pageerror', (e) => errors.push(e.message))
  await page.goto('/s/demo')
  await expect(page.getByRole('heading', { name: 'Демо-специалист' })).toBeVisible()
  const response = page.waitForResponse(
    (r) => r.url().includes('/specialists/demo/slots?') && r.status() === 200,
  )
  await page.getByRole('button', { name: 'Завтра', exact: true }).click()
  expect((await response).request().method()).toBe('GET')
  const times = page.getByRole('group', { name: 'Доступное время', exact: true })
  await expect(times.getByRole('button')).toHaveCount(4)
  await times.getByRole('button', { name: '10:00', exact: true }).click()
  await expect(times.getByRole('button', { name: '10:00', exact: true })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  await expect(
    page.getByText(`${dateLabel(tomorrow())} · 10:00–10:30`, { exact: true }),
  ).toBeVisible()
  await expect(page.getByText('Время не забронировано.', { exact: false })).toBeVisible()
  await expect(page.getByText('Asia/Omsk · UTC+06:00', { exact: true })).toBeVisible()
  for (const width of [390, 768, 1440]) {
    await page.setViewportSize({ width, height: 1000 })
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    ).toBe(true)
    await page.screenshot({ path: testInfo.outputPath(`specialist-${width}.png`), fullPage: true })
  }
  await page.getByRole('button', { name: 'Сегодня', exact: true }).click()
  await expect(page.getByText('Выберите дату и время', { exact: true })).toBeVisible()
  await expect(page.getByText('Свободного времени нет', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Следующий день', exact: false })).toBeVisible()
  const missing = await request.get('/api/v1/bookings')
  expect(missing.status()).toBe(404)
  expect(errors).toEqual([])
})

test('keyboard selection and date dialog with focus return', async ({ page }) => {
  await page.goto('/')
  await expect(page).toHaveURL(/\/s\/demo$/)
  await page.getByRole('button', { name: 'Завтра', exact: true }).focus()
  await page.keyboard.press('Enter')
  const time = page
    .getByRole('group', { name: 'Доступное время', exact: true })
    .getByRole('button', { name: '10:30' })
  await time.focus()
  await page.keyboard.press('Enter')
  await expect(time).toHaveAttribute('aria-pressed', 'true')
  await page.getByRole('button', { name: 'Перейти к дате', exact: true }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.getByLabel('Дата встречи').fill(addDays(tomorrow(), 1))
  await page.getByRole('button', { name: 'Показать дату' }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Перейти к дате', exact: true })).toBeFocused()
  await expect(page.getByText('Свободного времени нет', { exact: true })).toBeVisible()
  await expect(page.getByText('Выберите дату и время', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Перейти к дате', exact: true }).click()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).toHaveCount(0)
})

test('profile loading and slot failure recover via real API', async ({ page }) => {
  let release: () => void = () => {}
  const gate = new Promise<void>((resolve) => {
    release = resolve
  })
  await page.route('**/api/v1/specialists/demo', async (route) => {
    await gate
    await route.continue()
  })
  await page.goto('/s/demo')
  await expect(page.getByRole('status', { name: 'Загружаем профиль' })).toBeVisible()
  release()
  await expect(page.getByRole('heading', { name: 'Демо-специалист' })).toBeVisible()
  await page.route('**/api/v1/specialists/demo/slots?*', (route) => route.abort('failed'))
  await page.getByRole('button', { name: 'Завтра', exact: true }).click()
  await expect(page.getByText('Не удалось загрузить время', { exact: true })).toBeVisible()
  await page.unroute('**/api/v1/specialists/demo/slots?*')
  await page.getByRole('button', { name: 'Повторить попытку', exact: true }).click()
  await expect(
    page.getByRole('group', { name: 'Доступное время', exact: true }).getByRole('button'),
  ).toHaveCount(4)
})

test('unknown specialist is a real 404; unknown route is usable', async ({ page }) => {
  let count = 0
  // StrictMode may abort the first request; count completed 404 responses only.
  page.on('response', (r) => {
    if (r.url().endsWith('/specialists/nonexistent') && r.status() === 404) count++
  })
  await page.goto('/s/nonexistent')
  await expect(page.getByText('Специалист не найден', { exact: true })).toBeVisible()
  expect(count).toBe(1)
  await page.goto('/missing-page')
  await expect(page.getByText('Страница не найдена', { exact: true })).toBeVisible()
  await page.getByRole('link', { name: 'К расписанию' }).click()
  await expect(page.getByRole('heading', { name: 'Демо-специалист' })).toBeVisible()
})

test('a new date never displays the old slots while waiting', async ({ page }) => {
  await page.goto('/s/demo')
  await page.getByRole('button', { name: 'Завтра', exact: true }).click()
  await page
    .getByRole('group', { name: 'Доступное время', exact: true })
    .getByRole('button', { name: '10:00' })
    .click()
  let release: () => void = () => {}
  const gate = new Promise<void>((resolve) => {
    release = resolve
  })
  await page.route('**/api/v1/specialists/demo/slots?*', async (route) => {
    await gate
    await route.continue()
  })
  await page.getByRole('button', { name: 'Перейти к дате', exact: true }).click()
  await page.getByLabel('Дата встречи').fill(addDays(tomorrow(), 1))
  await page.getByRole('button', { name: 'Показать дату' }).click()
  await expect(page.getByRole('status', { name: 'Загружаем свободное время' })).toBeVisible()
  await expect(page.getByRole('group', { name: 'Доступное время', exact: true })).toHaveCount(0)
  await expect(page.getByText('Выберите дату и время', { exact: true })).toBeVisible()
  release()
  await expect(page.getByText('Свободного времени нет', { exact: true })).toBeVisible()
})
