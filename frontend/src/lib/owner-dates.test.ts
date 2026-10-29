import { describe, expect, it } from 'vitest'
import { bookingRange, slotInput, validDate, weekDates } from './owner-dates'

describe('owner calendar', () => {
  it('uses the specialist timezone regardless of browser time', () => {
    expect(slotInput('2030-01-02', '10:00', 'Asia/Omsk')).toEqual({
      starts_at: '2030-01-02T04:00:00Z',
      ends_at: '2030-01-02T04:30:00Z',
    })
    expect(bookingRange('2030-01-02', '2030-01-02', 'Asia/Omsk')).toEqual({
      from: '2030-01-01T18:00:00Z',
      to: '2030-01-02T18:00:00Z',
    })
  })
  it('rejects nonexistent and ambiguous local times instead of silently shifting', () => {
    expect(() => slotInput('2030-03-10', '02:30', 'America/New_York')).toThrow()
    expect(() => slotInput('2030-11-03', '01:30', 'America/New_York')).toThrow()
  })
  it('limits range and validates URL dates before rendering', () => {
    expect(() => bookingRange('2030-01-02', '2030-01-01', 'UTC')).toThrow()
    expect(() => bookingRange('2030-01-01', '2030-02-01', 'UTC')).toThrow()
    expect(validDate('2030-02-30', '2030-01-01')).toBe('2030-01-01')
    expect(weekDates('2030-01-02')[0]).toBe('2029-12-31')
  })
})
