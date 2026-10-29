import type { QueryClient } from '@tanstack/react-query'
import { sessionKey } from './owner-api'

export function clearOwnerSession(client: QueryClient) {
  // Cancel before removal: a late HTTP response must not restore private data.
  void client.cancelQueries({ queryKey: ['owner'] })
  client.removeQueries({
    queryKey: ['owner'],
    predicate: (query) => query.queryKey[1] !== 'session',
  })
  for (const mutation of client.getMutationCache().getAll()) {
    if (mutation.options.mutationKey?.[0] === 'owner') client.getMutationCache().remove(mutation)
  }
  client.setQueryData(sessionKey, null)
}

export function loginDestination(search: string) {
  const next = new URLSearchParams(search).get('next')
  if (!next) return '/dashboard'
  try {
    const url = new URL(next, 'https://slotbook.invalid')
    return url.origin === 'https://slotbook.invalid' &&
      ['/dashboard', '/dashboard/schedule'].includes(url.pathname)
      ? url.pathname + url.search
      : '/dashboard'
  } catch {
    return '/dashboard'
  }
}
