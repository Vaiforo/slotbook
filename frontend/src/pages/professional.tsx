import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { request, ApiError } from '@/lib/api'
import { useOwner } from '@/lib/use-owner'
import type { components } from '@/generated/api-types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card } from '@/components/ui/card'

type Profile = components['schemas']['ProfessionalDetails']
type ProfileInput = Omit<components['schemas']['ProfessionalSave'], 'services'>
const labels: Record<string, string> = {
  display_name: 'Публичное имя',
  specialization: 'Специализация',
  short_description: 'Краткое описание',
  description: 'О себе',
  city: 'Город',
  workplace: 'Место приёма',
  service_area: 'Территория обслуживания',
  timezone: 'Часовой пояс IANA',
}

export function ProfessionalPage() {
  const owner = useOwner()
  const profile = useQuery({
    queryKey: ['owner', owner.id, 'professional'],
    queryFn: ({ signal }) => request<Profile>('/me/specialist', { signal }),
  })
  if (profile.isPending) return <p role="status">Загружаем профиль…</p>
  if (profile.isError && !profile.data)
    return (
      <div role="alert">
        Не удалось загрузить профиль.{' '}
        <Button onClick={() => void profile.refetch()}>Повторить</Button>
      </div>
    )
  return (
    <>
      {profile.isError && (
        <p role="alert">Не удалось обновить профиль. Черновик сохранён на экране.</p>
      )}
      <ProfessionalForm key={profile.data!.slug} initial={profile.data!} />
    </>
  )
}

