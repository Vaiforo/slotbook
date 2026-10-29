import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import {
  ArrowRight,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Globe2,
  Check,
  RefreshCw,
  Info,
} from 'lucide-react'
import { ApiError, getAvailableSlots, getSpecialist } from '@/lib/api'
import { BookingForm } from '@/components/booking/booking-form'
import { Confirmation } from '@/components/booking/confirmation'
import type { BookingCreated } from '@/lib/api'
import type { PublicSpecialist } from '@/lib/api'
import { queryKeys } from '@/lib/query-keys'
import {
  addDays,
  calendarDays,
  dateLabel,
  dayFilters,
  shiftMonth,
  timeLabel,
  todayIn,
  zoneLabel,
} from '@/lib/dates'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Skeleton } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/ui/empty-state'

function timedSignal(signal: AbortSignal) {
  return AbortSignal.any([signal, AbortSignal.timeout(10_000)])
}

export function SpecialistPage() {
  const { slug = '' } = useParams()
  const profile = useQuery({
    queryKey: queryKeys.specialist(slug),
    queryFn: ({ signal }) => getSpecialist(slug, timedSignal(signal)),
  })
  if (profile.isPending)
    return (
      <div role="status" aria-label="Загружаем профиль" className="space-y-6">
        <Skeleton className="h-12 w-3/4" />
        <div className="booking-layout">
          <Skeleton className="h-80" />
          <Skeleton className="h-[540px]" />
        </div>
        <span className="sr-only">Загружаем профиль…</span>
      </div>
    )
  if (profile.isError && !profile.data)
    return (
      <EmptyState
        title={
          profile.error instanceof ApiError && profile.error.status === 404
            ? 'Специалист не найден'
            : 'Не удалось загрузить профиль'
        }
        action={
          <Button onClick={() => void profile.refetch()} disabled={profile.isFetching}>
            Повторить попытку
          </Button>
        }
      >
        {profile.error instanceof ApiError && profile.error.status === 404
          ? 'Проверьте ссылку на страницу специалиста.'
          : 'Проверьте соединение и попробуйте ещё раз.'}
      </EmptyState>
    )
  return <Schedule key={slug} profile={profile.data} />
}

