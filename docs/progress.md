# Фактический прогресс SlotBook

Актуальное состояние: **26 октября 2026, Asia/Omsk**. Этапы 01–03 реализованы;
подробности и статус Git — в записи каждого этапа ниже.

## Этап 01 — каркас двух приложений

**Реализован и проверен в локальной ветке; ожидает интеграции.**

- Ветка: `feat/project-foundation`.
- Commit реализации и проверенного кода: `d606615deef680ebd8e7956248295e23e9c55127`.
- Этот журнал сохранён отдельным последующим документационным commit;
  его SHA доступен через `git log -1 -- docs/progress.md`.
- Исходная ветка `work` и `origin/main` указывали на
  `17af9e180aabf581c70262d4dec64ffcea43f505`; исходное рабочее дерево было чистым.
- Существующая история и remote `https://github.com/Vaiforo/slotbook.git` сохранены.
- После явного разрешения пользователя ветка `feat/project-foundation` опубликована
  в origin. PR и merge не выполнялись. Локальная `main` не создавалась;
  удалённая `main` не изменена. Реализация доступна в feature-ветке.
- Подготовлен [текст будущего PR](pr-project-foundation.md).

### Реализовано

- `backend/`: FastAPI, Pydantic settings из корневого `.env`, JSON logging,
  типизированный `GET /health/live` с `Cache-Control: no-store`, Swagger/OpenAPI.
- `frontend/`: React 19, TypeScript strict, Vite; настоящий fetch к backend через
  proxy `/health`, состояния loading/success/error, timeout 5 секунд и ручной retry.
  Проверка формы JSON выполняется до показа успешного состояния.
- Proxy `/api` подготовлен; отсутствующие маршруты возвращают JSON 404 backend.
- Установка и проверки через Makefile, `.env.example`, `.gitignore`, `uv.lock`,
  `package-lock.json`, README с командами запуска.
- Backend smoke tests и небольшой browser smoke test каркаса;
  [скриншоты](screenshots/) с ширин 390, 768 и 1440 px.
- Неизменённые приложенные спецификации сохранены в `docs/reference/`.
  Пути `artifacts/slotbook-*.md` отсутствовали в предоставленном checkout,
  поэтому использованы именно загруженные пользователем файлы.

Изменения приложения ограничены `/workspace/slotbook/`. `interview-tracker` и
`sources/` не изменялись; в предоставленном workspace эти каталоги не обнаружены.

### Среда и исправления

До установки проверены Python 3.12.14, Node 24.19.0, npm 11.9.0, uv 0.12.23,
Docker CLI 28.4.0. Для архитектуры установлен отдельный Python **3.14.8** через uv.
Системный Python не изменён. Использован Chromium **154.0.8037.57**.

Домашние каталоги кэшей в облачной среде недоступны для записи; Makefile направляет
кэши и управляемый Python в игнорируемую `.cache/` проекта. Установка пакетов
выполнена через разрешённый сетевой доступ среды.

Предварительный прогон выявил предупреждение устаревшего ESLint 9 и deprecated
использование HTTPX через новый Starlette TestClient. Подключён ESLint 10 с
совместимыми плагинами; backend smoke test использует HTTPX ASGITransport и
pytest-asyncio с настоящим приложением. После изменений выполнен финальный прогон.

### Выполненные проверки

Команды выполнялись из `/workspace/slotbook/` на содержимом commit реализации:

| Команда | Фактический результат |
|---|---|
| `make install` | `uv sync --frozen` и `npm ci` прошли с сохранёнными lock-файлами |
| `make check` | Ruff check/format, mypy strict, pytest, ESLint, tsc и Vite build прошли |
| backend pytest | **3 passed**, без предупреждений: health-контракт, env, JSON logs |
| `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium make smoke` | **2 passed**, Chromium, реальные запущенные FastAPI/Vite |
| `git diff --cached --check` | Ошибок пробелов нет |
| Проверка списка Git-файлов | `.env`, кэши, `.venv`, `node_modules`, `dist` и временные test-results не включены |

Браузер подтвердил HTTP 200 и JSON `{"status":"ok","service":"SlotBook"}`
на запрос самой страницы, текст «API доступен» и повторный запрос по кнопке.
Неизвестный `/api/v1/bookings` через Vite вернул JSON 404, не HTML страницы.
Второй тест намеренно обрывает транспорт через Playwright, проверяет «API недоступен»,
снимает тестовый перехват и подтверждает восстановление через настоящий backend.
В production-коде тестового ответа нет.

