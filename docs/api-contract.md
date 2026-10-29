# HTTP-контракт SlotBook

Источник типов реализованного API — Pydantic и настоящий OpenAPI
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
409 `slot_unavailable` / `booking_started`, 413 `payload_too_large`,
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

### Создание бронирования

```http
POST /api/v1/bookings
Content-Type: application/json

{"slot_id":"<UUID свободного слота>","client_name":"Анна Тестовая","client_email":"client@example.com"}
```

201 возвращается только после commit транзакции. Ответ содержит `id`, `slot_id`,
`client_name`, `client_email`, `status: "confirmed"`, `starts_at`, `ends_at`,
`created_at`, `cancelled_at: null` и `manage_token`.

`slot_id` — UUID, имя после trim — 1–200 символов без управляющих символов,
email — синтаксически валидный адрес длиной не более 320 символов. Доставка
письма не проверяется и не выполняется. Лишние JSON-поля запрещены.
Тела POST/PUT/PATCH ограничены **16 KiB фактических байтов**, включая chunked
запросы; превышение возвращает 413 `payload_too_large` до разбора JSON/транзакции.

Слот отсутствует — 404 `not_found`; закрыт, прошёл или уже занят — 409
`slot_unavailable`. Валидация — 422 `validation_error`. При конфликте не создаётся
дополнительная запись. Нет автоматического retry POST и гарантии Idempotency-Key:
если соединение оборвалось после commit, повтор может вернуть 409, а исходный
manage token нельзя восстановить повторным запросом. Не повторяйте POST вслепую.

`manage_token` — 32 случайных байта (256 бит), URL-safe строка длиной 43 символа.
Он возвращается один раз при создании; PostgreSQL хранит только SHA-256-хеш.
Секрет даёт доступ только к одной записи, его нельзя публиковать или хранить
в URL query, localStorage либо логах. Форма записи показывает подтверждение
с копируемой ссылкой `/manage/<id>#token=…`. Страница управления забирает секрет
в память до React/router mount и сразу очищает fragment; API получает его только
через Authorization. После обновления страницы требуется вновь открыть сохранённую
полную ссылку. Переход по ссылке не отменяет запись: отмена требует подтверждения.

### Чтение и отмена по секрету

```http
GET /api/v1/bookings/<booking-id>
Authorization: Bearer <manage-token>
```

200 содержит те же поля записи, кроме `manage_token`. Хеш никогда не возвращается.
GET ничего не изменяет. UUID записи без секрета не даёт доступ. Отсутствующая запись,
неверный/отсутствующий token, token другой записи, cookie или token в query вместо
Authorization возвращают одинаковый 404 `not_found`. Cookie-сессия владельца
не используется как обход проверки секрета.

```http
POST /api/v1/bookings/<booking-id>/cancel
Authorization: Bearer <manage-token>
```

200 возвращает запись со `status: "cancelled"` и `cancelled_at`. Отмена возможна
до начала встречи; после начала — 409 `booking_started`. Повторная отмена уже
отменённой записи возвращает тот же результат даже после её начала. Она не отменяет
новую запись на этот слот и не меняет состояние слота: закрытый слот остаётся закрытым.
Все ответы имеют `Cache-Control: no-store` и `Referrer-Policy: no-referrer`.

Создание и отмена используют один порядок блокировок: **slot → booking**.
Слот блокируется `SELECT … FOR UPDATE`, текущее время PostgreSQL проверяется
через `clock_timestamp()` после получения блокировки; `now()` здесь не подходит,
потому что фиксируется в начале транзакции. Проверка и изменения выполняются
в одной транзакции. Частичный UNIQUE дополнительно запрещает две confirmed-записи.
Только нарушение `one_confirmed_booking_per_slot` переводится в 409 после rollback;
другие ошибки целостности не маскируются под занятое время.

### Frontend-потребители

`getSpecialist`, `getAvailableSlots`, `createBooking`, `getBooking` и `cancelBooking` в `src/lib/api.ts` используют сгенерированные
типы. Общий request добавляет Accept, same-origin credentials, передаёт AbortSignal,
не повторяет запросы автоматически. `ApiError` содержит status, code, requestId.
HTML/не-JSON от proxy преобразуется в безопасный `invalid_response`.
Для будущих mutations предусмотрен X-CSRF-Token; запросы GET его не добавляют.
Ни CSRF, ни manage token не сохраняются клиентом в localStorage.

`queryKeys.specialist(slug)` и `queryKeys.slots(slug, filters)` включают все фильтры
и нормализуют значения пагинации по умолчанию. Публичная страница /s/:slug
использует TanStack Query и общий клиент. HTTP-ошибки 4xx не повторяются; для
сети/5xx разрешена одна повторная попытка. Публичные ответы типизированы по OpenAPI.

## API владельца

Все изменения с cookie требуют точного Origin из SLOTBOOK_PUBLIC_ORIGIN.
Вход также проверяет Origin для защиты от login CSRF. Сессия живёт 12 часов,
в БД хранится только хеш. Повторный вход отзывает текущую сессию этого браузера.

### Вход, сессия и выход

```http
POST /api/v1/auth/login
Content-Type: application/json

{"email":"owner@example.invalid","password":"<password>"}
```

Успех 204, `Set-Cookie` с непрозрачной сессией HttpOnly/Secure/SameSite=Lax.
Для HTTP cookie без Secure разрешена только development/test loopback-конфигурация.
Production требует HTTPS origin; Secure не зависит от входящего Host.
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

### Управление слотами

```http
POST /api/v1/slots
Cookie: session=<opaque-token>
X-CSRF-Token: <csrf-token>
Content-Type: application/json

{"starts_at":"2030-01-01T10:00:00+06:00","ends_at":"2030-01-01T10:30:00+06:00"}
```

201: `id`, `starts_at`, `ends_at`, `state: "open"`. Специалист выводится из сессии,
не задаётся произвольным client-side specialist_id. Пересечение — 409 `slot_overlap`, прошлое время — 409 `slot_started`.
Длительность ровно 30 минут, timezone offset обязателен; лишние поля запрещены.

```http
PATCH /api/v1/slots/<slot-id>
Cookie: session=<opaque-token>
X-CSRF-Token: <csrf-token>
Content-Type: application/json

{"state":"closed"}
```

200: обновлённый слот. Изменение времени не поддерживается. Чужой слот — 404;
закрытие слота с активной записью — 409 `slot_booked`; прошедший слот — 409 `slot_started`. Повторное открытие — `state: "open"`.

### Список записей владельца

```http
GET /api/v1/me/bookings?from=2030-01-01T00:00:00Z&to=2030-01-02T00:00:00Z&status=confirmed&limit=100&offset=0
Cookie: session=<opaque-token>
```

200: `{items, limit, offset}` со своими записями и контактами; ownership учитывается
в SQL. Нет сессии — 401. Перечисленные приватные ответы — no-store/no-referrer.

Коды ошибок: 401 unauthorized, 403 forbidden, 404 not_found,
409 slot_unavailable или конкретный business code, 422 validation_error,
500 internal_error. Rate limiting пока не реализован.
