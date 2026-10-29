import { expect, test } from '@playwright/test'
import { login } from './helpers/owner'
import { addDays, todayIn } from '../src/lib/dates'

const date = () => addDays(todayIn('Asia/Omsk'), 3)

test('owner publishes, client books, owner sees booking and closes free time', async ({
  page,
  browser,
}, testInfo) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.goto(`/dashboard/schedule?date=${date()}`)
  await login(page)
  await expect(page).toHaveURL(new RegExp(`/dashboard/schedule\\?date=${date()}`))
  await expect(page.getByText('На этот день слотов нет', { exact: true })).toBeVisible()
  await page.getByLabel('Начало встречи').fill('13:00')
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
  await page.getByRole('button', { name: 'Опубликовать слот' }).dblclick()
  await expect(page.getByRole('button', { name: 'Публикуем…' })).toBeDisabled()
  release()
  await expect(
    page.getByText('Слот опубликован. Клиенты могут записаться.', { exact: true }),
  ).toBeVisible()
  expect(posts).toBe(1)
  await page.unroute('**/api/v1/slots')
  // Conflict is real: publish an overlapping slot, with no retry.
  await page.getByRole('button', { name: 'Опубликовать слот' }).click()
  await expect(page.getByText('Это время пересекается', { exact: false })).toBeVisible()
  await page.getByLabel('Начало встречи').fill('14:00')
  await page.getByRole('button', { name: 'Опубликовать слот' }).click()
  await expect(
    page.getByRole('list', { name: 'Слоты расписания' }).getByRole('listitem'),
  ).toHaveCount(2)
  const free = page.getByRole('listitem').filter({ hasText: '14:00–14:30' })
  await free.getByRole('button', { name: 'Закрыть слот' }).click()
  await page.getByRole('button', { name: 'Да, закрыть слот' }).click()
  await expect(free.getByText('Закрыт', { exact: true })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Перейти к содержимому' })).not.toBeFocused()
  await free.getByRole('button', { name: 'Открыть слот' }).click()
  await expect(free.getByText('Свободен', { exact: true })).toBeVisible()
  const guestContext = await browser.newContext({
    baseURL: 'http://127.0.0.1:5173',
    timezoneId: 'America/Los_Angeles',
    locale: 'ru-RU',
  })
  const guest = await guestContext.newPage()
  await guest.goto('/s/demo')
  await guest.getByRole('button', { name: 'Перейти к дате', exact: true }).click()
  await guest.getByLabel('Дата встречи').fill(date())
  await guest.getByRole('button', { name: 'Показать дату' }).click()
  await guest
    .getByRole('group', { name: 'Доступное время', exact: true })
    .getByRole('button', { name: '13:00', exact: true })
    .click()
  await guest.getByLabel('Ваше имя').fill('Клиент кабинета')
  await guest.getByLabel('Email', { exact: true }).fill('dashboard-client@example.com')
  await guest.getByRole('button', { name: 'Подтвердить запись' }).click()
  await expect(guest.getByRole('heading', { name: 'Вы записаны' })).toBeVisible()
  await guestContext.close()
  await page.getByRole('button', { name: 'Обновить расписание' }).click()
  await expect(page.getByText('Есть запись', { exact: true })).toBeVisible()
  await expect(
    page
      .getByRole('listitem')
      .filter({ hasText: '13:00–13:30' })
      .getByRole('button', { name: 'Закрыть слот' }),
  ).toBeDisabled()
  for (const width of [390, 768, 1440]) {
    await page.setViewportSize({ width, height: 1000 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.screenshot({ path: testInfo.outputPath(`schedule-${width}.png`), fullPage: true })
  }
  await page.getByRole('link', { name: 'Записи', exact: true }).click()
  await expect(page.getByText('dashboard-client@example.com', { exact: true })).toBeVisible()
  await page.getByLabel('С даты', { exact: true }).fill(date())
  await page.getByLabel('По дату включительно', { exact: true }).fill(date())
  await page.getByLabel('Статус', { exact: true }).selectOption('cancelled')
  await expect(page.getByText('Записей пока нет', { exact: true })).toBeVisible()
  await page.getByLabel('Статус', { exact: true }).selectOption('confirmed')
  await expect(page.getByText('dashboard-client@example.com', { exact: true })).toBeVisible()
  for (const width of [390, 768, 1440]) {
    await page.setViewportSize({ width, height: 1000 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.screenshot({ path: testInfo.outputPath(`bookings-${width}.png`), fullPage: true })
  }
  await page.getByRole('button', { name: 'Выйти', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Войти в SlotBook' })).toBeVisible()
  await expect(page.getByText('dashboard-client@example.com')).toHaveCount(0)
  await login(page, 'other@example.invalid', 'browser-other-password')
  await expect(page.getByRole('heading', { name: 'Другой специалист', exact: true })).toBeVisible()
  await expect(page.getByText('Записей пока нет', { exact: true })).toBeVisible()
  await expect(page.getByText('dashboard-client@example.com')).toHaveCount(0)
  await page.getByRole('link', { name: 'Расписание', exact: true }).click()
  await page.getByLabel('Дата', { exact: true }).fill(date())
  await expect(page.getByText('На этот день слотов нет', { exact: true })).toBeVisible()
  expect(await page.evaluate(() => [localStorage.length, sessionStorage.length])).toEqual([0, 0])
  expect(errors).toEqual([])
})

test('invalid login, expired session and network errors preserve the return route', async ({
  page,
  context,
}) => {
  const selectedDate = addDays(todayIn('Asia/Omsk'), 1)
  await page.goto(`/dashboard/schedule?date=${selectedDate}`)
  await page.getByLabel('Email', { exact: true }).fill('demo@example.invalid')
  await page.getByLabel('Пароль').fill('wrong-password')
  await page.getByRole('button', { name: 'Войти', exact: true }).click()
  await expect(page.getByText('Неверный email или пароль.', { exact: true })).toBeVisible()
  await login(page)
  await page.route('**/api/v1/me/slots?*', (route) => route.abort('failed'))
  await page.getByRole('button', { name: 'Обновить расписание' }).click()
  await expect(page.getByText('Не удалось загрузить расписание', { exact: true })).toBeVisible()
  await page.unroute('**/api/v1/me/slots?*')
  await page.getByRole('button', { name: 'Повторить попытку' }).click()
  await expect(page.getByRole('list', { name: 'Слоты расписания' })).toBeVisible()
  await context.clearCookies()
  await page.getByRole('button', { name: 'Обновить расписание' }).click()
  await expect(page.getByRole('heading', { name: 'Войти в SlotBook' })).toBeVisible()
  expect(new URL(page.url()).searchParams.get('next')).toBe(
    `/dashboard/schedule?date=${selectedDate}`,
  )
  await login(page)
  await expect(page.getByRole('heading', { name: 'Ваше расписание' })).toBeVisible()
  // A rejected mutation must keep the form usable, not pretend it succeeded.
  await page.route('**/api/v1/slots', (route) =>
    route.fulfill({
      status: 403,
      json: { error: { code: 'forbidden', message: 'Denied', request_id: 'test' } },
    }),
  )
  await page.getByLabel('Начало встречи').fill('15:00')
  await page.getByRole('button', { name: 'Опубликовать слот' }).click()
  await expect(page.getByText('Не удалось подтвердить доступ.', { exact: false })).toBeVisible()
  await expect(page.getByLabel('Начало встречи')).toHaveValue('15:00')
  await page.unroute('**/api/v1/slots')
})

test('an unauthorized mutation returns to login', async ({ page, context }) => {
  await page.goto('/dashboard/schedule')
  await login(page)
  await context.clearCookies()
  await page.getByRole('button', { name: 'Опубликовать слот' }).click()
  await expect(page.getByRole('heading', { name: 'Войти в SlotBook' })).toBeVisible()
})
