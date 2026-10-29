import { Temporal } from '@js-temporal/polyfill'
import { addDays, dayFilters } from './dates'

export function validDate(value: string | null, fallback: string) {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value) || value < '1900-01-01' || value > '9998-12-31')
    return fallback
  try {
    Temporal.PlainDate.from(value)
    return value
  } catch {
    return fallback
  }
}
export function weekDates(date: string) {
  const first = Temporal.PlainDate.from(date)
  const monday = first.subtract({ days: first.dayOfWeek - 1 })
  return Array.from({ length: 7 }, (_, i) => monday.add({ days: i }).toString())
}
export function bookingRange(from: string, through: string, timezone: string) {
  const count = Temporal.PlainDate.from(from).until(Temporal.PlainDate.from(through)).days
  if (count < 0 || count > 30) throw new Error('Выберите период от 1 до 31 дня.')
  const start = dayFilters(from, timezone).from
  const end = dayFilters(addDays(through, 1), timezone).from
  // The API limits elapsed time to 31 days, including DST changes.
  if (
    Temporal.Instant.from(end).epochMilliseconds - Temporal.Instant.from(start).epochMilliseconds >
    31 * 86400000
  )
    throw new Error('Сократите период: с учётом смены часового пояса он превышает 31 день.')
  return { from: start, to: end }
}
export function slotInput(date: string, time: string, timezone: string) {
  const start = Temporal.PlainDateTime.from(`${date}T${time}`)
    .toZonedDateTime(timezone, { disambiguation: 'reject' })
    .toInstant()
  return { starts_at: start.toString(), ends_at: start.add({ minutes: 30 }).toString() }
}
