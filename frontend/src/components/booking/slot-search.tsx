import { useEffect, useRef, useState } from 'react'
import { Search } from 'lucide-react'
import { ApiError, searchSlots } from '@/lib/api'
import type { PublicSpecialist, SearchResult } from '@/lib/api'
import { dateLabel, timeLabel } from '@/lib/dates'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'

export function SlotSearch({
  profile,
  disabled,
  onSelect,
}: {
  profile: PublicSpecialist
  disabled: boolean
  onSelect: (date: string, id: string) => void
}) {
  const [open, setOpen] = useState(false)
  const [text, setText] = useState('')
  const [pending, setPending] = useState(false)
  const [result, setResult] = useState<SearchResult | null>(null)
  const [error, setError] = useState('')
  const active = useRef<AbortController | null>(null)
  useEffect(() => () => active.current?.abort(), [])

  function changeOpen(value: boolean) {
    active.current?.abort()
    active.current = null
    setPending(false)
    setResult(null)
    setError('')
    setOpen(value)
  }
  async function submit() {
    if (pending || !text.trim()) return
    const controller = new AbortController()
    active.current = controller
    setPending(true)
    setResult(null)
    setError('')
    try {
      const response = await searchSlots(
        profile.slug,
        text.trim(),
        AbortSignal.any([controller.signal, AbortSignal.timeout(18_000)]),
      )
      if (active.current === controller) setResult(response)
    } catch (cause) {
      if (active.current === controller) {
        setError(
          cause instanceof ApiError && cause.status === 429
            ? 'Слишком много запросов. Подождите немного или выберите время в календаре.'
            : 'Не удалось подобрать время. Попробуйте ещё раз или откройте календарь.',
        )
      }
    } finally {
      if (active.current === controller) {
        active.current = null
        setPending(false)
      }
    }
  }
  return (
    <Dialog open={open} onOpenChange={changeOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" className="w-full" disabled={disabled}>
          <Search size={16} /> Подобрать по описанию
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogTitle className="pr-8 text-xl font-semibold">Когда вам удобно?</DialogTitle>
        <DialogDescription className="mt-2 text-sm text-muted-foreground">
          Опишите один день и время в часовом поясе {profile.timezone}. AI поможет найти свободные
          варианты на ближайшие 30 дней. Текст передаётся AI-провайдеру — не указывайте имя, email и
          другие личные данные.
        </DialogDescription>
        <form
          className="mt-5 space-y-3"
          onSubmit={(event) => {
            event.preventDefault()
            void submit()
          }}
        >
          <label className="block space-y-2 text-sm font-medium">
            <span>Пожелания ко времени</span>
            <Input
              value={text}
              maxLength={500}
              required
              disabled={pending}
              placeholder="Завтра с 15:00 до 18:00"
              onChange={(event) => {
                setText(event.target.value)
                setResult(null)
                setError('')
              }}
            />
          </label>
          <Button type="submit" className="w-full" disabled={pending || !text.trim()}>
            {pending ? 'Ищем свободное время…' : 'Найти время'}
          </Button>
        </form>
        {pending && (
          <p role="status" className="mt-4 text-sm">
            Проверяем пожелания и расписание…
          </p>
        )}
        {error && (
          <p role="alert" className="mt-4 text-sm text-red-700">
            {error}
          </p>
        )}
        {result && (
          <div className="mt-4 space-y-3">
            <p role="status" className="text-sm">
              {result.message}
            </p>
            {result.from && result.to && (
              <p className="text-sm font-medium">
                {dateLabel(result.from.slice(0, 10))} · {timeLabel(result.from, result.timezone)}–
                {timeLabel(result.to, result.timezone)}
                <span className="block text-xs text-muted-foreground">
                  Начало встречи · {result.timezone}
                </span>
              </p>
            )}
            <div className="grid grid-cols-2 gap-2" role="group" aria-label="Найденное время">
              {result.items.map((slot) => (
                <Button
                  key={slot.id}
                  variant="outline"
                  onClick={() => {
                    // Date comes from the server's normalized window in specialist timezone.
                    onSelect(result.from!.slice(0, 10), slot.id)
                    changeOpen(false)
                  }}
                >
                  Выбрать {timeLabel(slot.starts_at, result.timezone)}
                </Button>
              ))}
            </div>
            {result.items.length > 0 && (
              <p className="text-xs text-muted-foreground">
                Это ещё не запись. После выбора заполните форму и нажмите «Подтвердить запись».
                Доступность проверится повторно.
              </p>
            )}
          </div>
        )}
        <Button variant="ghost" className="mt-4 w-full" onClick={() => changeOpen(false)}>
          Выбрать в календаре
        </Button>
      </DialogContent>
    </Dialog>
  )
}
