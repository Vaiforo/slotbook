import { dayFilters } from './dates'

export function clientBookingRange(from: string, to: string, timezone: string) {
  try {
    for (const value of [from, to]) {
      if (
        value &&
        (!/^\d{4}-\d{2}-\d{2}$/.test(value) || value < '1900-01-01' || value > '9998-12-31')
      )
        throw new Error('date')
    }
    if (from && to && from > to) throw new Error('range')
    return {
      from: from ? dayFilters(from, timezone).from : '',
      to: to ? dayFilters(to, timezone).to : '',
      error: '',
    }
  } catch {
    return {
      from: '',
      to: '',
      error: 'Укажите корректный период с 1900 по 9998 год. Начало должно быть не позже окончания.',
    }
  }
}
