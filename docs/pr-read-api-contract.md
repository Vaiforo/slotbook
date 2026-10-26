# feat: add public read API and generated frontend contract

Этап 03. API возвращает публичный профиль и только будущие открытые слоты без
confirmed-записи. Диапазон from/to требует timezone и ограничен 31 днём;
есть стабильная сортировка и ограниченная пагинация. Публичные DTO не раскрывают
контакты, хеши и данные записей.

Добавлены единый error envelope, X-Request-ID и безопасные HTTP-логи.
Engine/session factory принадлежат lifespan конкретного приложения, поэтому
экспорт OpenAPI не подключается к БД. OpenAPI и TypeScript сохраняются в Git;
make api-check выявляет расхождение обоих артефактов без перезаписи.
Frontend получает общий fetch-клиент, сгенерированные типы и query keys.
Документ api-contract.md отдельно описывает будущие операции без фиктивных handlers.

Проверено: 24 backend tests на PostgreSQL 18 (19 integration + 5 unit/smoke),
7 Vitest tests, 2 Chromium smoke tests; Ruff, mypy, ESLint, tsc, Vite build;
uv sync --frozen / npm ci; намеренно внесённый drift в OpenAPI и TS отклоняется.
Запущенный Uvicorn вернул profile/slots 200 и безопасный validation 422.

Ветка feat/read-api-contract основана на feat/database-migrations (548453a);
этапы ещё не интегрированы в main. Для diff только этапа 03 база — ветка этапа 02.
Публичный UI, booking/auth endpoints, readiness и production deployment
не входят в изменения. PR/merge не выполнены.
