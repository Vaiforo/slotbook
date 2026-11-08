import { test, expect } from '@playwright/test'

test('guest registers, returns to selected slot, books and cancels in the account', async ({
  page,
}) => {
  await page.goto('/s/demo')
  await expect(page).toHaveURL('/')
  await page.goto('/s/fixture')
  await page.getByRole('button', { name: 'Завтра', exact: true }).click()
  await page
    .getByRole('group', { name: 'Доступное время', exact: true })
    .getByRole('button', { name: '10:00', exact: true })
    .click()
  await expect(page.getByText('Войдите или зарегистрируйтесь, чтобы записаться.')).toBeVisible()
  await page.getByRole('link', { name: 'Зарегистрироваться', exact: true }).click()
  await page.getByRole('button', { name: 'Продолжить' }).click()
  await page.getByLabel('Имя', { exact: true }).fill('Клиент с кабинетом')
  await page.getByLabel('Email', { exact: true }).fill(`journey-${Date.now()}@example.com`)
  await page.getByLabel('Пароль', { exact: true }).fill('client-journey-password')
  await page.getByLabel('Повторите пароль').fill('client-journey-password')
  await page.getByRole('button', { name: 'Зарегистрироваться' }).click()
  await expect(page).toHaveURL(/\/s\/fixture\?date=.*slot=/)
  await expect(page.getByLabel('Ваше имя')).toHaveValue('Клиент с кабинетом')
  await page.getByRole('button', { name: 'Подтвердить запись' }).click()
  await expect(page.getByText('Вы записаны', { exact: true })).toBeVisible()
  await page.goto('/dashboard')
  await expect(page.getByText('Предстоящих записей: 1')).toBeVisible()
  await page.getByRole('link', { name: 'Мои записи', exact: true }).click()
  await expect(
    page.getByRole('heading', { name: 'Тестовый специалист', exact: true }),
  ).toBeVisible()
  page.once('dialog', (dialog) => dialog.accept())
  await page.getByRole('button', { name: 'Отменить запись' }).click()
  await expect(page.getByText('Запись отменена', { exact: true })).toBeVisible()
  await page.getByLabel('Показать', { exact: true }).selectOption('cancelled')
  await expect(page.getByText('Статус: Отменена')).toBeVisible()
})
