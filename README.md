# SlotBook

Сервис записи на консультации. Реализован **только этап 01**: React/TypeScript/Vite
и FastAPI с настоящим HTTP-запросом между ними. Расписание, бронирование,
авторизация и БД пока не реализованы.

## Требования

- Python **3.14** (uv установит его при необходимости).
- Node.js **24 LTS**, npm; версии зафиксированы в `.python-version` / `.node-version`.
- [uv](https://docs.astral.sh/uv/getting-started/installation/) и GNU Make.
- Docker для этапа 01 не нужен.

Проверено на Python 3.14.8, Node 24.19.0, npm 11.9.0, uv 0.12.23.
Исходный системный Python 3.12 не соответствует выбранной архитектуре;
uv использует отдельный Python 3.14, не меняя системный интерпретатор.

## Локальный запуск

Все команды ниже выполняются из корня `slotbook/`.

```bash
make install
# Необязательно: значения по умолчанию уже пригодны для локального запуска.
cp .env.example .env
```

В первом терминале:

```bash
make backend
```

Во втором:

```bash
make frontend
```

Откройте [SlotBook](http://127.0.0.1:5173).
Страница покажет «API доступен» и полученный от сервера ответ.
Кнопка «Проверить ещё раз» отправляет новый запрос. Если backend остановлен,
появится ошибка; после его запуска повторная проверка восстановит состояние.
Запрос ограничен тайм-аутом 5 секунд. Данные не подменяются заглушками.

- [Liveness](http://127.0.0.1:8000/health/live):
  `{"status":"ok","service":"SlotBook"}`.
- [Swagger UI](http://127.0.0.1:8000/docs),
  [OpenAPI](http://127.0.0.1:8000/openapi.json).
- `GET /health/live` проверяет жизнь процесса, **не готовность БД**.
  `/health/ready` появится после подключения БД.

```text
React → GET /health/live на :5173 → Vite proxy → FastAPI на :8000 → JSON → React
```

Vite проксирует `/health` и `/api` без изменения пути. Неизвестные API-маршруты
возвращают JSON 404 от FastAPI. Оба dev-сервера слушают только loopback;
порты 8000 и 5173 должны быть свободны. Запуск останавливается через Ctrl+C.

## Настройки

Корневой `.env` читается backend независимо от текущей директории, а также Vite.
Переменные процесса имеют приоритет. Пример содержит только несекретные значения:

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `SLOTBOOK_APP_NAME` | `SlotBook` | Имя API и `service` в liveness |
| `SLOTBOOK_ENVIRONMENT` | `development` | `development`, `test` или `production` |
| `SLOTBOOK_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `API_PROXY_TARGET` | `http://127.0.0.1:8000` | Адрес backend для dev-прокси Vite |

После изменения `.env` перезапустите серверы. `API_PROXY_TARGET` используется
только процессом Vite. Переменные `VITE_*` не требуются: всё с таким префиксом
публично и не должно содержать секреты. `.env`, окружения, кэши и сборки исключены
из Git; оба lock-файла сохранены.

Логи приложения — JSON со временем UTC, уровнем, logger и сообщением.
Сырые access-логи отключены, чтобы не записывать query strings.
HTTP request_id и единый формат ошибок относятся к этапу 03.

## Проверки

```bash
make check
```

Команда выполняет Ruff, проверку форматирования, mypy strict, pytest,
ESLint, TypeScript strict (`tsc --noEmit`) и production-сборку Vite.
Backend-тесты проверяют HTTP-контракт liveness, настройки, JSON-логи
и отсутствие фиктивных business/readiness endpoints.

Для браузерной проверки остановите dev-серверы: тест сам запускает FastAPI и Vite.
При первой установке загрузите Chromium:

```bash
cd frontend
npx playwright install chromium
cd ..
make smoke
```

Либо используйте установленный совместимый Chromium (так проверено в облачной среде):

```bash
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium make smoke
```

Первый smoke test проверяет настоящий запрос из React через Vite к FastAPI,
повторную проверку, JSON 404 для отсутствующего API, отсутствие ошибок JavaScript
и горизонтального переполнения на 390/768/1440 px. Второй намеренно обрывает
запрос средствами Playwright, проверяет ошибку и повторное обращение к настоящему API.
Скриншоты сохраняются в `frontend/test-results/`; проверенные снимки этапа —
в `docs/screenshots/`. Это проверка каркаса, не сквозные сценарии бронирования этапа 09.

Makefile размещает кэши uv/npm и управляемый Python в игнорируемой `.cache/`
внутри проекта. Зависимости устанавливаются через `uv sync --frozen` и `npm ci`.
Окружение backend находится в `backend/.venv/`.

`frontend/dist/` — результат сборки. Production reverse proxy, контейнеры,
CI и деплой пока не настроены; собранный frontend требует проксирования
`/health` и `/api` к backend. Они будут добавлены в своих этапах.

## Документы и состояние

- [Фактический прогресс](docs/progress.md).
- [Описание изменений для будущего PR](docs/pr-project-foundation.md).
- [Исходная архитектура](docs/reference/slotbook-architecture.md).
- [Исходный план](docs/reference/slotbook-astra-plan.md).

`docs/reference/` содержит неизменённые снимки приложенных документов.
Упоминания «ещё не реализовано» в них относятся к дате подготовки спецификации;
актуальное состояние ведётся отдельно в `docs/progress.md`.
