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
    const fetch = vi.fn().mockResolvedValue(Response.json({ error: {
      code: 'not_found', message: 'Not Found', request_id: 'id-123',
    } }, { status: 404 }))
    vi.stubGlobal('fetch', fetch)
    await expect(getSpecialist('missing')).rejects.toMatchObject({
      name: 'ApiError', status: 404, code: 'not_found', requestId: 'id-123',
    })
    expect(fetch).toHaveBeenCalledTimes(1)
  })
  it('handles non-JSON proxy errors without exposing the response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('PRIVATE PROXY DETAILS', { status: 502 })))
    await expect(getSpecialist('demo')).rejects.toMatchObject({ code: 'invalid_response', status: 502 })
  })
  it('does not retry an aborted request', async () => {
    const abort = new DOMException('Aborted', 'AbortError')
    const fetch = vi.fn().mockRejectedValue(abort)
    vi.stubGlobal('fetch', fetch)
    await expect(getSpecialist('demo')).rejects.toBe(abort)
    expect(fetch).toHaveBeenCalledTimes(1)
  })
  it('supports 204 and adds CSRF only for mutations', async () => {
    const fetch = vi.fn().mockImplementation(() => Promise.resolve(new Response(null, { status: 204 })))
    vi.stubGlobal('fetch', fetch)
    await expect(request('/future', { method: 'POST', csrfToken: 'test-csrf' })).resolves.toBeUndefined()
    expect(fetch.mock.calls[0][1].headers.get('X-CSRF-Token')).toBe('test-csrf')
    await request('/future', { csrfToken: 'test-csrf' })
    expect(fetch.mock.calls[1][1].headers.has('X-CSRF-Token')).toBe(false)
  })
  it('rejects malformed JSON error shapes safely', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({ detail: 'PRIVATE' }, { status: 500 })))
    await expect(getSpecialist('demo')).rejects.toBeInstanceOf(ApiError)
  })
})

it('keys distinguish filters and normalize default pagination', () => {
  expect(queryKeys.slots('demo', filters)).toEqual(queryKeys.slots('demo', { ...filters, limit: 100, offset: 0 }))
  expect(queryKeys.slots('demo', filters)).not.toEqual(queryKeys.slots('demo', { ...filters, offset: 1 }))
  expect(queryKeys.slots('demo', filters)).not.toEqual(queryKeys.slots('other', filters))
})
