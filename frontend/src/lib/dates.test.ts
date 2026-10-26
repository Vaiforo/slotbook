import { describe, expect, it, vi, afterEach } from 'vitest'
import {
  addDays,
  calendarDays,
  dayFilters,
  shiftMonth,
  timeLabel,
  todayIn,
  zoneLabel,
} from './dates'

afterEach(() => vi.useRealTimers())

describe('specialist timezone', () => {
  it('computes local today across a UTC day boundary', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2030-01-01T20:00:00Z'))
    expect(todayIn('Asia/Omsk')).toBe('2030-01-02')
    expect(todayIn('America/Los_Angeles')).toBe('2030-01-01')
  })
  it('uses local midnight as both query boundaries', () => {
    expect(dayFilters('2030-01-02', 'Asia/Omsk')).toEqual({
      from: '2030-01-01T18:00:00Z',
      to: '2030-01-02T18:00:00Z',
      limit: 100,
      offset: 0,
    })
    expect(timeLabel('2030-01-02T04:00:00Z', 'Asia/Omsk')).toBe('10:00')
    expect(zoneLabel('2030-01-02', 'Asia/Omsk')).toBe('Asia/Omsk · UTC+06:00')
  })
  it('handles 23 and 25 hour days without a fixed UTC offset', () => {
    for (const [date, hours] of [
      ['2026-03-08', 23],
      ['2026-11-01', 25],
    ] as const) {
      const range = dayFilters(date, 'America/New_York')
      expect((Date.parse(range.to) - Date.parse(range.from)) / 3600000).toBe(hours)
    }
  })
  it('handles leap days, month/year changes and Monday-first calendars', () => {
    expect(addDays('2028-02-28', 1)).toBe('2028-02-29')
    expect(addDays('2028-02-29', 1)).toBe('2028-03-01')
    expect(shiftMonth('2026-12', 1)).toBe('2027-01')
    const days = calendarDays('2026-11')
    expect(days.slice(0, 6)).toEqual(Array(6).fill(null))
    expect(days[6]).toBe('2026-11-01')
    expect(days.filter(Boolean)).toHaveLength(30)
  })
})
