import { request, type SlotFilters } from './api'
import type { components } from '@/generated/api-types'

export type Identity = components['schemas']['Identity']
export type ScheduleSlot = components['schemas']['ScheduleSlot']
export type OwnerSlots = components['schemas']['OwnerSlots']
export type OwnerBookings = components['schemas']['OwnerBookings']
export type SlotCreate = components['schemas']['SlotCreate']
export type BookingFilters = SlotFilters & { status?: 'confirmed' | 'cancelled' }
export const sessionKey = ['owner', 'session'] as const
export const ownerKey = (id: string) => ['owner', id] as const

export const currentOwner = (signal?: AbortSignal) => request<Identity>('/auth/me', { signal })
export const loginOwner = (data: components['schemas']['Login']) =>
  request<void>('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
    signal: AbortSignal.timeout(15_000),
  })
export const logoutOwner = (csrfToken: string) =>
  request<void>('/auth/logout', { method: 'POST', csrfToken, signal: AbortSignal.timeout(15_000) })
function query(filters: BookingFilters) {
  const params = new URLSearchParams({
    from: filters.from,
    to: filters.to,
    limit: String(filters.limit ?? 100),
    offset: String(filters.offset ?? 0),
  })
  if (filters.status) params.set('status', filters.status)
  return params.toString()
}
export const ownerSlots = (filters: SlotFilters, signal?: AbortSignal) =>
  request<OwnerSlots>(`/me/slots?${query(filters)}`, { signal })
export const ownerBookings = (filters: BookingFilters, signal?: AbortSignal) =>
  request<OwnerBookings>(`/me/bookings?${query(filters)}`, { signal })
export const publishSlot = (data: SlotCreate, csrfToken: string) =>
  request<components['schemas']['OwnerSlot']>('/slots', {
    method: 'POST',
    csrfToken,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
    signal: AbortSignal.timeout(15_000),
  })
export const changeSlot = (id: string, state: 'open' | 'closed', csrfToken: string) =>
  request<components['schemas']['OwnerSlot']>(`/slots/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    csrfToken,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ state }),
    signal: AbortSignal.timeout(15_000),
  })
