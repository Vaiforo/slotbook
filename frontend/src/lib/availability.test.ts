import { QueryClient } from '@tanstack/react-query'
import { expect, it } from 'vitest'
import { invalidateAvailability } from './availability'

it('invalidates catalog, public schedule and private schedule together', async () => {
  const client = new QueryClient()
  const keys = [
    ['catalog', 'page'],
    ['specialists', 'slug', 'slots', 'date'],
    ['owner', 'user', 'slots'],
  ]
  for (const key of keys) client.setQueryData(key, {})
  client.setQueryData(['specialists', 'other'], {})
  await invalidateAvailability(client, 'user', 'slug')
  for (const key of keys) expect(client.getQueryState(key)?.isInvalidated).toBe(true)
  expect(client.getQueryState(['specialists', 'other'])?.isInvalidated).toBe(false)
})
