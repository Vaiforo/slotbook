import type { SlotFilters } from './api'

// Include every server filter in the cache identity.
export const queryKeys = {
  specialist: (slug: string) => ['specialists', slug] as const,
  slots: (slug: string, filters: SlotFilters) => [
    'specialists', slug, 'slots',
    { ...filters, limit: filters.limit ?? 100, offset: filters.offset ?? 0 },
  ] as const,
}
