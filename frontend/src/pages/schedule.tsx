import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { ChevronLeft, ChevronRight, Plus } from 'lucide-react'
import { changeSlot, ownerKey, ownerSlots, publishSlot, type ScheduleSlot } from '@/lib/owner-api'
import { useOwner } from '@/lib/use-owner'
import { addDays, dateLabel, dayFilters, timeLabel, todayIn } from '@/lib/dates'
import { slotInput, validDate, weekDates } from '@/lib/owner-dates'
import { ownerError } from '@/components/owner/feedback'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { EmptyState } from '@/components/ui/empty-state'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'

export function SchedulePage() {
  const owner = useOwner()
  const [now, setNow] = useState(Date.now)
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 30_000)
    return () => window.clearInterval(timer)
  }, [])
  const client = useQueryClient()
  const [params, setParams] = useSearchParams()
  const date = validDate(params.get('date'), todayIn(owner.specialist.timezone))
  const filters = dayFilters(date, owner.specialist.timezone)
  const closeTrigger = useRef<HTMLButtonElement>(null)
  const heading = useRef<HTMLHeadingElement>(null)
  const [closing, setClosing] = useState<ScheduleSlot | null>(null)
  const [notice, setNotice] = useState('')
  const [publishing, setPublishing] = useState(false)
  const slots = useQuery({
    queryKey: [...ownerKey(owner.id), 'slots', filters],
    enabled: !owner.checkingSession,
    queryFn: ({ signal }) =>
      ownerSlots(filters, AbortSignal.any([signal, AbortSignal.timeout(10_000)])),
    gcTime: 0,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })
  function refresh() {
    void client.invalidateQueries({ queryKey: ownerKey(owner.id) })
    void client.invalidateQueries({ queryKey: ['specialists', owner.specialist.slug, 'slots'] })
  }
  const mutation = useMutation({
    mutationKey: ['owner', owner.id, 'change-slot'],
    retry: false,
    gcTime: 0,
    mutationFn: ({ id, state }: { id: string; state: 'open' | 'closed' }) =>
      changeSlot(id, state, owner.csrf_token),
    onSuccess: (slot) => {
      setClosing(null)
      setNotice(slot.state === 'open' ? 'Слот открыт для записи.' : 'Слот закрыт.')
      refresh()
    },
    onError: () => {
      refresh()
    },
  })
  function selectDate(next: string) {
    if (publishing || mutation.isPending) return
    setParams({ date: next })
    setNotice('')
    mutation.reset()
  }
  return (
    <section className="space-y-5" aria-labelledby="schedule-owner-title">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2
            ref={heading}
            tabIndex={-1}
            id="schedule-owner-title"
            className="text-2xl font-semibold"
          >
            Ваше расписание
          </h2>
          <p className="mt-2 text-sm text-muted-foreground">
            30 минут на встречу · {owner.specialist.timezone}
          </p>
        </div>
        <Button variant="outline" disabled={slots.isFetching} onClick={() => void slots.refetch()}>
          Обновить расписание
        </Button>
      </div>
      <Card className="space-y-5 p-5">
        <fieldset disabled={publishing || mutation.isPending} className="min-w-0 space-y-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <label className="flex flex-wrap items-center gap-3 text-sm">
              Дата
              <Input
                className="w-auto"
                type="date"
                min="1900-01-08"
                max="9998-12-24"
                value={date}
                onChange={(e) => selectDate(validDate(e.target.value, date))}
              />
            </label>
            <div className="flex gap-2">
              <Button
                variant="outline"
                onClick={() => selectDate(todayIn(owner.specialist.timezone))}
              >
                Сегодня
              </Button>
              <Button
                size="icon"
                variant="outline"
                aria-label="Предыдущая неделя"
                disabled={date <= '1900-01-08'}
                onClick={() => selectDate(addDays(date, -7))}
              >
                <ChevronLeft />
              </Button>
              <Button
                size="icon"
                variant="outline"
                aria-label="Следующая неделя"
                disabled={date >= '9998-12-24'}
                onClick={() => selectDate(addDays(date, 7))}
              >
                <ChevronRight />
              </Button>
            </div>
          </div>
          <div className="grid grid-cols-7 gap-1 sm:gap-3" role="group" aria-label="Дни недели">
            {weekDates(date).map((day) => (
              <button
                key={day}
                type="button"
                aria-pressed={day === date}
                aria-label={dateLabel(day, { weekday: 'long', day: 'numeric', month: 'long' })}
                onClick={() => selectDate(day)}
                className={`min-w-0 rounded-xl px-1 py-3 text-center text-xs sm:text-sm ${day === date ? 'bg-primary text-white' : 'bg-muted hover:bg-border'}`}
              >
                <span className="block capitalize">{dateLabel(day, { weekday: 'short' })}</span>
                <span className="mt-2 block text-lg font-semibold">{Number(day.slice(-2))}</span>
              </button>
            ))}
          </div>
        </fieldset>
        <h3 className="font-semibold">
          {dateLabel(date, { day: 'numeric', month: 'long', year: 'numeric' })}
        </h3>
        {slots.isPending ? (
          <p role="status">Загружаем слоты…</p>
        ) : slots.isError ? (
          <EmptyState
            title="Не удалось загрузить расписание"
            action={<Button onClick={() => void slots.refetch()}>Повторить попытку</Button>}
          >
            Проверьте соединение.
          </EmptyState>
        ) : slots.data.items.length === 0 ? (
          <EmptyState title="На этот день слотов нет">Добавьте время для встречи ниже.</EmptyState>
        ) : (
          <ul className="space-y-3" aria-label="Слоты расписания">
            {slots.data.items.map((slot) => {
              const past = Date.parse(slot.starts_at) <= now
              return (
                <li
                  key={slot.id}
                  className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border p-4"
                >
                  <div className="space-y-1">
                    <p className="font-semibold">
                      {timeLabel(slot.starts_at, owner.specialist.timezone)}–
                      {timeLabel(slot.ends_at, owner.specialist.timezone)}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      {slot.has_booking
                        ? 'Есть запись'
                        : slot.state === 'closed'
                          ? 'Закрыт'
                          : 'Свободен'}
                      {past && ' · Время прошло'}
                    </p>
                  </div>
                  <Button
                    variant="outline"
                    disabled={past || slot.has_booking || mutation.isPending || slots.isFetching}
                    onClick={(event) => {
                      closeTrigger.current = event.currentTarget
                      setNotice('')
                      mutation.reset()
                      if (slot.state === 'open') setClosing(slot)
                      else mutation.mutate({ id: slot.id, state: 'open' })
                    }}
                  >
                    {slot.state === 'open' ? 'Закрыть слот' : 'Открыть слот'}
                  </Button>
                </li>
              )
            })}
          </ul>
        )}
        {notice && (
          <p role="status" className="text-sm text-emerald-800">
            {notice}
          </p>
        )}
        {mutation.isError && !closing && (
          <p role="alert" className="text-sm text-red-700">
            {ownerError(mutation.error)}
          </p>
        )}
      </Card>
      <PublishForm
        key={date}
        date={date}
        onPendingChange={setPublishing}
        onStart={() => setNotice('')}
        onPublished={() => {
          setNotice('Слот опубликован. Клиенты могут записаться.')
          refresh()
        }}
      />
      <Dialog
        open={!!closing && !owner.checkingSession}
        onOpenChange={(open) => {
          if (!open && !mutation.isPending) setClosing(null)
        }}
      >
        <DialogContent
          onCloseAutoFocus={(event) => {
            event.preventDefault()
            const target = closeTrigger.current
            if (target?.isConnected && !target.disabled) target.focus({ preventScroll: true })
            else heading.current?.focus({ preventScroll: true })
          }}
        >
          <DialogTitle className="pr-7 text-xl font-semibold">Закрыть слот?</DialogTitle>
          <DialogDescription className="mt-3 text-sm text-muted-foreground">
            Это время исчезнет со страницы записи. Позже слот можно открыть снова.
          </DialogDescription>
          <div className="mt-6 space-y-3">
            <Button
              className="w-full"
              disabled={mutation.isPending}
              onClick={() => {
                if (closing && !mutation.isPending)
                  mutation.mutate({ id: closing.id, state: 'closed' })
              }}
            >
              {mutation.isPending ? 'Закрываем…' : 'Да, закрыть слот'}
            </Button>
            <Button
              variant="outline"
              className="w-full"
              disabled={mutation.isPending}
              onClick={() => setClosing(null)}
            >
              Оставить открытым
            </Button>
            {mutation.isError && (
              <p role="alert" className="text-sm text-red-700">
                {ownerError(mutation.error)}
              </p>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </section>
  )
}
const schema = z.object({ time: z.string().regex(/^\d{2}:\d{2}$/, 'Укажите время встречи.') })
function PublishForm({
  date,
  onPublished,
  onStart,
  onPendingChange,
}: {
  date: string
  onPublished: () => void
  onStart: () => void
  onPendingChange: (pending: boolean) => void
}) {
  const sending = useRef(false)
  const owner = useOwner()
  const [error, setError] = useState('')
  const form = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: { time: '10:00' },
  })
  const mutation = useMutation({
    mutationKey: ['owner', owner.id, 'publish-slot'],
    retry: false,
    gcTime: 0,
    mutationFn: (data: ReturnType<typeof slotInput>) => publishSlot(data, owner.csrf_token),
    onMutate: () => onPendingChange(true),
    onSettled: () => onPendingChange(false),
    onSuccess: () => onPublished(),
  })
  return (
    <Card className="space-y-4 p-5">
      <h3 className="text-lg font-semibold">Добавить время</h3>
      <p className="text-sm text-muted-foreground">
        {dateLabel(date)} · {owner.specialist.timezone} · 30 минут
      </p>
      <form
        className="space-y-4"
        onSubmit={(event) => {
          void form.handleSubmit(async ({ time }) => {
            if (sending.current) return
            onStart()
            setError('')
            let data: ReturnType<typeof slotInput>
            try {
              data = slotInput(date, time, owner.specialist.timezone)
            } catch {
              setError(
                'Это время неоднозначно или не существует из-за перевода часов. Выберите другое.',
              )
              return
            }
            sending.current = true
            try {
              await mutation.mutateAsync(data)
            } catch {
              /* rendered below */
            } finally {
              sending.current = false
            }
          })(event)
        }}
      >
        <div className="flex flex-wrap items-end gap-4">
          <label className="block space-y-2 text-sm">
            <span>Начало встречи</span>
            <Input
              type="time"
              {...form.register('time')}
              disabled={mutation.isPending}
              aria-describedby="publish-error"
              aria-invalid={!!form.formState.errors.time}
            />
          </label>
          <Button type="submit" disabled={mutation.isPending}>
            <Plus />
            {mutation.isPending ? 'Публикуем…' : 'Опубликовать слот'}
          </Button>
        </div>
        <p role="alert" id="publish-error" className="text-sm text-red-700">
          {error ||
            form.formState.errors.time?.message ||
            (mutation.isError ? ownerError(mutation.error) : '')}
        </p>
      </form>
    </Card>
  )
}
