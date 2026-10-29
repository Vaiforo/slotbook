import { QueryClient } from '@tanstack/react-query'
import { expect, it, vi } from 'vitest'
import { clearOwnerSession, loginDestination } from './owner-session'
import { sessionKey } from './owner-api'

it('removes private cached data and cancels late responses on logout', async () => {
  const client = new QueryClient()
  client.setQueryData(['owner', 'one', 'bookings'], { client_email: 'private@example.com' })
  client.setQueryData(['specialists', 'demo'], { slug: 'demo' })
  let release!: (value: string) => void
  const abort = vi.fn()
  const pending = client
    .fetchQuery({
      queryKey: ['owner', 'two', 'slots'],
      queryFn: ({ signal }) => {
        signal.addEventListener('abort', abort)
        return new Promise<string>((resolve) => {
          release = resolve
        })
      },
    })
    .catch(() => undefined)
  clearOwnerSession(client)
  release('late private response')
  await pending
  expect(abort).toHaveBeenCalledOnce()
  expect(client.getQueryData(['owner', 'one', 'bookings'])).toBeUndefined()
  expect(client.getQueryData(['owner', 'two', 'slots'])).toBeUndefined()
  expect(client.getQueryData(sessionKey)).toBeNull()
  expect(client.getQueryData(['specialists', 'demo'])).toEqual({ slug: 'demo' })
})
it('only returns to supported internal dashboard routes', () => {
  expect(loginDestination('?next=%2Fdashboard%2Fschedule%3Fdate%3D2030-01-02')).toBe(
    '/dashboard/schedule?date=2030-01-02',
  )
  for (const next of [
    'https://evil.example',
    '//evil.example/dashboard',
    '/s/demo',
    '/dashboard/../login',
  ])
    expect(loginDestination(`?next=${encodeURIComponent(next)}`)).toBe('/dashboard')
})

it('notifies an active session observer when access expires', async () => {
  const { QueryObserver } = await import('@tanstack/react-query')
  const client = new QueryClient()
  client.setQueryData(sessionKey, { id: 'old-owner' })
  const observer = new QueryObserver(client, { queryKey: sessionKey, enabled: false })
  const changes = vi.fn()
  const unsubscribe = observer.subscribe(changes)
  clearOwnerSession(client)
  expect(observer.getCurrentResult().data).toBeNull()
  expect(changes).toHaveBeenCalled()
  unsubscribe()
})
