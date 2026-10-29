import { useRef } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ApiError, createBooking, type BookingCreated } from '@/lib/api'
import { bookingFormSchema, type BookingFormValues } from '@/lib/booking-form'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

export function BookingForm({
  slotId,
  onBooked,
  onUnavailable,
  onPendingChange,
}: {
  slotId: string
  onBooked: (booking: BookingCreated) => void
  onUnavailable: () => void
  onPendingChange?: (pending: boolean) => void
}) {
  const queryClient = useQueryClient()
  const submitting = useRef(false)
  const form = useForm<BookingFormValues>({
    resolver: zodResolver(bookingFormSchema),
    defaultValues: { client_name: '', client_email: '' },
  })
  const mutation = useMutation({
    retry: false,
    gcTime: 0,
    onMutate: () => onPendingChange?.(true),
    onSettled: () => onPendingChange?.(false),
    mutationFn: async (values: BookingFormValues) => {
      const booking = await createBooking(
        { ...values, slot_id: slotId },
        AbortSignal.timeout(15_000),
      )
      // Keep the secret in the confirmation component, out of mutation data/query keys.
      onBooked(booking)
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ['specialists'],
        predicate: (query) => query.queryKey[2] === 'slots',
      })
    },
    onError: (error) => {
      if (error instanceof ApiError && error.status === 409) {
        onUnavailable()
        void queryClient.invalidateQueries({
          queryKey: ['specialists'],
          predicate: (query) => query.queryKey[2] === 'slots',
        })
      }
    },
  })
  const error = mutation.error
  const message =
    error instanceof ApiError && error.status === 422
      ? 'Сервер не принял данные. Проверьте имя и email и отправьте форму снова.'
      : 'Не удалось получить подтверждение. Запись могла сохраниться. Не отправляйте заявку повторно вслепую: проверьте расписание или свяжитесь со специалистом.'
  return (
    <form
      noValidate
      className="space-y-5"
      onSubmit={(event) => {
        void form.handleSubmit(async (values) => {
          if (submitting.current) return
          submitting.current = true
          try {
            await mutation.mutateAsync(values)
          } catch {
            /* Shown below; never retry automatically. */
          } finally {
            submitting.current = false
          }
        })(event)
      }}
    >
      <fieldset disabled={mutation.isPending} className="space-y-4">
        <div className="space-y-2">
          <label htmlFor="client-name" className="text-sm font-medium">
            Ваше имя
          </label>
          <Input
            id="client-name"
            autoComplete="name"
            {...form.register('client_name')}
            aria-invalid={!!form.formState.errors.client_name}
            aria-describedby="name-error"
          />
          <p id="name-error" className="text-sm text-red-700" role="alert">
            {form.formState.errors.client_name?.message}
          </p>
        </div>
        <div className="space-y-2">
          <label htmlFor="client-email" className="text-sm font-medium">
            Email
          </label>
          <Input
            id="client-email"
            type="email"
            autoComplete="email"
            {...form.register('client_email')}
            aria-invalid={!!form.formState.errors.client_email}
            aria-describedby="email-error"
          />
          <p id="email-error" className="text-sm text-red-700" role="alert">
            {form.formState.errors.client_email?.message}
          </p>
        </div>
        <p className="text-sm text-muted-foreground">
          После записи сохраните секретную ссылку. Письмо с подтверждением пока не отправляется.
        </p>
        <Button type="submit" className="w-full" disabled={mutation.isPending}>
          {mutation.isPending ? 'Записываем…' : 'Подтвердить запись'}
        </Button>
      </fieldset>
      {error && !(error instanceof ApiError && error.status === 409) && (
        <p role="alert" className="text-sm text-red-700">
          {message}
        </p>
      )}
    </form>
  )
}
