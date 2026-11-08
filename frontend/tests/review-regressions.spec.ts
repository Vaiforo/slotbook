import { test, expect } from '@playwright/test'
import { login } from './helpers/owner'
import { authenticatePage } from './helpers/client'

test('profile draft survives background failures and recovery', async ({ page }) => {
  await page.clock.install()
  await page.goto('/dashboard/professional')
  await login(page)
  const field = page.getByLabel('Специализация', { exact: true })
  await field.fill('Несохранённый черновик')
  await page.route('**/api/v1/auth/me', (route) => route.abort())
  await page.route('**/api/v1/me/specialist', (route) =>
    route.request().method() === 'GET' ? route.abort() : route.continue(),
  )
  await page.clock.fastForward(16000)
  await page.evaluate(() => window.dispatchEvent(new Event('visibilitychange')))
  await expect(
    page.getByText('Не удалось обновить профиль. Черновик сохранён на экране.', { exact: true }),
  ).toBeVisible()
  await expect(field).toHaveValue('Несохранённый черновик')
  await expect(field).toBeVisible()
  await page.unroute('**/api/v1/auth/me')
  await page.unroute('**/api/v1/me/specialist')
  await page.evaluate(() => window.dispatchEvent(new Event('visibilitychange')))
  await expect(
    page.getByText('Не удалось обновить профиль. Черновик сохранён на экране.', { exact: true }),
  ).not.toBeVisible()
  await expect(field).toHaveValue('Несохранённый черновик')
})

test('invalid date does not crash client bookings', async ({ page }) => {
  await authenticatePage(page)
  await page.goto('/dashboard/bookings')
  await page.getByLabel('С даты', { exact: true }).fill('10000-01-01')
  await expect(page.getByRole('alert')).toContainText('Укажите корректный период')
  await page.getByLabel('С даты', { exact: true }).fill('')
  await expect(page.getByRole('heading', { name: 'Мои записи', exact: true })).toBeVisible()
  await expect(page.getByText('Записей пока нет.', { exact: true })).toBeVisible()
})
