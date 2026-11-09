import { expect, type Page, type APIRequestContext } from '@playwright/test'

export async function authenticatePage(
  page: Page,
  name = 'Анна Тестовая',
  email = 'anna@example.com',
) {
  const actor = await authenticateRequest(page.request, name, email)
  return actor
}

async function authenticateRequest(request: APIRequestContext, name: string, email: string) {
  const origin = 'http://127.0.0.1:5173'
  const response = await request.post('/api/v1/auth/register', {
    headers: { Origin: origin },
    data: {
      full_name: name,
      email,
      password: 'browser-client-password',
      role: 'client',
      timezone: 'Asia/Omsk',
    },
  })
  if (response.status() === 409) {
    expect(
      (
        await request.post('/api/v1/auth/login', {
          headers: { Origin: origin },
          data: { email, password: 'browser-client-password' },
        })
      ).status(),
    ).toBe(204)
    return (await request.get('/api/v1/auth/me')).json()
  }
  expect(response.status(), await response.text()).toBe(201)
  return response.json()
}

export async function bookClient(
  request: APIRequestContext,
  options: { data: { slot_id: string; client_name?: string; client_email?: string } },
) {
  const identity = await authenticateRequest(
    request,
    options.data.client_name || 'Клиент',
    options.data.client_email || 'api-client@example.com',
  )
  return request.post('/api/v1/bookings', {
    ...options,
    headers: { Origin: 'http://127.0.0.1:5173', 'X-CSRF-Token': identity.csrf_token },
  })
}
