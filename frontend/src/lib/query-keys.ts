import type { SlotFilters } from './api'

// Ready for TanStack Query in the public-page stage; include every server filter.
export const queryKeys = {
  specialist: (slug: string) => ['specialists', slug] as const,
  slots: (slug: string, filters: SlotFilters) => [
    'specialists', slug, 'slots',
    { ...filters, limit: filters.limit ?? 100, offset: filters.offset ?? 0 },
  ] as const,
}
