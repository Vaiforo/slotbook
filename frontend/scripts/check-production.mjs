import { chromium, expect } from '@playwright/test'

const browser = await chromium.launch({
  executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH || undefined,
})
try {
  const page = await browser.newPage()
  const errors = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.goto(`${process.argv[2]}/dashboard`)
  await expect(page.getByRole('heading', { name: 'Войти в SlotBook' })).toBeVisible()
  await page.goto(`${process.argv[2]}/manage/00000000-0000-0000-0000-000000000000`)
  await expect(page.getByRole('heading', { name: 'Откройте сохранённую ссылку' })).toBeVisible()
  expect(errors).toEqual([])
  console.log('Production browser routes passed')
} finally {
  await browser.close()
}
