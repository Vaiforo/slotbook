import { expect, it } from 'vitest'
import { clientBookingRange } from './client-booking-range'

it('rejects extreme, impossible and reversed dates without throwing', () => {
  for (const [from, to] of [
    ['10000-01-01', ''],
    ['2026-02-30', ''],
    ['2026-11-10', '2026-11-09'],
    ['', '9999-12-31'],
  ]) {
    expect(clientBookingRange(from, to, 'UTC').error).not.toBe('')
  }
})
it('uses local inclusive day bounds', () => {
  const range = clientBookingRange('2026-11-08', '2026-11-08', 'Asia/Omsk')
  expect(range).toEqual({ from: '2026-11-07T18:00:00Z', to: '2026-11-08T18:00:00Z', error: '' })
})
