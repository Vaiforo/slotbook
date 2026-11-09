import { invalidateAvailability } from '@/lib/availability'
import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { request, ApiError } from '@/lib/api'
import { useOwner } from '@/lib/use-owner'
import { todayIn, addDays } from '@/lib/dates'
import type { components } from '@/generated/api-types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card } from '@/components/ui/card'

type Batch = components['schemas']['ShiftBatch']
export function ShiftsPage() {
  const owner = useOwner()
  const client = useQueryClient()
  const tomorrow = addDays(todayIn(owner.specialist.timezone), 1)
  const [data, setData] = useState<Batch>({
    date_from: tomorrow,
    date_to: tomorrow,
    weekdays: [0, 1, 2, 3, 4],
    start: '09:00',
    end: '18:00',
    breaks: [],
  })
  const [preview, setPreview] = useState<number | null>(null)
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  function update(next: Batch) {
    setData(next)
    setPreview(null)
    setMessage('')
  }
  async function submit(create: boolean) {
    setBusy(true)
    setMessage('')
    try {
      const result = await request<components['schemas']['BatchResult']>(
        create ? '/me/specialist/slots/batch' : '/me/specialist/slots/preview',
        {
          method: 'POST',
          csrfToken: owner.csrf_token,
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data),
          signal: AbortSignal.timeout(30_000),
        },
      )
      setPreview(create ? null : result.count)
      setMessage(
        create
          ? `Создано интервалов: ${result.count}`
          : `Будет создано интервалов: ${result.count}`,
      )
      if (create) {
        void invalidateAvailability(client, owner.id, owner.specialist.slug)
      }
    } catch (error) {
      setPreview(null)
      setMessage(
        error instanceof ApiError && error.code === 'slot_overlap'
          ? `Есть пересечения. ${error.message}`
          : 'Проверьте даты, дни недели, перерывы и сетку по 30 минут. Все интервалы должны быть в будущем; максимум 90 дней и 1000 интервалов. Неоднозначное время недоступно.',
      )
    } finally {
      setBusy(false)
    }
  }
  return (
    <Card className="max-w-2xl space-y-5 p-6">
      <h2 className="text-2xl font-semibold">Создать смены</h2>
      <p>
        Часовой пояс расписания: {owner.specialist.timezone}. Длительность интервала — 30 минут.
      </p>
      <form
        onSubmit={(e) => {
          e.preventDefault()
          void submit(false)
        }}
      >
        <fieldset disabled={busy} className="space-y-4">
          {(
            [
              ['date_from', 'С даты', 'date'],
              ['date_to', 'По дату включительно', 'date'],
              ['start', 'Начало смены', 'time'],
              ['end', 'Конец смены', 'time'],
            ] as const
          ).map(([key, label, type]) => (
            <label key={key} className="block">
              {label}
              <Input
                required
                type={type}
                step={type === 'time' ? 1800 : undefined}
                value={data[key]}
                onChange={(e) => update({ ...data, [key]: e.target.value })}
              />
            </label>
          ))}
          <fieldset>
            <legend>Дни недели</legend>
            <div className="flex flex-wrap gap-3">
              {['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'].map((label, day) => (
                <label key={day}>
                  <input
                    type="checkbox"
                    checked={data.weekdays.includes(day)}
                    onChange={(e) =>
                      update({
                        ...data,
                        weekdays: e.target.checked
                          ? [...data.weekdays, day]
                          : data.weekdays.filter((d) => d !== day),
                      })
                    }
                  />{' '}
                  {label}
                </label>
              ))}
            </div>
          </fieldset>
          {(data.breaks || []).map((pause, i) => (
            <div key={i} className="space-y-2">
              <label>
                Начало перерыва {i + 1}
                <Input
                  required
                  type="time"
                  step={1800}
                  value={pause.start}
                  onChange={(e) =>
                    update({
                      ...data,
                      breaks: data.breaks?.map((b, j) =>
                        j === i ? { ...b, start: e.target.value } : b,
                      ),
                    })
                  }
                />
              </label>
              <label>
                Конец перерыва {i + 1}
                <Input
                  required
                  type="time"
                  step={1800}
                  value={pause.end}
                  onChange={(e) =>
                    update({
                      ...data,
                      breaks: data.breaks?.map((b, j) =>
                        j === i ? { ...b, end: e.target.value } : b,
                      ),
                    })
                  }
                />
              </label>
              <Button
                type="button"
                variant="outline"
                onClick={() => update({ ...data, breaks: data.breaks?.filter((_, j) => j !== i) })}
              >
                Удалить перерыв {i + 1}
              </Button>
            </div>
          ))}
          <Button
            type="button"
            variant="outline"
            disabled={(data.breaks?.length || 0) >= 10}
            onClick={() =>
              update({
                ...data,
                breaks: [...(data.breaks || []), { start: '13:00', end: '14:00' }],
              })
            }
          >
            Добавить перерыв
          </Button>
          <div className="flex flex-wrap gap-3">
            <Button type="submit">Предпросмотр</Button>
            <Button type="button" disabled={preview === null} onClick={() => void submit(true)}>
              Создать интервалы
            </Button>
          </div>
        </fieldset>
      </form>
      <p role="status">{message}</p>
    </Card>
  )
}
