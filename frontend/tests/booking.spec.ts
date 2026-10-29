import { expect, test, type Page } from '@playwright/test'
import type { BookingCreated } from '../src/lib/api'

async function choose(page: Page, time = '10:00') {
  await page.goto('/s/demo')
  await page.getByRole('button', { name: 'Завтра', exact: true }).click()
  await page
    .getByRole('group', { name: 'Доступное время', exact: true })
    .getByRole('button', { name: time, exact: true })
    .click()
  await page.getByLabel('Ваше имя').fill('Анна Тестовая')
  await page.getByLabel('Email', { exact: true }).fill('anna@example.com')
}

test('real booking, secret link in StrictMode, explicit cancellation and rebooking', async ({
  page,
  context,
  request,
}, testInfo) => {
  const created: BookingCreated[] = []
  const messages: string[] = []
  const urls: string[] = []
  const pageErrors: string[] = []
  let creates = 0
  let cancels = 0
  page.on('console', (m) => messages.push(m.text()))
  page.on('pageerror', (e) => pageErrors.push(e.message))
  page.on('request', (r) => {
    urls.push(r.url())
    if (r.method() === 'POST' && r.url().endsWith('/api/v1/bookings')) creates++
    if (r.method() === 'POST' && r.url().endsWith('/cancel')) cancels++
  })
  try {
    await choose(page)
    let release!: () => void
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    await page.route('**/api/v1/bookings', async (route) => {
      await gate
      await route.continue()
    })
    const response = page.waitForResponse(
      (r) => r.url().endsWith('/api/v1/bookings') && r.status() === 201,
    )
    await page.getByRole('button', { name: 'Подтвердить запись' }).dblclick()
    await expect(page.getByRole('button', { name: 'Записываем…' })).toBeDisabled()
    await expect(page.getByRole('button', { name: 'Сегодня', exact: true })).toBeDisabled()
    release()
    created.push(await (await response).json())
    await expect(page.getByRole('heading', { name: 'Вы записаны' })).toBeVisible()
    expect(creates).toBe(1)
    const link = await page.getByLabel('Сохраните ссылку на запись').inputValue()
    expect(new URL(link).hash).toBe(`#token=${created[0].manage_token}`)
    await context.grantPermissions(['clipboard-read', 'clipboard-write'])
    await page.getByRole('button', { name: 'Копировать ссылку' }).click()
    await expect(page.getByText('Ссылка скопирована.', { exact: true })).toBeVisible()
    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(link)
    // Also cover clipboard denial with a manual fallback.
    await page.evaluate(() => {
      navigator.clipboard.writeText = async () => {
        throw new Error('Denied')
      }
    })
    await page.getByRole('button', { name: 'Копировать ссылку' }).click()
    await expect(
      page.getByText('Не удалось скопировать автоматически.', { exact: false }),
    ).toBeVisible()
    for (const width of [390, 768, 1440]) {
      await page.setViewportSize({ width, height: 1000 })
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
        true,
      )
      await page.screenshot({
        path: testInfo.outputPath(`confirmation-${width}.png`),
        fullPage: true,
      })
    }
    await page.getByRole('link', { name: 'Управлять записью' }).click()
    await expect(page.getByRole('heading', { name: 'Запись подтверждена' })).toBeVisible()
    expect(new URL(page.url()).hash).toBe('')
    expect(cancels).toBe(0)
    expect(await page.evaluate(() => [localStorage.length, sessionStorage.length])).toEqual([0, 0])
    expect(await page.evaluate(() => JSON.stringify(history.state))).not.toContain(
      created[0].manage_token,
    )
    await page.reload()
    await expect(page.getByText('Откройте сохранённую ссылку', { exact: true })).toBeVisible()
    await page.goto(link)
    await expect(page.getByRole('heading', { name: 'Запись подтверждена' })).toBeVisible()
    await page.goto(`/manage/${created[0].id}#token=${'b'.repeat(43)}`)
    await expect(page.getByText('Запись недоступна', { exact: true })).toBeVisible()
    await expect(page.getByText('anna@example.com', { exact: true })).toHaveCount(0)
    await page.goto(link)
    await expect(page.getByRole('heading', { name: 'Запись подтверждена' })).toBeVisible()
    await page.getByRole('button', { name: 'Отменить запись', exact: true }).click()
    await page.getByRole('button', { name: 'Сохранить запись', exact: true }).click()
    expect(cancels).toBe(0)
    await expect(page.getByRole('button', { name: 'Отменить запись', exact: true })).toBeFocused()
    await page.getByRole('button', { name: 'Отменить запись', exact: true }).click()
    for (const width of [390, 768, 1440]) {
      await page.setViewportSize({ width, height: 1000 })
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
        true,
      )
      await page.screenshot({ path: testInfo.outputPath(`manage-${width}.png`), fullPage: true })
    }
    await page.getByRole('button', { name: 'Да, отменить встречу' }).dblclick()
    await expect(page.getByRole('heading', { name: 'Запись отменена' })).toBeVisible()
    expect(cancels).toBe(1)
    await page.unroute('**/api/v1/bookings')
    await choose(page)
    const rebooked = page.waitForResponse(
      (r) => r.url().endsWith('/api/v1/bookings') && r.status() === 201,
    )
    await page.getByRole('button', { name: 'Подтвердить запись' }).click()
    created.push(await (await rebooked).json())
    await expect(page.getByRole('heading', { name: 'Вы записаны' })).toBeVisible()
    expect(created[1].id).not.toBe(created[0].id)
    expect(created[1].slot_id).toBe(created[0].slot_id)
    for (const booking of created) {
      expect(messages.join('\n')).not.toContain(booking.manage_token)
      expect(urls.join('\n')).not.toContain(booking.manage_token)
    }
    expect(pageErrors).toEqual([])
  } finally {
    for (const booking of created)
      await request.post(`/api/v1/bookings/${booking.id}/cancel`, {
        headers: { Authorization: `Bearer ${booking.manage_token}` },
      })
  }
})

