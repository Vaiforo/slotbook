import { useRef, useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useQueryClient } from '@tanstack/react-query'
import { useLocation, useNavigate } from 'react-router-dom'
import { ApiError } from '@/lib/api'
import { currentOwner, loginOwner, sessionKey } from '@/lib/owner-api'
import { clearOwnerSession, loginDestination } from '@/lib/owner-session'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

const schema = z.object({
  email: z.string().trim().pipe(z.email('Укажите корректный email.')),
  password: z.string().min(1, 'Введите пароль.').max(1024, 'Пароль слишком длинный.'),
})
export function LoginPage() {
  const client = useQueryClient()
  const navigate = useNavigate()
  const location = useLocation()
  const [error, setError] = useState('')
  const sending = useRef(false)
  const form = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema) })
  return (
    <Card className="mx-auto max-w-md space-y-6 p-6 sm:p-8">
      <div className="space-y-3">
        <p className="eyebrow">Кабинет специалиста</p>
        <h1>Войти в SlotBook</h1>
        <p className="text-sm text-muted-foreground">
          {new URLSearchParams(location.search).has('next')
            ? 'Войдите, чтобы продолжить работу. После входа вернём вас к выбранной странице.'
            : 'Управляйте расписанием и встречами в одном месте.'}
        </p>
      </div>
      <form
        noValidate
        className="space-y-4"
        onSubmit={(event) => {
          void form.handleSubmit(async (data) => {
            if (sending.current) return
            sending.current = true
            setError('')
            clearOwnerSession(client)
            try {
              await loginOwner(data)
              const identity = await currentOwner(AbortSignal.timeout(10_000))
              client.setQueryData(sessionKey, identity)
              form.reset()
              navigate(loginDestination(location.search), { replace: true })
            } catch (reason) {
              setError(
                reason instanceof ApiError && reason.status === 401
                  ? 'Неверный email или пароль.'
                  : 'Не удалось войти. Проверьте соединение и попробуйте снова.',
              )
            } finally {
              sending.current = false
            }
          })(event)
        }}
      >
        <fieldset disabled={form.formState.isSubmitting} className="space-y-4">
          <div className="space-y-2">
            <label htmlFor="owner-email">Email</label>
            <Input
              id="owner-email"
              type="email"
              autoComplete="username"
              {...form.register('email')}
              aria-invalid={!!form.formState.errors.email}
              aria-describedby="owner-email-error"
            />
            <p role="alert" id="owner-email-error" className="text-sm text-red-700">
              {form.formState.errors.email?.message}
            </p>
          </div>
          <div className="space-y-2">
            <label htmlFor="owner-password">Пароль</label>
            <Input
              id="owner-password"
              type="password"
              autoComplete="current-password"
              {...form.register('password')}
              aria-invalid={!!form.formState.errors.password}
              aria-describedby="owner-password-error"
            />
            <p role="alert" id="owner-password-error" className="text-sm text-red-700">
              {form.formState.errors.password?.message}
            </p>
          </div>
          <Button type="submit" className="w-full">
            {form.formState.isSubmitting ? 'Входим…' : 'Войти'}
          </Button>
        </fieldset>
        {error && (
          <p role="alert" className="text-sm text-red-700">
            {error}
          </p>
        )}
      </form>
    </Card>
  )
}
