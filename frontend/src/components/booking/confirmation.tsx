import { useEffect, useRef, useState } from 'react'
import { Check, Copy } from 'lucide-react'
import type { BookingCreated } from '@/lib/api'
import { manageLink } from '@/lib/manage-token'
import { timeLabel } from '@/lib/dates'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'

export function Confirmation({
  booking,
  timezone,
  specialist,
}: {
  booking: BookingCreated
  timezone: string
  specialist: string
}) {
  const heading = useRef<HTMLHeadingElement>(null)
  useEffect(() => {
    heading.current?.focus()
  }, [])
  const [copyStatus, setCopyStatus] = useState('')
  const link = manageLink(booking.id, booking.manage_token)
  return (
    <Card className="mx-auto max-w-xl space-y-6 p-6 sm:p-8">
      <div className="selection-icon">
        <Check aria-hidden="true" />
      </div>
      <div className="space-y-3">
        <h1 ref={heading} tabIndex={-1}>
          Вы записаны
        </h1>
        <p className="font-medium">{specialist}</p>
        <p>
          {new Intl.DateTimeFormat('ru-RU', { dateStyle: 'long', timeZone: timezone }).format(
            new Date(booking.starts_at),
          )}{' '}
          · {timeLabel(booking.starts_at, timezone)}–{timeLabel(booking.ends_at, timezone)}
        </p>
        <p className="text-sm text-muted-foreground">Часовой пояс: {timezone}</p>
      </div>
      <div className="space-y-3 rounded-xl bg-muted p-4">
        <label htmlFor="manage-link" className="block font-medium">
          Сохраните ссылку на запись
        </label>
        <p className="text-sm text-muted-foreground">
          По ней можно посмотреть или отменить встречу. Любой, у кого есть эта ссылка, получит
          доступ к записи. Письмо не отправляется.
        </p>
        <Input id="manage-link" readOnly value={link} onFocus={(event) => event.target.select()} />
        <Button
          variant="outline"
          className="w-full"
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(link)
              setCopyStatus('Ссылка скопирована.')
            } catch {
              setCopyStatus(
                'Не удалось скопировать автоматически. Выделите ссылку в поле и скопируйте вручную.',
              )
            }
          }}
        >
          <Copy />
          Копировать ссылку
        </Button>
        <p role="status" className="text-sm">
          {copyStatus}
        </p>
      </div>
      <Button asChild className="w-full">
        <a href={link} referrerPolicy="no-referrer">
          Управлять записью
        </a>
      </Button>
      <p className="text-sm text-muted-foreground">
        Сохраните ссылку перед переходом: после обновления страницы доступ можно восстановить только
        по ней.
      </p>
    </Card>
  )
}
