import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, getAvailableSlots, getSpecialist, request } from './api'
import { queryKeys } from './query-keys'

const filters = { from: '2030-01-01T10:00:00+06:00', to: '2030-01-02T10:00:00+06:00' }
afterEach(() => vi.unstubAllGlobals())

describe('HTTP client', () => {
  it('encodes filters and slug, sends same-origin credentials and cancellation', async () => {
    const fetch = vi.fn().mockResolvedValue(Response.json({ items: [], limit: 100, offset: 0 }))
    vi.stubGlobal('fetch', fetch)
    const signal = new AbortController().signal
    await getAvailableSlots('a/b', filters, signal)
    const [path, init] = fetch.mock.calls[0]
    expect(path).toContain('/api/v1/specialists/a%2Fb/slots?')
    expect(new URL(path, 'http://test').searchParams.get('from')).toBe(filters.from)
    expect(init.signal).toBe(signal)
    expect(init.credentials).toBe('same-origin')
    expect(fetch).toHaveBeenCalledTimes(1)
  })
  it('preserves typed errors and never retries', async () => {
    const fetch = vi.fn().mockResolvedValue(
      Response.json(
        {
          error: {
            code: 'not_found',
            message: 'Not Found',
            request_id: 'id-123',
          },
        },
        { status: 404 },
      ),
    )
    vi.stubGlobal('fetch', fetch)
    await expect(getSpecialist('missing')).rejects.toMatchObject({
      name: 'ApiError',
      status: 404,
      code: 'not_found',
      requestId: 'id-123',
    })
    expect(fetch).toHaveBeenCalledTimes(1)
  })
  it('handles non-JSON proxy errors without exposing the response', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response('PRIVATE PROXY DETAILS', { status: 502 })),
    )
    await expect(getSpecialist('demo')).rejects.toMatchObject({
      code: 'invalid_response',
      status: 502,
    })
  })
  it('does not retry an aborted request', async () => {
    const abort = new DOMException('Aborted', 'AbortError')
    const fetch = vi.fn().mockRejectedValue(abort)
    vi.stubGlobal('fetch', fetch)
    await expect(getSpecialist('demo')).rejects.toBe(abort)
    expect(fetch).toHaveBeenCalledTimes(1)
  })
  it('supports 204 and adds CSRF only for mutations', async () => {
    const fetch = vi
      .fn()
      .mockImplementation(() => Promise.resolve(new Response(null, { status: 204 })))
    vi.stubGlobal('fetch', fetch)
    await expect(
      request('/future', { method: 'POST', csrfToken: 'test-csrf' }),
    ).resolves.toBeUndefined()
    expect(fetch.mock.calls[0][1].headers.get('X-CSRF-Token')).toBe('test-csrf')
    await request('/future', { csrfToken: 'test-csrf' })
    expect(fetch.mock.calls[1][1].headers.has('X-CSRF-Token')).toBe(false)
  })
  it('rejects malformed JSON error shapes safely', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(Response.json({ detail: 'PRIVATE' }, { status: 500 })),
    )
    await expect(getSpecialist('demo')).rejects.toBeInstanceOf(ApiError)
  })
})

it('keys distinguish filters and normalize default pagination', () => {
  expect(queryKeys.slots('demo', filters)).toEqual(
    queryKeys.slots('demo', { ...filters, limit: 100, offset: 0 }),
  )
  expect(queryKeys.slots('demo', filters)).not.toEqual(
    queryKeys.slots('demo', { ...filters, offset: 1 }),
  )
  expect(queryKeys.slots('demo', filters)).not.toEqual(queryKeys.slots('other', filters))
})

it('query retries are bounded and never repeat client errors', async () => {
  const { queryClient } = await import('../app/query-client')
  const retry = queryClient.getDefaultOptions().queries?.retry
  if (typeof retry !== 'function') throw new Error('Expected an explicit retry policy')
  for (const status of [401, 403, 404, 422]) {
    expect(retry(0, new ApiError(status, 'client_error', 'Test'))).toBe(false)
  }
  expect(retry(0, new ApiError(500, 'internal_error', 'Test'))).toBe(true)
  expect(retry(1, new ApiError(500, 'internal_error', 'Test'))).toBe(false)
  expect(retry(0, new TypeError('Network failure'))).toBe(true)
})

it('does not retry booking creation after a conflict', async () => {
  const { createBooking } = await import('./api')
  const fetch = vi.fn().mockResolvedValue(
    Response.json(
      {
        error: {
          code: 'slot_unavailable',
          message: 'Unavailable',
          request_id: 'test-id',
        },
      },
      { status: 409 },
    ),
  )
  vi.stubGlobal('fetch', fetch)
  await expect(
    createBooking({ slot_id: 'slot-id', client_name: 'Test', client_email: 'test@example.com' }),
  ).rejects.toMatchObject({ status: 409, code: 'slot_unavailable' })
  expect(fetch).toHaveBeenCalledTimes(1)
  expect(fetch.mock.calls[0][0]).toBe('/api/v1/bookings')
  expect(fetch.mock.calls[0][1].method).toBe('POST')
})

it('passes manage tokens only in Authorization for read and cancellation', async () => {
  const { getBooking, cancelBooking } = await import('./api')
  const fetch = vi
    .fn()
    .mockImplementation(() => Promise.resolve(Response.json({ status: 'cancelled' })))
  vi.stubGlobal('fetch', fetch)
  await getBooking('booking-id', 'private-token')
  await cancelBooking('booking-id', 'private-token')
  for (const [url, init] of fetch.mock.calls) {
    expect(url).not.toContain('private-token')
    expect(init.headers.get('Authorization')).toBe('Bearer private-token')
    expect(init.body).toBeUndefined()
  }
  expect(fetch.mock.calls[1][0]).toBe('/api/v1/bookings/booking-id/cancel')
  expect(fetch.mock.calls[1][1].method).toBe('POST')
})
