import { useState } from 'react'
import { useForm, useWatch } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { request, ApiError } from '@/lib/api'
import { sessionKey, type Identity } from '@/lib/owner-api'
import { clearOwnerSession, loginDestination } from '@/lib/owner-session'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card } from '@/components/ui/card'

const schema = z
  .object({
    role: z.enum(['client', 'specialist']),
    full_name: z.string().trim().min(1, 'Укажите имя').max(200),
    email: z.email('Укажите корректный email'),
    password: z.string().min(12, 'Минимум 12 символов').max(1024),
    confirmation: z.string(),
    category_code: z.string(),
  })
  .refine((v) => v.password === v.confirmation, {
    path: ['confirmation'],
    message: 'Пароли не совпадают',
  })
  .refine((v) => v.role !== 'specialist' || !!v.category_code, {
    path: ['category_code'],
    message: 'Выберите категорию',
  })

export function RegisterPage() {
  const [step, setStep] = useState(1)
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const location = useLocation()
  const client = useQueryClient()
  const form = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: { role: 'client', category_code: '' },
  })
  const role = useWatch({ control: form.control, name: 'role' })
  return (
    <Card className="mx-auto max-w-md space-y-5 p-6">
      <h1>Регистрация</h1>
      {step === 1 ? (
        <div className="space-y-4">
          <fieldset className="space-y-3">
            <legend>Выберите роль</legend>
            <label className="block">
              <input type="radio" value="client" {...form.register('role')} /> Клиент — ищу
              специалиста
            </label>
            <label className="block">
              <input type="radio" value="specialist" {...form.register('role')} /> Специалист —
              предлагаю услуги
            </label>
          </fieldset>
          <Button onClick={() => setStep(2)}>Продолжить</Button>
        </div>
      ) : (
        <form
          noValidate
          className="space-y-4"
          onSubmit={form.handleSubmit(async (values) => {
            setError('')
            try {
              clearOwnerSession(client)
              const identity = await request<Identity>('/auth/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  role: values.role,
                  full_name: values.full_name,
                  email: values.email,
                  password: values.password,
                  timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Omsk',
                  category_code: values.role === 'specialist' ? values.category_code : null,
                }),
                signal: AbortSignal.timeout(30_000),
              })
              client.setQueryData(sessionKey, identity)
              form.reset()
              navigate(
                identity.role === 'client' ? loginDestination(location.search) : '/dashboard',
                { replace: true },
              )
            } catch (reason) {
              setError(
                reason instanceof ApiError && reason.code === 'email_exists'
                  ? 'Этот email уже зарегистрирован. Войдите в аккаунт.'
                  : 'Не удалось зарегистрироваться. Проверьте данные и повторите попытку.',
              )
            }
          })}
        >
          <p>Роль: {role === 'client' ? 'Клиент' : 'Специалист'}</p>
          <fieldset disabled={form.formState.isSubmitting} className="space-y-4">
            {(
              [
                ['full_name', 'Имя', 'text', 'name'],
                ['email', 'Email', 'email', 'email'],
                ['password', 'Пароль', 'password', 'new-password'],
                ['confirmation', 'Повторите пароль', 'password', 'new-password'],
              ] as const
            ).map(([name, label, type, autocomplete]) => (
              <div key={name}>
                <label htmlFor={`register-${name}`}>{label}</label>
                <Input
                  id={`register-${name}`}
                  type={type}
                  autoComplete={autocomplete}
                  {...form.register(name)}
                  aria-invalid={!!form.formState.errors[name]}
                  aria-describedby={`error-${name}`}
                />
                <p id={`error-${name}`} role="alert">
                  {form.formState.errors[name]?.message}
                </p>
              </div>
            ))}
            {role === 'specialist' && (
              <div>
                <label htmlFor="category">Категория</label>
                <select
                  id="category"
                  {...form.register('category_code')}
                  className="block w-full rounded border p-3"
                >
                  <option value="">Выберите категорию</option>
                  <option value="medicine">Медицина</option>
                  <option value="plumbing">Сантехника</option>
                  <option value="law">Юриспруденция</option>
                  <option value="delivery">Доставка</option>
                </select>
                <p role="alert">{form.formState.errors.category_code?.message}</p>
                <p className="text-sm">
                  Подробную информацию о себе и сменах можно заполнить в кабинете.
                </p>
              </div>
            )}
            <Button type="button" variant="outline" onClick={() => setStep(1)}>
              Назад
            </Button>{' '}
            <Button type="submit">
              {form.formState.isSubmitting ? 'Создаём аккаунт…' : 'Зарегистрироваться'}
            </Button>
          </fieldset>
          {error && <p role="alert">{error}</p>}
        </form>
      )}
      <p>
        Уже есть аккаунт? <Link to={`/login${location.search}`}>Войти</Link>
      </p>
    </Card>
  )
}
