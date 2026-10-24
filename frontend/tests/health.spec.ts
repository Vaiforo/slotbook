import { expect, test } from '@playwright/test'

test('React reads the real API through Vite and refreshes it', async ({ page, request }, testInfo) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  const responsePromise = page.waitForResponse('/health/live')
  await page.goto('/')
  const response = await responsePromise
  expect(response.status()).toBe(200)
  expect(await response.json()).toEqual({ status: 'ok', service: 'SlotBook' })
  await expect(page.getByRole('status')).toContainText('API доступен')
  await expect(page.getByRole('status')).toContainText('Сервис SlotBook ответил: ok.')

  const refresh = page.waitForResponse('/health/live')
  await page.getByRole('button', { name: 'Проверить ещё раз' }).click()
  expect((await refresh).status()).toBe(200)
  await expect(page.getByRole('status')).toContainText('API доступен')

  const missing = await request.get('/api/v1/bookings')
  expect(missing.status()).toBe(404)
  expect(missing.headers()['content-type']).toContain('application/json')

  for (const width of [390, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
    await page.screenshot({ path: testInfo.outputPath(`health-${width}.png`), fullPage: true })
  }
  await page.getByRole('button').focus()
  await expect(page.getByRole('button')).toBeFocused()
  expect(errors).toEqual([])
})

test('a failed request is visible and retry returns to the real API', async ({ page }) => {
  // Transport failure is injected only in this test; success uses the real backend.
  await page.route('**/health/live', (route) => route.abort('failed'))
  await page.goto('/')
  await expect(page.getByRole('status')).toContainText('API недоступен')
  await page.unroute('**/health/live')
  await page.getByRole('button', { name: 'Проверить ещё раз' }).click()
  await expect(page.getByRole('status')).toContainText('API доступен')
})
