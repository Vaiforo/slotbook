import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { ownerBookings, ownerKey, type BookingFilters } from '@/lib/owner-api'
import { useOwner } from '@/lib/use-owner'
import { addDays, timeLabel, todayIn } from '@/lib/dates'
import { bookingRange, validDate } from '@/lib/owner-dates'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { EmptyState } from '@/components/ui/empty-state'

export function DashboardPage() {
  const owner = useOwner()
  const [params, setParams] = useSearchParams()
  const timezone = owner.specialist.timezone
  const today = todayIn(timezone)
  const from = validDate(params.get('from'), today)
  const to = validDate(params.get('to'), addDays(today, 6))
  const status = ['confirmed', 'cancelled'].includes(params.get('status') ?? '')
    ? (params.get('status') as BookingFilters['status'])
    : undefined
  const page = Math.min(500, Math.max(0, Math.floor(Number(params.get('page')) || 0)))
  let range = { from: '', to: '' }
  let rangeError = ''
  try {
    range = bookingRange(from, to, timezone)
  } catch (error) {
    rangeError = (error as Error).message
  }
  const filters = { ...range, status, limit: 20, offset: page * 20 }
  const bookings = useQuery({
    queryKey: [...ownerKey(owner.id), 'bookings', filters],
    queryFn: ({ signal }) =>
      ownerBookings(filters, AbortSignal.any([signal, AbortSignal.timeout(10_000)])),
    enabled: !rangeError && !owner.checkingSession,
    gcTime: 0,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })
  function filter(name: string, value: string) {
    setParams((prev) => {
      prev.set(name, value)
      prev.delete('page')
      return prev
    })
  }
  return (
    <section className="space-y-5" aria-labelledby="bookings-title">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 id="bookings-title" className="text-2xl font-semibold">
            Записи клиентов
          </h2>
          <p className="mt-2 text-sm text-muted-foreground">Дата и время: {timezone}</p>
        </div>
        <Button
          variant="outline"
          disabled={bookings.isFetching || !!rangeError}
          onClick={() => void bookings.refetch()}
        >
          Обновить записи
        </Button>
      </div>
      <Card className="grid gap-4 p-5 sm:grid-cols-3">
        <label className="space-y-2 text-sm">
          <span>С даты</span>
          <Input
            type="date"
            min="1900-01-01"
            max="9998-12-31"
            value={from}
            onChange={(e) => filter('from', e.target.value)}
          />
        </label>
        <label className="space-y-2 text-sm">
          <span>По дату включительно</span>
          <Input
            type="date"
            min="1900-01-01"
            max="9998-12-31"
            value={to}
            onChange={(e) => filter('to', e.target.value)}
          />
        </label>
        <label className="space-y-2 text-sm">
          <span>Статус</span>
          <select
            aria-label="Статус"
            className="min-h-11 w-full rounded-xl border border-border bg-background px-3"
            value={status ?? ''}
            onChange={(e) => filter('status', e.target.value)}
          >
            <option value="">Все записи</option>
            <option value="confirmed">Подтверждённые</option>
            <option value="cancelled">Отменённые</option>
          </select>
        </label>
      </Card>
      {rangeError ? (
        <p role="alert" className="text-sm text-red-700">
          {rangeError}
        </p>
      ) : bookings.isPending ? (
        <p role="status">Загружаем записи…</p>
      ) : bookings.isError ? (
        <EmptyState
          title="Не удалось загрузить записи"
          action={<Button onClick={() => void bookings.refetch()}>Повторить попытку</Button>}
        >
          Проверьте соединение. Выбранные фильтры сохранены.
        </EmptyState>
      ) : (
        <>
          {bookings.data.items.length === 0 ? (
            <EmptyState title="Записей пока нет">
              За выбранный период нет записей с таким статусом.
            </EmptyState>
          ) : (
            <ul className="space-y-3" aria-label="Записи клиентов">
              {bookings.data.items.map((booking) => (
                <li key={booking.id}>
                  <Card className="flex flex-wrap items-start justify-between gap-4 p-5">
                    <div className="min-w-0 space-y-2">
                      <p className="font-semibold break-words">{booking.client_name}</p>
                      <p className="break-all text-sm text-muted-foreground">
                        {booking.client_email}
                      </p>
                      <p className="text-sm">
                        {new Intl.DateTimeFormat('ru-RU', {
                          dateStyle: 'long',
                          timeZone: timezone,
                        }).format(new Date(booking.starts_at))}{' '}
                        · {timeLabel(booking.starts_at, timezone)}–
                        {timeLabel(booking.ends_at, timezone)}
                      </p>
                    </div>
                    <span
                      className={`rounded-full px-3 py-1 text-xs font-medium ${booking.status === 'confirmed' ? 'bg-emerald-50 text-emerald-800' : 'bg-muted text-muted-foreground'}`}
                    >
                      {booking.status === 'confirmed' ? 'Подтверждена' : 'Отменена'}
                    </span>
                  </Card>
                </li>
              ))}
            </ul>
          )}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <Button
              variant="outline"
              disabled={page === 0 || bookings.isFetching}
              onClick={() =>
                setParams((prev) => {
                  prev.set('page', String(page - 1))
                  return prev
                })
              }
            >
              Назад
            </Button>
            <span className="text-sm text-muted-foreground">Страница {page + 1}</span>
            <Button
              variant="outline"
              disabled={bookings.data.items.length < 20 || bookings.isFetching || page >= 500}
              onClick={() =>
                setParams((prev) => {
                  prev.set('page', String(page + 1))
                  return prev
                })
              }
            >
              Далее
            </Button>
          </div>
        </>
      )}
    </section>
  )
}
