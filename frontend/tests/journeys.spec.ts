import { expect, test } from '@playwright/test'
import { login } from './helpers/owner'
import { addDays, todayIn, timeLabel } from '../src/lib/dates'
import { slotInput } from '../src/lib/owner-dates'

const future = (days: number) => addDays(todayIn('Asia/Omsk'), days)

test('session recheck preserves a draft and a pending publication', async ({ page }) => {
  const date = future(10)
  await page.goto(`/dashboard/schedule?date=${date}`)
  await login(page)
  await page.getByLabel('Начало встречи').fill('17:15')
  async function recheck(preserveFocus = false) {
    let release!: () => void
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    await page.route('**/api/v1/auth/me', async (route) => {
      await gate
      await route.continue()
    })
    await page.evaluate(() => window.dispatchEvent(new Event('visibilitychange')))
    await expect(page.getByRole('status').filter({ hasText: 'Проверяем вход' })).toBeVisible()
    await expect(page.getByLabel('Начало встречи')).not.toBeVisible()
    release()
    await expect(page.getByLabel('Начало встречи')).toBeVisible()
    await expect(page.getByLabel('Начало встречи')).toHaveValue('17:15')
    if (preserveFocus) await expect(page.getByLabel('Начало встречи')).toBeFocused()
    await page.unroute('**/api/v1/auth/me')
  }
  await recheck(true)
  let release!: () => void
  const gate = new Promise<void>((resolve) => {
    release = resolve
  })
  let posts = 0
  await page.route('**/api/v1/slots', async (route) => {
    posts++
    await gate
    await route.continue()
  })
  await page.getByRole('button', { name: 'Опубликовать слот' }).click()
  await expect(page.getByRole('button', { name: 'Публикуем…' })).toBeDisabled()
  await recheck()
  await expect(page.getByRole('button', { name: 'Публикуем…' })).toBeDisabled()
  release()
  await expect(page.getByText('17:15–17:45', { exact: true })).toBeVisible()
  expect(posts).toBe(1)
  await page.getByRole('link', { name: 'Записи', exact: true }).click()
  await expect(page.locator('main')).toBeFocused()
})

test('a client wins before closing; cancellation frees the slot and stays isolated', async ({
  page,
  browser,
}, testInfo) => {
  const date = future(11)
  await page.goto(`/dashboard/schedule?date=${date}`)
  await login(page)
  const identity = await (await page.request.get('/api/v1/auth/me')).json()
  const origin = new URL(page.url()).origin
  const response = await page.request.post('/api/v1/slots', {
    headers: { Origin: origin, 'X-CSRF-Token': identity.csrf_token },
    data: slotInput(date, '09:00', 'Asia/Omsk'),
  })
  expect(response.status()).toBe(201)
  const slot = await response.json()
  await page.getByRole('button', { name: 'Обновить расписание' }).click()
  await page.getByRole('button', { name: 'Закрыть слот', exact: true }).click()
  const guest = await browser.newContext({
    baseURL: origin,
    timezoneId: 'America/Los_Angeles',
    locale: 'ru-RU',
  })
  try {
    expect((await guest.request.get('/api/v1/auth/me')).status()).toBe(401)
    const booked = await guest.request.post('/api/v1/bookings', {
      data: { slot_id: slot.id, client_name: 'Клиент гонки', client_email: 'race-ui@example.com' },
    })
    expect(booked.status()).toBe(201)
    const booking = await booked.json()
    await page.getByRole('button', { name: 'Да, закрыть слот' }).click()
    await expect(
      page.getByRole('dialog').getByText('На это время уже записался клиент.', { exact: false }),
    ).toBeVisible()
    // Small viewport + an error in the dialog must keep both choices reachable.
    await page.setViewportSize({ width: 390, height: 400 })
    await page.getByRole('button', { name: 'Оставить открытым' }).scrollIntoViewIfNeeded()
    await expect(page.getByRole('button', { name: 'Оставить открытым' })).toBeInViewport()
    await page.getByRole('button', { name: 'Оставить открытым' }).click()
    await expect(page.getByRole('heading', { name: 'Ваше расписание' })).toBeFocused()
    await expect(page.getByText('Есть запись', { exact: true })).toBeVisible()
    const manage = await guest.newPage()
    await manage.goto(`/manage/${booking.id}#token=${booking.manage_token}`)
    await expect(manage.getByRole('heading', { name: 'Запись подтверждена' })).toBeVisible()
    await expect(
      manage.getByText('Ваш часовой пояс: America/Los_Angeles.', { exact: false }),
    ).toBeVisible()
    await expect(
      manage.getByText(timeLabel(booking.starts_at, 'America/Los_Angeles'), { exact: false }),
    ).toBeVisible()
    await manage.getByRole('button', { name: 'Отменить запись', exact: true }).click()
    await manage.getByRole('button', { name: 'Да, отменить встречу' }).click()
    await expect(manage.getByRole('heading', { name: 'Запись отменена' })).toBeVisible()
    await expect(manage.getByRole('heading', { name: 'Запись отменена' })).toBeFocused()
    await page.getByRole('button', { name: 'Обновить расписание' }).click()
    await expect(page.getByText('Свободен', { exact: true })).toBeVisible()
    await page.getByRole('button', { name: 'Закрыть слот', exact: true }).click()
    await page.getByRole('button', { name: 'Да, закрыть слот' }).click()
    await expect(page.getByText('Закрыт', { exact: true })).toBeVisible()
    for (const width of [390, 768, 1440]) {
      await manage.setViewportSize({ width, height: 900 })
      await manage.evaluate(() => window.scrollTo(0, 0))
      expect(await manage.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
        true,
      )
      await manage.screenshot({
        path: testInfo.outputPath(`cancelled-${width}.png`),
        fullPage: true,
      })
    }
  } finally {
    await guest.close()
  }
})

test('navigation, keyboard focus, invalid date range and empty page recovery', async ({
  page,
}, testInfo) => {
  await page.goto('/login')
  await page.keyboard.press('Tab')
  await expect(page.getByRole('link', { name: 'Перейти к содержимому' })).toBeFocused()
  await page.keyboard.press('Enter')
  await expect(page.locator('main')).toBeFocused()
  for (const width of [390, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.screenshot({ path: testInfo.outputPath(`login-${width}.png`), fullPage: true })
  }
  await login(page, 'other@example.invalid', 'browser-other-password')
  await page.getByLabel('С даты', { exact: true }).fill(future(8))
  await page.getByLabel('По дату включительно', { exact: true }).fill(future(7))
  await expect(page.getByText('Выберите период от 1 до 31 дня.', { exact: true })).toBeVisible()
  await page.getByLabel('По дату включительно', { exact: true }).fill(future(8))
  await expect(page.getByText('Записей пока нет', { exact: true })).toBeVisible()
  await page.getByRole('link', { name: 'Расписание', exact: true }).click()
  await expect(page.locator('main')).toBeFocused()
  await page.getByRole('button', { name: 'Следующая неделя' }).focus()
  await page.keyboard.press('Enter')
  await expect(page.getByRole('button', { name: 'Следующая неделя' })).toBeFocused()
})
