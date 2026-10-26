# HTTP-контракт SlotBook

Этап 03. Источник типов реализованного API — Pydantic и настоящий OpenAPI
в `docs/openapi.json`; TypeScript — `frontend/src/generated/api-types.ts`.
`make api-generate` обновляет оба файла, `make api-check` проверяет их без записи.
Экспорт не запускает lifespan и не открывает подключение к БД.

## Реализовано

Все API пути ниже имеют префикс `/api/v1`. Запросы — same-origin через Vite proxy.
Ответы содержат `X-Request-ID` (новый UUID сервера, входящий заголовок не используется)
и `Cache-Control: no-store`. Ошибки имеют единую структуру:

```json
{"error":{"code":"validation_error","message":"Проверьте параметры запроса.","request_id":"e9d087ae-77d8-49fb-b3e2-d546b89cc9aa"}}
```

`request_id` в теле совпадает с заголовком. В error body и логах нет исходного
ввода, контактов, токенов, SQL-параметров или текста внутреннего исключения.
Лог HTTP содержит request_id, шаблон route, method, status, duration_ms;
неизвестный маршрут записывается как `<unmatched>`, без сырого URL/query string.
Коды сейчас: 404 `not_found`, 405 `method_not_allowed` (с Allow),
422 `validation_error`, 500 `internal_error` с безопасным общим сообщением.

### Публичный профиль

```http
GET /api/v1/specialists/demo
```

200, пример структуры (UUID демонстрационный):

```json
{
  "id": "ab5b0099-ecbd-4a31-a346-001afc9a3fbd",
  "slug": "demo",
  "display_name": "Демо-специалист",
  "timezone": "Asia/Omsk"
}
```

Только эти четыре поля. Нет user_id, email, password_hash или session/token fields.
Неизвестный slug возвращает 404.

### Доступные слоты

```http
GET /api/v1/specialists/demo/slots?from=2030-01-01T00:00:00%2B06:00&to=2030-01-02T00:00:00%2B06:00&limit=100&offset=0
```

Пример параметров демонстрирует формат; реальные даты seed вычисляются относительно
даты запуска. Символ `+` кодируется как `%2B`; предпочтительно использовать URLSearchParams.

- `from` и `to` обязательны, ISO 8601 с UTC offset или `Z`; наивное время запрещено.
- `0 < to - from <= 31 день` по абсолютному времени UTC, ровно 31 день разрешён.
- Фильтр по началу слота: `starts_at >= from AND starts_at < to`.
- `limit`: 1–100, по умолчанию 100. `offset`: 0–10000, по умолчанию 0.
- Неизвестные query-параметры отклоняются с 422.
- Только `open`, начало строго позже `now()` PostgreSQL, нет `confirmed` booking.
  Отменённая запись не блокирует слот. Чужие специалисты не попадают в выборку.
- Сортировка стабильна по `starts_at`, затем `id`. Пустая страница — 200 с `items: []`.
- Неизвестный специалист — 404, даже если нет подходящих слотов.

200, пример структуры:

```json
{
  "items": [{
    "id": "27c5aad9-b897-4d21-b88a-9e3783aeb96c",
    "starts_at": "2030-01-01T04:00:00Z",
    "ends_at": "2030-01-01T04:30:00Z"
  }],
  "limit": 100,
  "offset": 0
}
```

Timestamp всегда содержит timezone; конкретный offset в ответе не фиксирован.
Показывать локальное время следует по timezone специалиста. Пагинация отражает
доступность на момент чтения: последующее бронирование обязано проверить её заново.
В ответе нет контактов, booking ids, manage tokens и сведений о чужих записях.

### Frontend-потребители

`getSpecialist` и `getAvailableSlots` в `src/lib/api.ts` используют сгенерированные
типы. Общий request добавляет Accept, same-origin credentials, передаёт AbortSignal,
не повторяет запросы автоматически. `ApiError` содержит status, code, requestId.
HTML/не-JSON от proxy преобразуется в безопасный `invalid_response`.
Для будущих mutations предусмотрен X-CSRF-Token; запросы GET его не добавляют.
Ни CSRF, ни manage token не сохраняются клиентом в localStorage.

