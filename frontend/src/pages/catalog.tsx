import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { request } from '@/lib/api'
import type { components } from '@/generated/api-types'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

export function CatalogPage() {
  const [params, setParams] = useSearchParams()
  const offset = Math.min(10000, Math.max(0, Number(params.get('offset')) || 0))
  const query = new URLSearchParams({
    q: params.get('q') || '',
    category: params.get('category') || '',
    city: params.get('city') || '',
    available: String(params.get('available') === 'true'),
    limit: '12',
    offset: String(offset),
  })
  const categories = useQuery({
    queryKey: ['categories'],
    queryFn: ({ signal }) =>
      request<components['schemas']['Category'][]>('/specialist-categories', { signal }),
  })
  const catalog = useQuery({
    queryKey: ['catalog', query.toString()],
    queryFn: ({ signal }) =>
      request<components['schemas']['CatalogPage']>(`/specialists?${query}`, { signal }),
  })
  function filter(name: string, value: string) {
    setParams((prev) => {
      prev.set(name, value)
      prev.delete('offset')
      return prev
    })
  }
  return (
    <section className="space-y-6">
      <div>
        <p className="eyebrow">SlotBook</p>
        <h1>Найдите своего специалиста</h1>
        <p>Выберите направление и удобное время для записи.</p>
      </div>
      <Card className="grid gap-4 p-5 sm:grid-cols-2">
        <label>
          Поиск
          <Input
            type="search"
            maxLength={100}
            value={params.get('q') || ''}
            onChange={(e) => filter('q', e.target.value)}
            placeholder="Имя или специализация"
          />
        </label>
        <label>
          Категория
          <select
            className="block w-full rounded border p-3"
            value={params.get('category') || ''}
            onChange={(e) => filter('category', e.target.value)}
          >
            <option value="">Все направления</option>
            {categories.data?.map((c) => (
              <option key={c.code} value={c.code}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Город
          <Input
            maxLength={100}
            value={params.get('city') || ''}
            onChange={(e) => filter('city', e.target.value)}
          />
        </label>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={params.get('available') === 'true'}
            onChange={(e) => filter('available', String(e.target.checked))}
          />{' '}
          Есть свободное время
        </label>
      </Card>
      {catalog.isPending && <p role="status">Загружаем специалистов…</p>}
      {catalog.isError && (
        <div role="alert">
          Не удалось загрузить каталог.{' '}
          <Button onClick={() => void catalog.refetch()}>Повторить</Button>
        </div>
      )}
      {catalog.data && (
        <>
          <p role="status">Найдено: {catalog.data.total}</p>
          {!catalog.data.items.length && (
            <Card className="space-y-3 p-6">
              <h2>Специалистов пока нет</h2>
              <p>Попробуйте изменить фильтры или загляните позже.</p>
              <Button variant="outline" onClick={() => setParams({})}>
                Сбросить фильтры
              </Button>
            </Card>
          )}
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {catalog.data.items.map((s) => (
              <Card key={s.id} className="min-w-0 space-y-3 break-words p-6">
                <p className="eyebrow">
                  {categories.data?.find((c) => c.code === s.category_code)?.name}
                </p>
                <h2 className="text-xl font-semibold">{s.display_name}</h2>
                <p>{s.specialization}</p>
                <p>
                  {s.city} ·{' '}
                  {s.work_formats
                    .split(',')
                    .map((f) => ({ office: 'Очно', online: 'Онлайн', visit: 'Выезд' })[f])
                    .join(', ')}
                </p>
                <p>{s.short_description}</p>
                <p>
                  {s.next_available_at
                    ? `Ближайшее время: ${new Intl.DateTimeFormat('ru', { dateStyle: 'medium', timeStyle: 'short', timeZone: s.timezone }).format(new Date(s.next_available_at))} (${s.timezone})`
                    : 'Нет свободного времени'}
                </p>
                <Button asChild>
                  <Link to={`/s/${s.slug}`}>Посмотреть профиль</Link>
                </Button>
              </Card>
            ))}
          </div>
          <div className="flex gap-3">
            <Button
              variant="outline"
              disabled={!offset}
              onClick={() =>
                setParams((p) => {
                  p.set('offset', String(Math.max(0, offset - 12)))
                  return p
                })
              }
            >
              Назад
            </Button>
            <Button
              variant="outline"
              disabled={offset + 12 >= catalog.data.total}
              onClick={() =>
                setParams((p) => {
                  p.set('offset', String(offset + 12))
                  return p
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
