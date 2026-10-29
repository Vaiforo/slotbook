import { z } from 'zod'

export const bookingFormSchema = z.object({
  client_name: z
    .string()
    .trim()
    .min(1, 'Укажите имя.')
    .max(200, 'Не больше 200 символов.')
    .refine((name) => !/\p{Cc}/u.test(name), 'Уберите управляющие символы из имени.'),
  client_email: z
    .string()
    .trim()
    .max(320, 'Не больше 320 символов.')
    .pipe(z.email('Укажите корректный email, например name@example.com.')),
})
export type BookingFormValues = z.infer<typeof bookingFormSchema>
