import { expect, type Page } from '@playwright/test'
export async function login(
  page: Page,
  email = 'demo@example.invalid',
  password = 'browser-owner-password',
) {
  await expect(page.getByRole('heading', { name: 'Войти в SlotBook' })).toBeVisible()
  await page.getByLabel('Email', { exact: true }).fill(email)
  await page.getByLabel('Пароль', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Войти', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Выйти', exact: true })).toBeVisible()
}
