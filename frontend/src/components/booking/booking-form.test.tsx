// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import { BookingForm } from './booking-form'
import { ApiError, createBooking, type BookingCreated } from '@/lib/api'
import { sessionKey } from '@/lib/owner-api'

vi.mock('@/lib/api', async (original) => ({
  ...(await original<typeof import('@/lib/api')>()),
  createBooking: vi.fn(),
}))
vi.mock('@/lib/owner-api', async (original) => ({
  ...(await original<typeof import('@/lib/owner-api')>()),
  currentOwner: vi.fn(async () => null),
}))
afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})
function setup(authenticated = true) {
  const client = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity } } })
  client.setQueryData(
    sessionKey,
    authenticated
      ? {
          id: 'client',
          role: 'client',
          full_name: 'Анна',
          email: 'anna@example.com',
          csrf_token: 'csrf',
        }
      : null,
  )
  const onBooked = vi.fn(),
    onUnavailable = vi.fn()
  render(
    <MemoryRouter>
      <QueryClientProvider client={client}>
        <BookingForm
          date="2030-01-01"
          slotId="slot"
          onBooked={onBooked}
          onUnavailable={onUnavailable}
        />
      </QueryClientProvider>
    </MemoryRouter>,
  )
  return { user: userEvent.setup(), onBooked, onUnavailable }
}
it('shows account contacts and blocks duplicate submissions', async () => {
  let release!: (value: BookingCreated) => void
  vi.mocked(createBooking).mockImplementation(
    () =>
      new Promise((resolve) => {
        release = resolve
      }),
  )
  const { user, onBooked } = setup()
  expect(screen.getByLabelText('Ваше имя')).toHaveValue('Анна')
  expect(screen.getByLabelText('Email')).toHaveAttribute('readonly')
  await user.dblClick(screen.getByRole('button', { name: 'Подтвердить запись' }))
  expect(createBooking).toHaveBeenCalledTimes(1)
  expect(createBooking).toHaveBeenCalledWith({ slot_id: 'slot' }, expect.any(AbortSignal), 'csrf')
  release({ id: 'booking', manage_token: 'secret' } as BookingCreated)
  await waitFor(() => expect(onBooked).toHaveBeenCalledTimes(1))
})
it('asks guests to authenticate and preserves selection in the return URL', () => {
  setup(false)
  expect(screen.getByRole('link', { name: 'Войти' })).toHaveAttribute(
    'href',
    expect.stringContaining('next='),
  )
  expect(screen.queryByRole('button', { name: 'Подтвердить запись' })).not.toBeInTheDocument()
})
it('refreshes availability on conflict without retry', async () => {
  vi.mocked(createBooking).mockRejectedValue(new ApiError(409, 'slot_unavailable', 'Conflict'))
  const { user, onUnavailable } = setup()
  await user.click(screen.getByRole('button', { name: 'Подтвердить запись' }))
  await waitFor(() => expect(onUnavailable).toHaveBeenCalledTimes(1))
  expect(createBooking).toHaveBeenCalledTimes(1)
})
it('explains an uncertain network result without retry', async () => {
  vi.mocked(createBooking).mockRejectedValue(new TypeError('Failed to fetch'))
  const { user, onBooked } = setup()
  await user.click(screen.getByRole('button', { name: 'Подтвердить запись' }))
  expect(await screen.findByText('Запись могла сохраниться.', { exact: false })).toBeVisible()
  expect(createBooking).toHaveBeenCalledTimes(1)
  expect(onBooked).not.toHaveBeenCalled()
})