На ширинах 390/768/1440 нет горизонтального переполнения; ошибок JavaScript нет,
кнопка фокусируется с клавиатуры. Скриншоты мобильного и desktop-вида просмотрены.
Сохранены снимки всех трёх размеров. Единственное сообщение финального browser-run —
предупреждение Node о одновременно заданных средой `NO_COLOR` и `FORCE_COLOR`;
на проверки оно не влияет.

### Границы проверки и следующий шаг

Критерии этапа 01 выполнены. Проверены dev-связь и сборка frontend; production
развёртывание, БД/readiness, Docker daemon/Compose, CI, защита веток и публичный URL
не проверялись и пока не настроены. Версия `0.0.0` обозначает каркас, релизных тегов нет.

- [x] 01 Каркас двух приложений — реализован в ветке, ожидает интеграции.
- [x] 02 БД и миграции — реализован, проверен и опубликован в feature-ветке.
- [x] 03 Read API и контракт — реализован и проверен в feature-ветке.
- [ ] 04 Публичная страница React.
- [ ] 05 Бронирование и отмена.
- [ ] 06 Клиентский сценарий React.
- [ ] 07 Вход и API кабинета.
- [ ] 08 Кабинет React.
- [ ] 09 Полные сквозные сценарии и визуальная доводка.
- [ ] 10 Production/CI.
- [ ] 11 Review и исправления полного приложения.
- [ ] 12 MVP, демо и учебные материалы.
- [ ] 13 Redis.
- [ ] 14 Очереди и уведомления.
- [ ] 15 AI.

Следующее действие по отдельному поручению: интеграция проверенного этапа 01;
затем этап 02 — PostgreSQL, модели, миграции и seed. В рамках текущей задачи
остальные этапы не запускались.


## Этап 02 — PostgreSQL, миграции и seed

Дата: 25 октября 2026, Asia/Omsk. **Реализован, проверен и опубликован в feature-ветке.**

- Ветка: `feat/database-migrations`.
- Commit реализации: `9502a875c3d46124d4cb39a768c8cc1f7e9f38ef`.
- База ветки: `1cca558`, опубликованный этап 01. Этап 01 ещё не объединён
  с main, поэтому этап 02 продолжен зависимой веткой; main не менялась.
- После явного разрешения пользователя ветка `feat/database-migrations`
  опубликована в `https://github.com/Vaiforo/slotbook`. Первоначальная блокировка
  автоматической проверки снята разрешением; push выполнен успешно.
- PR и merge не выполнены; подготовлен `docs/pr-database-migrations.md`.

Созданы Compose с PostgreSQL 18 и persistent volume, SQLAlchemy-модели пяти
таблиц, фабрика отдельных AsyncSession, миграция `768bb00f10e5`, seed.
Ограничения БД: FK/NOT NULL, статусы, 30-минутная длительность, запрет пересечений
всех слотов одного специалиста, единственная confirmed-запись на слот,
согласованность cancellation timestamp, уникальные хеши токенов.
Даты — timestamptz; timezone хранится отдельно как `Asia/Omsk`.

Seed использует advisory lock и стабильные идентификаторы, создаёт четыре
будущих слота на завтра по Омску. Повтор в тот же день не дублирует данные;
следующий день добавляет новую дату без удаления истории. Владелец синтетический,
вход отключён до этапа 07; фиктивных booking/read API нет.

Фактические проверки:

| Команда | Результат |
|---|---|
| `make install` | uv sync --frozen и npm ci прошли |
| `docker compose up -d --wait db` | PostgreSQL **18.6**, healthy |
| `make migrate` | upgrade head на пустой dev-БД прошёл |
| `make seed` дважды | 1 user, 1 specialist, 4 slots, подтверждено SQL-запросом |
| `make db-test` | **8 passed** на настоящем PostgreSQL |
| `make check` | Ruff/format, mypy, 3 backend smoke/unit, ESLint, tsc, Vite build прошли |
| `git diff --check` | Прошёл |

8 интеграционных проверок включают upgrade → downgrade → upgrade и alembic check
в отдельной случайной `slotbook_test_<uuid>` БД, пересечения/соседние интервалы/
разных специалистов, частичный UNIQUE и сохранение отменённой истории,
CHECK/FK/NOT NULL, повторный seed и будущие даты, async isolation/rollback.
Одноразовая БД после тестов удалена. Dev-БД не откатывалась и содержит demo.
В `make check` эти 8 тестов намеренно skipped без тестового URL; их успешный
прогон отдельно выполнен через `make db-test`.

Исправления при проверке: форматирование миграции и длинных SQL-условий;
предупреждение Alembic path_separator; ожидание теста невалидного booking status
(он нарушает сразу два CHECK, PostgreSQL первым сообщает cancellation consistency).
Ограничения БД ради теста не ослаблялись.

