import { useEffect, useRef, useState, useSyncExternalStore } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { ApiError, cancelBooking, getBooking } from '@/lib/api'
import { getManageCredential, subscribeManageToken } from '@/lib/manage-token'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { EmptyState } from '@/components/ui/empty-state'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'

export function ManagePage() {
  const { id = '' } = useParams()
  const credential = useSyncExternalStore(subscribeManageToken, getManageCredential)
  if (!credential || credential.id !== id)
    return (
      <EmptyState title="Откройте сохранённую ссылку">
        Для просмотра записи нужна полная секретная ссылка, полученная после бронирования. После
        обновления страницы откройте её снова.
      </EmptyState>
    )
  return (
    <ManageBooking
      key={credential.revision}
      id={id}
      token={credential.token}
      revision={credential.revision}
    />
  )
}

function ManageBooking({ id, token, revision }: { id: string; token: string; revision: number }) {
  const client = useQueryClient()
  const [open, setOpen] = useState(false)
  const sending = useRef(false)
  const heading = useRef<HTMLHeadingElement>(null)
  const key = ['booking', id, revision]
  const booking = useQuery({
    queryKey: key,
    queryFn: ({ signal }) =>
      getBooking(id, token, AbortSignal.any([signal, AbortSignal.timeout(10_000)])),
    gcTime: 0,
  })
  useEffect(() => {
    heading.current?.focus()
  }, [booking.data?.status])
  const cancellation = useMutation({
    retry: false,
    gcTime: 0,
    mutationFn: () => cancelBooking(id, token, AbortSignal.timeout(15_000)),
    onSuccess: (updated) => {
      client.setQueryData(key, updated)
      void client.invalidateQueries({
        queryKey: ['specialists'],
        predicate: (query) => query.queryKey[2] === 'slots',
      })
      setOpen(false)
    },
    onError: () => {
      void client.invalidateQueries({ queryKey: key })
    },
  })
  if (booking.isPending) return <p role="status">Загружаем запись…</p>
  if (booking.isError)
    return (
      <EmptyState
        title={
          booking.error instanceof ApiError && booking.error.status === 404
            ? 'Запись недоступна'
            : 'Не удалось загрузить запись'
        }
        action={
          <Button onClick={() => void booking.refetch()} disabled={booking.isFetching}>
            Повторить попытку
          </Button>
        }
      >
        Проверьте соединение и полную сохранённую ссылку.
      </EmptyState>
    )
  const details = booking.data
  // The booking API returns instants. Label the browser's timezone explicitly.
  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone
  const format = new Intl.DateTimeFormat('ru-RU', {
    dateStyle: 'long',
    timeStyle: 'short',
    timeZone: timezone,
  })
  return (
    <Card className="mx-auto max-w-xl space-y-6 p-6 sm:p-8">
      <div className="space-y-3">
        <p className="eyebrow">Ваша встреча</p>
        <h1 ref={heading} tabIndex={-1}>
          {details.status === 'cancelled' ? 'Запись отменена' : 'Запись подтверждена'}
        </h1>
        <p>
          {format.format(new Date(details.starts_at))} —{' '}
          {new Intl.DateTimeFormat('ru-RU', { timeStyle: 'short', timeZone: timezone }).format(
            new Date(details.ends_at),
          )}
        </p>
        <p className="text-sm text-muted-foreground">
          Ваш часовой пояс: {timezone}. В расписании время показано по часовому поясу специалиста.
        </p>
      </div>
      <dl className="space-y-3 rounded-xl bg-muted p-4 break-words">
        <div>
          <dt className="small-label">Имя</dt>
          <dd>{details.client_name}</dd>
        </div>
        <div>
          <dt className="small-label">Email</dt>
          <dd>{details.client_email}</dd>
        </div>
      </dl>
      {details.status === 'cancelled' ? (
        <p role="status">Встреча отменена. Можно выбрать новое время в расписании специалиста.</p>
      ) : (
        <>
          <p className="text-sm text-muted-foreground">Отменить запись можно до начала встречи.</p>
          <Dialog
            open={open}
            onOpenChange={(next) => {
              if (!cancellation.isPending) setOpen(next)
            }}
          >
            <DialogTrigger asChild>
              <Button variant="outline" className="w-full" onClick={() => cancellation.reset()}>
                Отменить запись
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogTitle className="pr-8 text-xl font-semibold">Отменить встречу?</DialogTitle>
              <DialogDescription className="mt-3 text-sm text-muted-foreground">
                Вы освободите это время для других клиентов. Чтобы записаться снова, нужно будет
                выбрать свободный слот.
              </DialogDescription>
              <div className="mt-6 space-y-3">
                <Button
                  className="w-full"
                  disabled={cancellation.isPending}
                  onClick={async () => {
                    if (sending.current) return
                    sending.current = true
                    try {
                      await cancellation.mutateAsync()
                    } catch {
                      /* Displayed in the dialog. */
                    } finally {
                      sending.current = false
                    }
                  }}
                >
                  {cancellation.isPending ? 'Отменяем…' : 'Да, отменить встречу'}
                </Button>
                <Button
                  variant="outline"
                  className="w-full"
                  disabled={cancellation.isPending}
                  onClick={() => setOpen(false)}
                >
                  Сохранить запись
                </Button>
                {cancellation.isError && (
                  <p role="alert" className="text-sm text-red-700">
                    {cancellation.error instanceof ApiError && cancellation.error.status === 409
                      ? 'Встреча уже началась. Отменить её нельзя.'
                      : 'Не удалось подтвердить отмену. Проверьте соединение и обновите запись перед новой попыткой.'}
                  </p>
                )}
              </div>
            </DialogContent>
          </Dialog>
        </>
      )}
      <Button
        variant="ghost"
        className="w-full"
        disabled={booking.isFetching || cancellation.isPending}
        onClick={() => void booking.refetch()}
      >
        Обновить запись
      </Button>
      <p className="text-sm text-muted-foreground">
        Доступ действует до обновления страницы. Для возвращения используйте сохранённую секретную
        ссылку.
      </p>
    </Card>
  )
}
