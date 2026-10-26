import { Temporal } from '@js-temporal/polyfill'
import type { SlotFilters } from './api'

export function todayIn(timezone: string): string {
  return Temporal.Now.zonedDateTimeISO(timezone).toPlainDate().toString()
}
export function addDays(date: string, days: number): string {
  return Temporal.PlainDate.from(date).add({ days }).toString()
}
export function dayFilters(date: string, timezone: string): SlotFilters {
  const day = Temporal.PlainDate.from(date)
  return {
    from: day.toZonedDateTime(timezone).toInstant().toString(),
    to: day.add({ days: 1 }).toZonedDateTime(timezone).toInstant().toString(),
    limit: 100,
    offset: 0,
  }
}
export function dateLabel(
  date: string,
  options: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'long' },
): string {
  return new Intl.DateTimeFormat('ru-RU', { ...options, timeZone: 'UTC' }).format(
    new Date(`${date}T12:00:00Z`),
  )
}
export function timeLabel(timestamp: string, timezone: string): string {
  return new Intl.DateTimeFormat('ru-RU', {
    timeZone: timezone,
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(timestamp))
}
export function zoneLabel(date: string, timezone: string): string {
  return `${timezone} · UTC${Temporal.PlainDate.from(date).toZonedDateTime(timezone).offset}`
}
export function calendarDays(month: string): (string | null)[] {
  const first = Temporal.PlainYearMonth.from(month).toPlainDate({ day: 1 })
  return [
    ...Array<null>(first.dayOfWeek - 1).fill(null),
    ...Array.from({ length: first.daysInMonth }, (_, day) => first.add({ days: day }).toString()),
  ]
}
export function shiftMonth(month: string, count: number): string {
  return Temporal.PlainYearMonth.from(month).add({ months: count }).toString()
}
