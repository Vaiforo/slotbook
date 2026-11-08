import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Link, useOutletContext } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { ApiError, request } from '@/lib/api'
import { sessionKey, type Identity } from '@/lib/owner-api'
import { clearOwnerSession } from '@/lib/owner-session'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card } from '@/components/ui/card'

export function AccountOverview() {
  const user = useOutletContext<Identity>()
  return (
    <Card className="space-y-4 p-6">
      <h2>Здравствуйте, {user.full_name || user.email}!</h2>
      <p>
        {user.role === 'specialist'
          ? 'Аккаунт специалиста создан. Заполните личные данные и проверьте часовой пояс.'
          : 'Добро пожаловать в личный кабинет клиента. Проверьте личные данные перед записью к специалисту.'}
      </p>
      <Link to="/dashboard/profile">Заполнить личные данные</Link>
    </Card>
  )
}

const profileSchema = z.object({
  full_name: z.string().trim().min(1, 'Укажите имя').max(200),
  phone: z.string().trim().max(30),
  timezone: z
    .string()
    .min(1, 'Укажите часовой пояс')
    .refine((value) => {
      try {
        new Intl.DateTimeFormat('ru', { timeZone: value })
        return true
      } catch {
        return false
      }
    }, 'Неизвестный часовой пояс'),
})

export function AccountProfile() {
  const user = useOutletContext<Identity>()
  const client = useQueryClient()
  const [message, setMessage] = useState('')
  const form = useForm<z.infer<typeof profileSchema>>({
    resolver: zodResolver(profileSchema),
    defaultValues: { full_name: user.full_name, phone: user.phone, timezone: user.timezone },
  })
  return (
    <Card className="max-w-xl space-y-4 p-6">
      <h2>Личные данные</h2>
      <p>Email: {user.email}</p>
      <form
        noValidate
        className="space-y-4"
        onSubmit={form.handleSubmit(async (values) => {
          setMessage('')
          try {
            const updated = await request<Identity>('/me/profile', {
              method: 'PATCH',
              csrfToken: user.csrf_token,
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(values),
              signal: AbortSignal.timeout(15_000),
            })
            client.setQueryData(sessionKey, updated)
            form.reset(values)
            setMessage('Данные сохранены')
          } catch {
            setMessage('Не удалось сохранить данные. Обновите страницу и повторите попытку.')
          }
        })}
      >
        <fieldset disabled={form.formState.isSubmitting} className="space-y-4">
          {(
            [
              ['full_name', 'Имя'],
              ['phone', 'Телефон'],
              ['timezone', 'Часовой пояс IANA (например, Asia/Omsk)'],
            ] as const
          ).map(([name, label]) => (
            <div key={name}>
              <label htmlFor={name}>{label}</label>
              <Input
                id={name}
                type={name === 'phone' ? 'tel' : 'text'}
                {...form.register(name)}
                aria-invalid={!!form.formState.errors[name]}
              />
              <p role="alert">{form.formState.errors[name]?.message}</p>
            </div>
          ))}
          <Button type="submit">Сохранить</Button>
        </fieldset>
      </form>
      <p role="status">{message}</p>
    </Card>
  )
}

const passwordSchema = z
  .object({
    current_password: z.string().min(1, 'Введите текущий пароль').max(1024),
    new_password: z.string().min(12, 'Минимум 12 символов').max(1024),
    confirmation: z.string(),
  })
  .refine((v) => v.new_password === v.confirmation, {
    path: ['confirmation'],
    message: 'Пароли не совпадают',
  })

export function AccountSecurity() {
  const user = useOutletContext<Identity>()
  const client = useQueryClient()
  const [error, setError] = useState('')
  const form = useForm<z.infer<typeof passwordSchema>>({ resolver: zodResolver(passwordSchema) })
  return (
    <Card className="max-w-xl space-y-4 p-6">
      <h2>Безопасность</h2>
      <p>После смены пароля все сеансы завершатся. Войдите с новым паролем.</p>
      <form
        noValidate
        className="space-y-4"
        onSubmit={form.handleSubmit(async ({ current_password, new_password }) => {
          setError('')
          try {
            await request<void>('/auth/change-password', {
              method: 'POST',
              csrfToken: user.csrf_token,
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ current_password, new_password }),
              signal: AbortSignal.timeout(30_000),
            })
            form.reset()
            clearOwnerSession(client)
            window.location.replace('/login?passwordChanged=1')
          } catch (reason) {
            setError(
              reason instanceof ApiError && reason.code === 'invalid_password'
                ? 'Текущий пароль неверен'
                : 'Не удалось изменить пароль. Обновите страницу и повторите попытку.',
            )
          }
        })}
      >
        <fieldset disabled={form.formState.isSubmitting} className="space-y-4">
          {(
            [
              ['current_password', 'Текущий пароль'],
              ['new_password', 'Новый пароль'],
              ['confirmation', 'Повторите новый пароль'],
            ] as const
          ).map(([name, label]) => (
            <div key={name}>
              <label htmlFor={name}>{label}</label>
              <Input
                id={name}
                type="password"
                autoComplete={name === 'current_password' ? 'current-password' : 'new-password'}
                {...form.register(name)}
                aria-invalid={!!form.formState.errors[name]}
              />
              <p role="alert">{form.formState.errors[name]?.message}</p>
            </div>
          ))}
          <Button type="submit">Изменить пароль</Button>
        </fieldset>
        <p role="alert">{error}</p>
      </form>
    </Card>
  )
}
