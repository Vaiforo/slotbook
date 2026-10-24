# feat: add PostgreSQL schema, migrations and demo seed

Этап 02 добавляет PostgreSQL 18 в Compose, пять SQLAlchemy-моделей, async sessions,
миграцию Alembic и явный транзакционный seed. БД запрещает пересекающиеся слоты,
интервалы не по 30 минут и две confirmed-записи одного слота; отменённая история
сохраняется. Повторный seed создаёт одного специалиста и четыре будущих слота
без дубликатов. Демо-вход отключён до этапа авторизации.

Проверено: PostgreSQL 18.6; make migrate; make seed дважды (1 user / 1 specialist /
4 slots); make db-test (8 passed, включая migration roundtrip и async rollback);
make check (Ruff, mypy, 3 unit/smoke tests, ESLint, tsc, Vite build).
В make check DB-тесты отдельно пропускаются, их успешный результат получен make db-test.

Ветка feat/database-migrations основана на feat/project-foundation (1cca558),
поскольку этап 01 пока не интегрирован в main. Для отдельного diff этапа 02
использовать feat/project-foundation как базу. PR/merge не выполнены.
Read API, booking endpoints, readiness и production deployment не входят в этот этап.