function ProfessionalForm({ initial }: { initial: Profile }) {
  const owner = useOwner()
  const client = useQueryClient()
  const { slug, publication_status, services: initialServices, ...fields } = initial
  const [data, setData] = useState<ProfileInput>(fields)
  const [status, setStatus] = useState(publication_status)
  const [services, setServices] = useState(initialServices)
  const [message, setMessage] = useState('')
  const mutation = useMutation({
    mutationKey: ['owner', 'professional'],
    retry: false,
    gcTime: 0,
    mutationFn: async (action: string) => {
      const options = {
        signal: AbortSignal.timeout(30_000),
        csrfToken: owner.csrf_token,
        headers: { 'Content-Type': 'application/json' },
      }
      if (action === 'save') {
        return request<Profile>('/me/specialist', {
          ...options,
          method: 'PATCH',
          body: JSON.stringify({ ...data, services }),
        })
      }
      return request<Profile>(`/me/specialist/${action}`, { ...options, method: 'POST' })
    },
    onSuccess: (profile) => {
      setStatus(profile.publication_status)
      void client.invalidateQueries({ queryKey: ['owner', 'session'] })
      setMessage('Изменения сохранены')
      void client.invalidateQueries({ queryKey: ['catalog'] })
      void client.invalidateQueries({ queryKey: ['specialists', slug] })
      void client.invalidateQueries({ queryKey: ['owner', owner.id, 'professional'] })
    },
    onError: (error) =>
      setMessage(
        error instanceof ApiError && error.code === 'profile_incomplete'
          ? 'Заполните имя, категорию, специализацию, оба описания, город и формат работы. Для очного приёма укажите место, для выезда — территорию.'
          : error instanceof ApiError && error.code === 'timezone_has_slots'
            ? 'Нельзя изменить часовой пояс при наличии будущих интервалов.'
            : 'Не удалось сохранить. Проверьте данные и повторите попытку.',
      ),
  })
  return (
    <section className="space-y-5">
      <h2 className="text-2xl font-semibold">Публичный профиль</h2>
      <p>Статус: {status === 'published' ? 'Опубликован' : 'Черновик'}</p>
      <p>Сначала сохраните изменения, затем опубликуйте профиль.</p>
      <form
        onSubmit={(e) => {
          e.preventDefault()
          setMessage('')
          mutation.mutate('save')
        }}
      >
        <fieldset disabled={mutation.isPending} className="space-y-4">
          {Object.entries(labels).map(([name, label]) => (
            <label key={name} className="block">
              {label}
              {['description', 'short_description'].includes(name) ? (
                <textarea
                  className="block min-h-28 w-full rounded border p-3"
                  maxLength={name === 'description' ? 10000 : 500}
                  value={String(data[name as keyof ProfileInput] ?? '')}
                  onChange={(e) => setData({ ...data, [name]: e.target.value })}
                />
              ) : (
                <Input
                  required={name === 'display_name' || name === 'timezone'}
                  maxLength={
                    ['workplace', 'service_area'].includes(name)
                      ? 500
                      : name === 'city' || name === 'timezone'
                        ? 100
                        : 200
                  }
                  value={String(data[name as keyof ProfileInput] ?? '')}
                  onChange={(e) => setData({ ...data, [name]: e.target.value })}
                />
              )}
            </label>
          ))}
          <label className="block">
            Категория
            <select
              className="block w-full rounded border p-3"
              value={data.category_code || ''}
              onChange={(e) =>
                setData({
                  ...data,
                  category_code: (e.target.value || null) as ProfileInput['category_code'],
                })
              }
            >
              <option value="">Не выбрана</option>
              <option value="medicine">Медицина</option>
              <option value="plumbing">Сантехника</option>
              <option value="law">Юриспруденция</option>
              <option value="delivery">Доставка</option>
            </select>
          </label>
          <label className="block">
            Опыт в годах
            <Input
              type="number"
              min={0}
              max={80}
              value={data.experience_years ?? ''}
              onChange={(e) =>
                setData({
                  ...data,
                  experience_years: e.target.value ? Number(e.target.value) : null,
                })
              }
            />
          </label>
          <fieldset>
            <legend>Формат работы</legend>
            {[
              ['office', 'Очно'],
              ['online', 'Онлайн'],
              ['visit', 'Выезд'],
            ].map(([value, label]) => (
              <label key={value} className="mr-4 inline-flex gap-2">
                <input
                  type="checkbox"
                  checked={(data.work_formats || '').split(',').includes(value)}
                  onChange={(e) => {
                    const formats = (data.work_formats || '')
                      .split(',')
                      .filter(Boolean)
                      .filter((f) => f !== value)
                    if (e.target.checked) formats.push(value)
                    setData({ ...data, work_formats: formats.join(',') })
                  }}
                />
                {label}
              </label>
            ))}
          </fieldset>
          <Card className="space-y-3 p-4">
            <h3>Услуги</h3>
            {services.map((s, i) => (
              <div key={i} className="space-y-2">
                <label>
                  Название услуги {i + 1}
                  <Input
                    required
                    maxLength={200}
                    value={s.name}
                    onChange={(e) =>
                      setServices(
                        services.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)),
                      )
                    }
                  />
                </label>
                <label>
                  Описание услуги {i + 1}
                  <Input
                    maxLength={2000}
                    value={s.description || ''}
                    onChange={(e) =>
                      setServices(
                        services.map((x, j) =>
                          j === i ? { ...x, description: e.target.value } : x,
                        ),
                      )
                    }
                  />
                </label>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setServices(services.filter((_, j) => j !== i))}
                >
                  Удалить услугу {i + 1}
                </Button>
              </div>
            ))}
            <Button
              type="button"
              variant="outline"
              disabled={services.length >= 30}
              onClick={() => setServices([...services, { name: '', description: '' }])}
            >
              Добавить услугу
            </Button>
          </Card>
          <Button type="submit">Сохранить профиль</Button>{' '}
          <Button
            type="button"
            variant="outline"
            onClick={() => {
              setMessage('')
              mutation.mutate(status === 'published' ? 'unpublish' : 'publish')
            }}
          >
            {status === 'published' ? 'Снять с публикации' : 'Опубликовать'}
          </Button>
        </fieldset>
      </form>
      <p role="status">{message}</p>
      {status === 'published' && <Link to={`/s/${slug}`}>Открыть публичную страницу</Link>}
    </section>
  )
}
