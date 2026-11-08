import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useOutletContext } from 'react-router-dom'
import { request } from '@/lib/api'
import type { Identity } from '@/lib/owner-api'
import type { components } from '@/generated/api-types'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { dayFilters } from '@/lib/dates'

type Page = components['schemas']['ClientBookingPage']
export function MyBookingsPage({ overview = false }: { overview?: boolean }) {
  const user = useOutletContext<Identity>()
  const cache = useQueryClient()
  const [view, setView] = useState('upcoming')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [offset, setOffset] = useState(0)
  const [busy, setBusy] = useState<string | null>(null)
  const [message, setMessage] = useState('')
  const query = new URLSearchParams({ view, limit: overview ? '1' : '20', offset: String(offset) })
  if (from) query.set('from', dayFilters(from, user.timezone).from)
  if (to) query.set('to', dayFilters(to, user.timezone).to)
  const bookings = useQuery({
    queryKey: ['owner', user.id, 'client-bookings', query.toString()],
    queryFn: ({ signal }) => request<Page>(`/me/bookings?${query}`, { signal }),
    gcTime: 0,
  })
  return (
    <section className="space-y-5">
      <h2 className="text-2xl font-semibold">{overview ? 'Ближайшая запись' : 'Мои записи'}</h2>
      {overview ? (
        <>
          <p>Предстоящих записей: {bookings.data?.upcoming_count ?? '…'}</p>
          <div className="flex gap-3">
            <Link to="/">Найти специалиста</Link>
            <Link to="/dashboard/bookings">Все мои записи</Link>
          </div>
        </>
      ) : (
        <Card className="flex flex-wrap gap-4 p-4">
          <label>
            Показать
            <select
              aria-label="Показать"
              className="block rounded border p-2"
              value={view}
              onChange={(e) => {
                setView(e.target.value)
                setOffset(0)
              }}
            >
              <option value="upcoming">Предстоящие</option>
              <option value="past">Прошедшие</option>
              <option value="cancelled">Отменённые</option>
            </select>
          </label>
          <label>
            С даты
            <Input
              type="date"
              value={from}
              onChange={(e) => {
                setFrom(e.target.value)
                setOffset(0)
              }}
            />
          </label>
          <label>
            По дату
            <Input
              type="date"
              value={to}
              onChange={(e) => {
                setTo(e.target.value)
                setOffset(0)
              }}
            />
          </label>
        </Card>
      )}
      {bookings.isPending && <p role="status">Загружаем записи…</p>}
      {bookings.isError && (
        <p role="alert">
          Не удалось загрузить записи.{' '}
          <Button onClick={() => void bookings.refetch()}>Повторить</Button>
        </p>
      )}
      {bookings.data?.items.length === 0 && <p>Записей пока нет.</p>}
      {bookings.data?.items.map((booking) => (
        <Card key={booking.id} className="space-y-3 break-words p-5">
          <h3 className="text-xl font-semibold">{booking.specialist_name}</h3>
          <p>{booking.specialization}</p>
          <p>
            {new Intl.DateTimeFormat('ru', {
              dateStyle: 'long',
              timeStyle: 'short',
              timeZone: user.timezone,
            }).format(new Date(booking.starts_at))}{' '}
            —{' '}
            {new Intl.DateTimeFormat('ru', { timeStyle: 'short', timeZone: user.timezone }).format(
              new Date(booking.ends_at),
            )}{' '}
            ({user.timezone})
          </p>
          <p>
            Статус:{' '}
            {booking.status === 'cancelled'
              ? 'Отменена'
              : new Date(booking.ends_at) <= new Date()
                ? 'Прошедшая'
                : 'Подтверждена'}
          </p>
          <p>
            {booking.workplace || booking.service_area || 'Место и формат уточняются у специалиста'}
          </p>
          <p>
            Формат:{' '}
            {booking.work_formats
              .split(',')
              .map((f) => ({ office: 'Очно', online: 'Онлайн', visit: 'Выезд' })[f])
              .join(', ')}
          </p>
          <p>
            {booking.client_name} · {booking.client_email}
          </p>
          <Link to={`/s/${booking.specialist_slug}`}>Профиль специалиста</Link>
          {booking.status === 'confirmed' && new Date(booking.starts_at) > new Date() && (
            <div>
              <Button
                variant="outline"
                disabled={busy !== null}
                onClick={async () => {
                  if (!window.confirm('Отменить эту запись?')) return
                  setBusy(booking.id)
                  setMessage('')
                  try {
                    await request(`/me/bookings/${booking.id}/cancel`, {
                      method: 'POST',
                      csrfToken: user.csrf_token,
                      signal: AbortSignal.timeout(15000),
                    })
                    await cache.invalidateQueries({
                      queryKey: ['owner', user.id, 'client-bookings'],
                    })
                    void cache.invalidateQueries({ queryKey: ['specialists'] })
                    void cache.invalidateQueries({ queryKey: ['catalog'] })
                    setMessage('Запись отменена')
                  } catch {
                    setMessage('Не удалось отменить запись. Обновите список и повторите попытку.')
                  } finally {
                    setBusy(null)
                  }
                }}
              >
                Отменить запись
              </Button>
            </div>
          )}
        </Card>
      ))}
      <p role="status">{message}</p>
      {!overview && (
        <div className="flex gap-3">
          <Button
            variant="outline"
            disabled={!offset}
            onClick={() => setOffset(Math.max(0, offset - 20))}
          >
            Назад
          </Button>
          <Button
            variant="outline"
            disabled={!bookings.data || offset + 20 >= bookings.data.total}
            onClick={() => setOffset(offset + 20)}
          >
            Далее
          </Button>
        </div>
      )}
    </section>
  )
}