Браузерные проверки заново не запускались: frontend не изменялся. Readiness,
HTTP read API, операции бронирования, production-контейнеры приложения и CI
не реализованы. `interview-tracker` и `sources/` не менялись. Этап 03 не начат.

Следующее действие: интегрировать зависимые этапы через review/PR. Переход к этапу 03 — по отдельному запросу.


## Этап 03 — публичный read API и общий контракт

Дата: **26 октября 2026, Asia/Omsk**. Реализован, проверен и опубликован в feature-ветке.

- Ветка: `feat/read-api-contract`.
- Commit реализации: `745d2a5d8bb6389a24f5ff5227b076d04acb5a2d`.
- База: `548453a`, опубликованный этап 02. Этапы 01–02 ещё не интегрированы
  в main, поэтому используется зависимая ветка. Main не изменена.
- После явного разрешения пользователя ветка `feat/read-api-contract` опубликована
  в `https://github.com/Vaiforo/slotbook`. Push выполнен успешно.
  PR/merge не выполнены; main не изменена. Подготовлен `docs/pr-read-api-contract.md`.

Реализованы `GET /api/v1/specialists/{slug}` и `GET /api/v1/specialists/{slug}/slots`.
Публичные DTO содержат только разрешённые поля. Слоты выбираются по специалисту,
open, будущему starts_at относительно PostgreSQL now(), отсутствию confirmed booking.
Параметры from/to требуют timezone, диапазон [from,to) не больше 31 дня;
limit 1–100 и offset 0–10000, стабильная сортировка. Неизвестный специалист — 404,
некорректные параметры — 422, пустая выборка — 200 с items: [].

Добавлены единый формат ошибок, X-Request-ID и HTTP-логи с шаблоном маршрута,
статусом и длительностью; без query strings, контактов, токенов и текста внутренних
исключений. Async engine/session factory теперь принадлежат конкретному app lifespan
и закрываются при shutdown; импорт/генерация OpenAPI не подключаются к БД.

Сохранены docs/openapi.json, генерируемые api-types.ts, общий fetch client,
типизированные HTTP-ошибки, AbortSignal, same-origin credentials и query keys.
Автоматических retries нет. Health-страница переведена на общий клиент.
Команды api-generate/api-check воспроизводят контракт и обнаруживают drift.
`docs/api-contract.md` описывает реализованное и отдельно будущие операции;
фиктивных booking/auth handlers нет. Существующие миграции не изменялись.

Фактические проверки:

| Проверка | Результат |
|---|---|
| `make install` | uv sync --frozen и npm ci прошли |
| `SLOTBOOK_TEST_ADMIN_URL=<local PostgreSQL URL> make check` | **24 backend passed**, Ruff/format, mypy, ESLint, tsc, Vite build, api-check прошли |
| Vitest (в make check) | **7 passed**: ошибки, credentials, signal, encoding, CSRF, 204, query keys |
| PostgreSQL integration (в общем прогоне) | **19 passed**, включая 8 проверок этапа 02 и 11 read API |
| `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium make smoke` | **2 passed**, настоящий API через Vite и восстановление после ошибки |
| Запущенный Uvicorn на loopback :8011 | Профиль 200, будущие seed-слоты 200, неверный запрос 422; request_id совпадает в теле и заголовке |
| Экспорт с невалидным URL БД | Прошёл без engine/lifespan и DB connection |
| Намеренно изменённые OpenAPI/TS | Оба drift-check завершились с ошибкой; исходные файлы восстановлены |
| `git diff --check` | Прошёл |

Проверены границы ровно 31 день и превышение на микросекунду, from включительно/
to исключительно, UTC и +06:00, timezone-less даты, missing/лишние параметры,
пагинация, пустой результат, закрытые/прошедшие/занятые слоты, отменённые записи,
разные специалисты, отсутствие приватных полей, безопасные 404/405/422/500,
уникальный request_id и безопасные логи. Тесты используют отдельные случайные БД,
которые удаляются после прогона; dev-БД не откатывалась. Seed обновлён явной командой.

Во время проверки исправлены типизация SQLAlchemy scalar result и форматирование.
Проверка TS drift использует программный API openapi-typescript без дочернего Node
процесса (его запуск был ограничен sandbox). Финальные проверки прошли.

Публичный экран расписания (этап 04), booking/auth, readiness, CI/deployment не
реализованы. Frontend layout не менялся. `interview-tracker` и `sources/` не менялись.
Следующий этап по отдельному запросу — 04; до интеграции учитывать зависимость веток.
