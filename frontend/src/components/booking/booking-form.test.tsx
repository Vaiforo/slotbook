// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, expect, it, vi } from 'vitest'
import { BookingForm } from './booking-form'
import { ApiError, createBooking, type BookingCreated } from '@/lib/api'

vi.mock('@/lib/api', async (original) => ({
  ...(await original<typeof import('@/lib/api')>()),
  createBooking: vi.fn(),
}))
afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})
function setup() {
  const client = new QueryClient()
  const invalidation = vi.spyOn(client, 'invalidateQueries')
  const onBooked = vi.fn()
  const onUnavailable = vi.fn()
  render(
    <QueryClientProvider client={client}>
      <BookingForm slotId="slot" onBooked={onBooked} onUnavailable={onUnavailable} />
    </QueryClientProvider>,
  )
  return { user: userEvent.setup(), onBooked, onUnavailable, invalidation }
}
async function fill(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText('Ваше имя'), ' Анна ')
  await user.type(screen.getByLabelText('Email'), 'anna@example.com')
}
it('validates fields before sending, trims values and blocks duplicate submission while pending', async () => {
  let release!: (booking: BookingCreated) => void
  vi.mocked(createBooking).mockImplementation(
    () =>
      new Promise((resolve) => {
        release = resolve
      }),
  )
  const { user, onBooked, invalidation } = setup()
  await user.click(screen.getByRole('button', { name: 'Подтвердить запись' }))
  expect(await screen.findByText('Укажите имя.')).toBeVisible()
  expect(createBooking).not.toHaveBeenCalled()
  await fill(user)
  await user.dblClick(screen.getByRole('button', { name: 'Подтвердить запись' }))
  expect(screen.getByRole('button', { name: 'Записываем…' })).toBeDisabled()
  expect(createBooking).toHaveBeenCalledTimes(1)
  expect(createBooking).toHaveBeenCalledWith(
    { slot_id: 'slot', client_name: 'Анна', client_email: 'anna@example.com' },
    expect.any(AbortSignal),
  )
  release({ id: 'booking', manage_token: 'secret' } as BookingCreated)
  await waitFor(() => expect(onBooked).toHaveBeenCalledTimes(1))
  await waitFor(() => expect(invalidation).toHaveBeenCalled())
})
it('refreshes availability and asks for another slot on 409 without retry', async () => {
  vi.mocked(createBooking).mockRejectedValue(new ApiError(409, 'slot_unavailable', 'Conflict'))
  const { user, onUnavailable, invalidation, onBooked } = setup()
  await fill(user)
  await user.click(screen.getByRole('button', { name: 'Подтвердить запись' }))
  await waitFor(() => expect(onUnavailable).toHaveBeenCalledTimes(1))
  expect(invalidation).toHaveBeenCalledWith({
    queryKey: ['specialists'],
    predicate: expect.any(Function),
  })
  expect(createBooking).toHaveBeenCalledTimes(1)
  expect(onBooked).not.toHaveBeenCalled()
})
it.each([
  [new ApiError(422, 'validation_error', 'Invalid'), 'Сервер не принял данные.'],
  [new TypeError('Failed to fetch'), 'Запись могла сохраниться.'],
])('keeps entered values and explains a failure without retry: %s', async (error, message) => {
  vi.mocked(createBooking).mockRejectedValue(error)
  const { user, onBooked } = setup()
  await fill(user)
  await user.click(screen.getByRole('button', { name: 'Подтвердить запись' }))
  expect(await screen.findByText(message, { exact: false })).toBeVisible()
  expect(screen.getByLabelText('Email')).toHaveValue('anna@example.com')
  expect(screen.getByRole('button', { name: 'Подтвердить запись' })).toBeEnabled()
  expect(createBooking).toHaveBeenCalledTimes(1)
  expect(onBooked).not.toHaveBeenCalled()
})