function Schedule({ profile }: { profile: PublicSpecialist }) {
  const today = todayIn(profile.timezone)
  const [date, setDate] = useState(today)
  const [month, setMonth] = useState(today.slice(0, 7))
  const [bookingPending, setBookingPending] = useState(false)
  const [booking, setBooking] = useState<BookingCreated | null>(null)
  const [unavailable, setUnavailable] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const filters = dayFilters(date, profile.timezone)
  const slots = useQuery({
    queryKey: queryKeys.slots(profile.slug, filters),
    queryFn: ({ signal }) => getAvailableSlots(profile.slug, filters, timedSignal(signal)),
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })
  const selected =
    !slots.isError && !slots.isFetching
      ? slots.data?.items.find((slot) => slot.id === selectedId)
      : undefined
  function selectDate(next: string) {
    setDate(next)
    setMonth(next.slice(0, 7))
    setSelectedId(null)
  }
  const initials = profile.display_name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0])
    .join('')
  if (booking)
    return (
      <Confirmation
        booking={booking}
        timezone={profile.timezone}
        specialist={profile.display_name}
      />
    )
  return (
    <>
      <div className="page-heading">
        <p className="eyebrow">Личная встреча начинается здесь</p>
        <h1>
          Найдите время
          <br className="mobile-break" /> для важного.
        </h1>
        <p>Выберите удобный день и свободное время в расписании специалиста.</p>
      </div>
      <div className="booking-layout">
        <aside className="space-y-5">
          <Card className="profile-card" aria-labelledby="specialist-name">
            <div className="avatar" aria-hidden="true">
              {initials}
            </div>
            <p className="small-label">Ваш специалист</p>
            <h2 id="specialist-name">{profile.display_name}</h2>
            <p className="profile-subtitle">Индивидуальная консультация</p>
            <div className="profile-facts">
              <div>
                <Clock3 />
                <span>
                  30 минут<span className="fact-caption">Продолжительность встречи</span>
                </span>
              </div>
              <div>
                <Globe2 />
                <span className="break-all">
                  {profile.timezone}
                  <span className="fact-caption">Часовой пояс специалиста</span>
                </span>
              </div>
            </div>
            <p className="profile-note">
              В расписании показаны только свободные часы. Выберите время, которое подходит вам.
            </p>
          </Card>
          <div className="note">
            <Info size={17} />
            <p>Все даты и время указаны по часовому поясу специалиста.</p>
          </div>
        </aside>
        <Card className="schedule-card" aria-labelledby="schedule-title">
          <fieldset disabled={bookingPending} className="contents">
            <div className="schedule-heading">
              <div>
                <p className="small-label">Расписание</p>
                <h2 id="schedule-title">Когда вам удобно?</h2>
              </div>
              <span className="duration">
                <Clock3 size={14} />
                30 мин
              </span>
            </div>
            <div className="schedule-body">
              <div className="calendar-panel">
                <div className="calendar-heading">
                  <h3 className="capitalize">
                    {dateLabel(`${month}-01`, { month: 'long', year: 'numeric' })}
                  </h3>
                  <div className="flex gap-1">
                    <Button
                      size="icon"
                      variant="ghost"
                      aria-label="Предыдущий месяц"
                      disabled={month <= today.slice(0, 7)}
                      onClick={() => setMonth(shiftMonth(month, -1))}
                    >
                      <ChevronLeft />
                    </Button>
                    <Button
                      size="icon"
                      variant="ghost"
                      aria-label="Следующий месяц"
                      disabled={month >= '9999-12'}
                      onClick={() => setMonth(shiftMonth(month, 1))}
                    >
                      <ChevronRight />
                    </Button>
                  </div>
                </div>
                <div className="weekdays" aria-hidden="true">
                  {['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'].map((day) => (
                    <span key={day}>{day}</span>
                  ))}
                </div>
                <div className="calendar-grid" role="group" aria-label="Дни месяца">
                  {calendarDays(month).map((day, index) =>
                    day ? (
                      <button
                        key={day}
                        type="button"
                        className="day-button"
                        disabled={day < today}
                        aria-pressed={date === day}
                        aria-current={today === day ? 'date' : undefined}
                        aria-label={dateLabel(day, {
                          weekday: 'long',
                          day: 'numeric',
                          month: 'long',
                          year: 'numeric',
                        })}
                        onClick={() => selectDate(day)}
                      >
                        {Number(day.slice(-2))}
                        {day === today && <span className="today-dot" />}
                      </button>
                    ) : (
                      <span key={`blank-${index}`} />
                    ),
                  )}
                </div>
                <div className="calendar-tools">
                  <Button variant="outline" onClick={() => selectDate(today)}>
                    Сегодня
                  </Button>
                  <Button variant="outline" onClick={() => selectDate(addDays(today, 1))}>
                    Завтра
                  </Button>
                  <DateJump date={date} today={today} onSelect={selectDate} />
                </div>
              </div>
              <div className="times-panel">
                <div className="times-heading">
                  <div>
                    <h3>{dateLabel(date)}</h3>
                    <p className="capitalize">{dateLabel(date, { weekday: 'long' })}</p>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label="Обновить свободное время"
                    disabled={slots.isFetching}
                    onClick={() => void slots.refetch()}
                  >
                    <RefreshCw
                      className={slots.isFetching ? 'animate-spin motion-reduce:animate-none' : ''}
                    />
                  </Button>
                </div>
                <p className="time-caption">Доступное время</p>
                {slots.isPending ? (
                  <div role="status" aria-label="Загружаем свободное время">
                    <div className="time-grid">
                      {Array.from({ length: 4 }, (_, i) => (
                        <Skeleton key={i} className="h-12" />
                      ))}
                    </div>
                    <span className="sr-only">Загружаем свободное время…</span>
                  </div>
                ) : slots.isError ? (
                  <EmptyState
                    title="Не удалось загрузить время"
                    action={
                      <Button variant="outline" onClick={() => void slots.refetch()}>
                        Повторить попытку
                      </Button>
                    }
                  >
                    Проверьте соединение. Ваш выбор даты сохранён.
                  </EmptyState>
                ) : slots.data.items.length === 0 ? (
                  <EmptyState
                    title="Свободного времени нет"
                    action={
                      <Button
                        variant="outline"
                        disabled={date >= '9999-12-31'}
                        onClick={() => selectDate(addDays(date, 1))}
                      >
                        Следующий день
                        <ArrowRight />
                      </Button>
                    }
                  >
                    На этот день нет доступных слотов. Попробуйте выбрать другую дату.
                  </EmptyState>
                ) : (
                  <>
                    <div className="time-grid" role="group" aria-label="Доступное время">
                      {slots.data.items.map((slot) => (
                        <button
                          type="button"
                          key={slot.id}
                          className="time-button"
                          aria-pressed={selected?.id === slot.id}
                          disabled={slots.isFetching}
                          onClick={() => {
                            setSelectedId(slot.id)
                            setUnavailable(false)
                          }}
                        >
                          {timeLabel(slot.starts_at, profile.timezone)}
                          {selected?.id === slot.id && <Check size={14} />}
                        </button>
                      ))}
                    </div>
                    <p className="availability-note" role="status">
                      {slots.isFetching ? 'Обновляем расписание…' : 'Выберите время из доступных'}
                    </p>
                  </>
                )}
              </div>
            </div>
            <div className="timezone-line">
              <Globe2 size={14} />
              <span>{zoneLabel(date, profile.timezone)}</span>
            </div>
            <div className="selection-panel" aria-live="polite" aria-atomic="true">
              <div className="selection-icon">
                <CalendarDays size={21} />
              </div>
              <div className="selection-copy">
                <p className="small-label">Ваш выбор</p>
                <p className="selection-value">
                  {selected
                    ? `${dateLabel(date)} · ${timeLabel(selected.starts_at, profile.timezone)}–${timeLabel(selected.ends_at, profile.timezone)}`
                    : 'Выберите дату и время'}
                </p>
                <p className="selection-help">
                  {selected
                    ? 'Время не забронировано. Заполните форму для подтверждения.'
                    : 'Выбранное время появится здесь.'}
                </p>
              </div>
            </div>
            {unavailable && (
              <p role="alert" className="px-6 py-4 text-sm text-red-700">
                Это время уже недоступно. Расписание обновлено — выберите другое время.
              </p>
            )}
            {selected && (
              <div className="border-t border-border p-6">
                <h3 className="mb-4 text-lg font-semibold">Данные для записи</h3>
                <BookingForm
                  key={selected.id}
                  slotId={selected.id}
                  onPendingChange={setBookingPending}
                  onBooked={setBooking}
                  onUnavailable={() => {
                    setUnavailable(true)
                    setSelectedId(null)
                  }}
                />
              </div>
            )}
          </fieldset>
        </Card>
      </div>
    </>
  )
}

function DateJump({
  date,
  today,
  onSelect,
}: {
  date: string
  today: string
  onSelect: (date: string) => void
}) {
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState(date)
  return (
    <Dialog
      open={open}
      onOpenChange={(value) => {
        setDraft(date)
        setOpen(value)
      }}
    >
      <DialogTrigger asChild>
        <Button variant="ghost" size="icon" aria-label="Перейти к дате">
          <CalendarDays />
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogTitle className="pr-8 text-xl font-semibold">Перейти к дате</DialogTitle>
        <DialogDescription className="mt-2 text-sm text-muted-foreground">
          Откройте расписание на нужный день.
        </DialogDescription>
        <form
          className="mt-6 space-y-4"
          onSubmit={(event) => {
            event.preventDefault()
            if (draft && draft >= today) {
              onSelect(draft)
              setOpen(false)
            }
          }}
        >
          <label className="block space-y-2 text-sm font-medium">
            <span>Дата встречи</span>
            <Input
              type="date"
              required
              min={today}
              max="9999-12-31"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
            />
          </label>
          <Button className="w-full" type="submit">
            Показать дату
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  )
}
