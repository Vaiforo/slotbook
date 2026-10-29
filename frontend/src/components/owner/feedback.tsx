import { ApiError } from '@/lib/api'

export function ownerError(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 409) {
      if (error.code === 'slot_overlap')
        return 'Это время пересекается с существующим слотом. Выберите другое время.'
      if (error.code === 'slot_booked')
        return 'На это время уже записался клиент. Закрыть слот нельзя.'
      return 'Время встречи уже наступило. Обновите расписание.'
    }
    if (error.status === 403)
      return 'Не удалось подтвердить доступ. Обновите страницу и повторите действие.'
    if (error.status === 422) return 'Проверьте дату и время. Встреча должна длиться 30 минут.'
    if (error.status === 404) return 'Слот недоступен. Обновите расписание.'
  }
  return 'Не удалось получить подтверждение. Изменение могло сохраниться — обновите расписание перед повторной попыткой.'
}