test('real conflict refreshes slots and lets the client choose another time', async ({
  page,
  request,
}) => {
  await choose(page, '10:30')
  // Another client wins after this browser has already selected the slot.
  const { dayFilters, todayIn, addDays } = await import('../src/lib/dates')
  const filters = dayFilters(addDays(todayIn('Asia/Omsk'), 1), 'Asia/Omsk')
  const slots = await (
    await request.get('/api/v1/specialists/demo/slots', { params: filters })
  ).json()
  const slot = slots.items.find(
    (item: { starts_at: string }) => new Date(item.starts_at).getUTCMinutes() === 30,
  )
  const winnerResponse = await request.post('/api/v1/bookings', {
    data: { slot_id: slot.id, client_name: 'Другой клиент', client_email: 'other@example.com' },
  })
  expect(winnerResponse.status()).toBe(201)
  const winner: BookingCreated = await winnerResponse.json()
  try {
    const conflict = page.waitForResponse(
      (r) => r.url().endsWith('/api/v1/bookings') && r.status() === 409,
    )
    await page.getByRole('button', { name: 'Подтвердить запись' }).click()
    await conflict
    await expect(page.getByText('Это время уже недоступно.', { exact: false })).toBeVisible()
    await expect(
      page
        .getByRole('group', { name: 'Доступное время', exact: true })
        .getByRole('button', { name: '10:30', exact: true }),
    ).toHaveCount(0)
    await page
      .getByRole('group', { name: 'Доступное время', exact: true })
      .getByRole('button', { name: '11:00', exact: true })
      .click()
    await expect(page.getByLabel('Ваше имя')).toBeVisible()
    await expect(page.getByText('Это время уже недоступно.', { exact: false })).toHaveCount(0)
  } finally {
    await request.post(`/api/v1/bookings/${winner.id}/cancel`, {
      headers: { Authorization: `Bearer ${winner.manage_token}` },
    })
  }
})

test('missing and wrong management secrets never expose a booking', async ({ page }) => {
  const id = '00000000-0000-4000-8000-000000000001'
  await page.goto(`/manage/${id}`)
  await expect(page.getByText('Откройте сохранённую ссылку', { exact: true })).toBeVisible()
  await page.goto(`/manage/${id}#token=${'a'.repeat(43)}`)
  await expect(page.getByText('Запись недоступна', { exact: true })).toBeVisible()
  expect(new URL(page.url()).hash).toBe('')
  await expect(page.getByRole('button', { name: 'Отменить запись', exact: true })).toHaveCount(0)
})

test('cancellation failures keep the booking and do not retry POST', async ({ page, request }) => {
  await choose(page, '11:30')
  const response = page.waitForResponse(
    (r) => r.url().endsWith('/api/v1/bookings') && r.status() === 201,
  )
  await page.getByRole('button', { name: 'Подтвердить запись' }).click()
  const booking: BookingCreated = await (await response).json()
  try {
    await page.getByRole('link', { name: 'Управлять записью' }).click()
    await expect(page.getByRole('heading', { name: 'Запись подтверждена' })).toBeVisible()
    let attempts = 0
    await page.route('**/cancel', async (route) => {
      attempts++
      await route.fulfill({
        status: 409,
        json: { error: { code: 'booking_started', message: 'Started', request_id: 'test' } },
      })
    })
    await page.getByRole('button', { name: 'Отменить запись', exact: true }).click()
    await page.getByRole('button', { name: 'Да, отменить встречу' }).click()
    await expect(page.getByText('Встреча уже началась. Отменить её нельзя.')).toBeVisible()
    expect(attempts).toBe(1)
    await page.unroute('**/cancel')
    await page.route('**/cancel', (route) => {
      attempts++
      return route.abort('failed')
    })
    await page.getByRole('button', { name: 'Да, отменить встречу' }).click()
    await expect(page.getByText('Не удалось подтвердить отмену.', { exact: false })).toBeVisible()
    expect(attempts).toBe(2)
    await page.getByRole('button', { name: 'Сохранить запись', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Запись подтверждена' })).toBeVisible()
    await page.unroute('**/cancel')
    await page.getByRole('button', { name: 'Отменить запись', exact: true }).click()
    await page.getByRole('button', { name: 'Да, отменить встречу' }).click()
    await expect(page.getByRole('heading', { name: 'Запись отменена' })).toBeVisible()
  } finally {
    await request.post(`/api/v1/bookings/${booking.id}/cancel`, {
      headers: { Authorization: `Bearer ${booking.manage_token}` },
    })
  }
})