`queryKeys.specialist(slug)` и `queryKeys.slots(slug, filters)` включают все фильтры
и нормализуют значения пагинации по умолчанию. TanStack Query и публичный экран
появятся в этапе 04. Страница health уже использует общий клиент и сохраняет
runtime-проверку своего JSON; публичные ответы типизированы по OpenAPI.

## Проект оставшихся операций — НЕ реализованы

Следующие примеры — договорённости для будущих этапов, не действующие handlers.
Они отсутствуют в OpenAPI и генерируемых типах до реализации. Для защиты от дрейфа
конкретные схемы будут закреплены Pydantic при реализации соответствующего этапа.
UUID и токены ниже — placeholders. Даты в примерах иллюстрируют формат.

### Вход, сессия и выход (этап 07)

```http
POST /api/v1/auth/login
Content-Type: application/json

{"email":"owner@example.invalid","password":"<password>"}
```

Успех 204, `Set-Cookie` с непрозрачной сессией HttpOnly/Secure/SameSite=Lax.
Неверные credentials — 401 без подсказки о существовании email.

```http
GET /api/v1/auth/me
Cookie: session=<opaque-token>
```

200: собственные `id`, `email` и `csrf_token`; без сессии 401.

```http
POST /api/v1/auth/logout
Cookie: session=<opaque-token>
X-CSRF-Token: <csrf-token>
Origin: https://<slotbook-host>
```

204; сессия отозвана, cookie удалена. Неверный CSRF/Origin — 403.

### Управление слотами (этап 07)

```http
POST /api/v1/slots
Cookie: session=<opaque-token>
X-CSRF-Token: <csrf-token>
Content-Type: application/json

{"starts_at":"2030-01-01T10:00:00+06:00","ends_at":"2030-01-01T10:30:00+06:00"}
```

201: `id`, `starts_at`, `ends_at`, `state: "open"`. Специалист выводится из сессии,
не задаётся произвольным client-side specialist_id. Пересечение — 409.

```http
PATCH /api/v1/slots/<slot-id>
Cookie: session=<opaque-token>
X-CSRF-Token: <csrf-token>
Content-Type: application/json

{"state":"closed"}
```

200: обновлённый слот. Изменение времени не поддерживается. Чужой слот — 404;
закрытие слота с активной записью — 409. Повторное открытие — `state: "open"`.

### Создание и управление записью (этапы 05–07)

```http
POST /api/v1/bookings
Content-Type: application/json

{"slot_id":"<slot-id>","client_name":"Демо-клиент","client_email":"client@example.invalid"}
```

201: `id`, `slot_id`, `status: "confirmed"`, `starts_at`, `ends_at`,
`manage_token` (выдаётся при создании один раз). Клиент строит ссылку
`/manage/<id>#token=<manage_token>`; GET не совершает отмену.
Слот недоступен — 409 `slot_unavailable`; неверные поля — 422.
Повтор POST после сетевого обрыва не гарантирует повтор исходного результата.

```http
GET /api/v1/bookings/<booking-id>
Authorization: Bearer <manage-token>
```

200: только эта запись (`id`, `slot_id`, `status`, время, собственные контакты).
Альтернативно владелец использует cookie-сессию с обязательной проверкой ownership.
Неверный token/чужая запись — 404. UUID сам по себе не даёт доступ.

```http
POST /api/v1/bookings/<booking-id>/cancel
Authorization: Bearer <manage-token>
```

200: запись со `status: "cancelled"` и временем отмены. Альтернатива владельца —
cookie + CSRF + Origin. Повторная отмена старой записи не меняет новую запись
на том же слоте. Отмена после начала запрещена (409). Секрет — только в памяти
клиента и Authorization, не в URL query или логах.

```http
GET /api/v1/me/bookings?from=2030-01-01T00:00:00Z&to=2030-01-02T00:00:00Z&status=confirmed&limit=100&offset=0
Cookie: session=<opaque-token>
```

200: `{items, limit, offset}` со своими записями и контактами; ownership учитывается
в SQL. Нет сессии — 401. Перечисленные приватные ответы — no-store/no-referrer.

Базовая таблица будущих ошибок: 401 unauthorized, 403 forbidden, 404 not_found,
409 slot_unavailable или конкретный business code, 422 validation_error,
429 rate_limited (Retry-After), 500 internal_error. Бизнес-коды фиксируются при
реализации сценария, не подменяются общим успешным ответом на текущем этапе.
