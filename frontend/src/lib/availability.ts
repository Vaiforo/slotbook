import type { QueryClient } from '@tanstack/react-query'

export function invalidateAvailability(client: QueryClient, ownerId: string, slug: string) {
  return Promise.all([
    client.invalidateQueries({ queryKey: ['owner', ownerId] }),
    client.invalidateQueries({ queryKey: ['catalog'] }),
    client.invalidateQueries({ queryKey: ['specialists', slug] }),
  ])
}
