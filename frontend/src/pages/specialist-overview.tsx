import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useOwner } from '@/lib/use-owner'
import { ownerBookings } from '@/lib/owner-api'
import { dayFilters, todayIn, timeLabel } from '@/lib/dates'
import { request } from '@/lib/api'
import type { components } from '@/generated/api-types'
import { Card } from '@/components/ui/card'

export function SpecialistOverview() {
  const user = useOwner()
  const profile = useQuery({
    queryKey: ['owner', user.id, 'professional'],
    queryFn: ({ signal }) =>
      request<components['schemas']['ProfessionalDetails']>('/me/specialist', { signal }),
  })
  const today = useQuery({
    queryKey: ['owner', user.id, 'today'],
    queryFn: ({ signal }) =>
      ownerBookings(
        {
          ...dayFilters(todayIn(user.specialist.timezone), user.specialist.timezone),
          status: 'confirmed',
        },
        signal,
      ),
    gcTime: 0,
  })
  const upcoming = useQuery({
    queryKey: ['owner', user.id, 'upcoming-clients'],
    queryFn: ({ signal }) =>
      ownerBookings(
        {
          from: new Date().toISOString(),
          to: new Date(Date.now() + 30 * 86400000).toISOString(),
          status: 'confirmed',
          limit: 5,
        },
        signal,
      ),
    gcTime: 0,
  })
  return (
    <section className="space-y-5">
      <h2 className="text-2xl font-semibold">Обзор</h2>
      <Card className="space-y-3 p-5">
        <h3>Публичный профиль</h3>
        <p>
          {profile.data
            ? profile.data.publication_status === 'published'
              ? 'Опубликован'
              : 'Черновик: заполните профиль, чтобы клиенты могли найти вас.'
            : profile.isError
              ? 'Не удалось загрузить статус профиля'
              : 'Загружаем…'}
        </p>
        <Link to="/dashboard/professional">Настроить профиль</Link>
      </Card>
      <Card className="space-y-3 p-5">
        <h3>Записи на сегодня</h3>
        {today.isError ? (
          <p role="alert">Не удалось загрузить записи</p>
        ) : (
          <p>{today.data?.items.length ?? '…'}</p>
        )}
        {today.data?.items.map((b) => (
          <p key={b.id}>
            {timeLabel(b.starts_at, user.specialist.timezone)} · {b.client_name} · {b.client_email}
          </p>
        ))}
        <Link to="/dashboard/bookings">Все записи клиентов</Link>
      </Card>
      <Card className="space-y-3 p-5">
        <h3>Ближайшие клиенты</h3>
        {upcoming.isPending && <p role="status">Загружаем…</p>}
        {upcoming.isError && <p role="alert">Не удалось загрузить ближайшие записи</p>}
        {upcoming.data?.items.length === 0 && <p>На ближайшие 30 дней записей нет.</p>}
        {upcoming.data?.items.map((booking) => (
          <p key={booking.id}>
            {new Intl.DateTimeFormat('ru', {
              dateStyle: 'medium',
              timeStyle: 'short',
              timeZone: user.specialist.timezone,
            }).format(new Date(booking.starts_at))}{' '}
            · {booking.client_name}
          </p>
        ))}
      </Card>
      <div className="flex gap-4">
        <Link to="/dashboard/schedule">Расписание</Link>
        <Link to="/dashboard/shifts">Создать смены</Link>
      </div>
    </section>
  )
}
