#!/usr/bin/env bash
# Disposable stack; never uses the normal production volume or environment file.
set -euo pipefail
cd "$(dirname "$0")/.."
export RABBITMQ_PASSWORD="broker-check-$$"
export SLOTBOOK_EMAIL_URL=http://mail-provider:8001/messages
export SLOTBOOK_EMAIL_API_KEY=''
export SLOTBOOK_AI_MODEL='' SLOTBOOK_AI_API_KEY=''
export SLOTBOOK_NOTIFICATION_MAX_ATTEMPTS=5
export POSTGRES_PASSWORD="container-test-$(date +%s)-$$"
export SLOTBOOK_DATABASE_URL="postgresql+psycopg://slotbook:${POSTGRES_PASSWORD}@db:5432/slotbook"
export SLOTBOOK_PUBLIC_ORIGIN=https://slotbook.example.invalid
export SLOTBOOK_REDIS_URL=redis://redis:6379/0
export SLOTBOOK_LOGIN_LIMIT=10 SLOTBOOK_BOOKING_LIMIT=20 SLOTBOOK_RATE_WINDOW_SECONDS=60
export SLOTBOOK_RATE_PREFIX=slotbook:rate:container-test
export HTTP_PORT=${SLOTBOOK_CHECK_PORT:-18080}
export IMAGE_TAG=check-$$
project="slotbook-check-$$"
compose=(docker compose --env-file /dev/null -p "$project" -f compose.production.yaml)
cleanup() {
  result=$?
  if [ "$result" != 0 ]; then "${compose[@]}" logs --tail=60; fi
  docker rm -f "$project-ip-holder" >/dev/null 2>&1 || true
  "${compose[@]}" down -v --remove-orphans
  exit "$result"
}
trap cleanup EXIT
# Optional CA mount for environments with a managed HTTPS proxy.
if [ -n "${CODEX_PROXY_CERT:-}" ]; then
  docker build --secret id=proxy_ca,src=/etc/ssl/certs/ca-certificates.crt -t "slotbook-api:$IMAGE_TAG" backend
  docker build --secret "id=proxy_ca,src=$CODEX_PROXY_CERT" -t "slotbook-web:$IMAGE_TAG" frontend
else
  "${compose[@]}" build
fi
"${compose[@]}" up -d --wait --wait-timeout 120
base="http://127.0.0.1:$HTTP_PORT"
"${compose[@]}" exec -T api python -m scripts.seed_demo
"${compose[@]}" exec -T api python -m scripts.seed_demo
curl -fsS -H 'Content-Type: application/json' -d '{"text":"завтра"}' "$base/api/v1/specialists/demo/search" | python3 -c 'import json,sys; r=json.load(sys.stdin); assert r["status"]=="unavailable" and r["items"]==[]'
"${compose[@]}" stop redis
python3 scripts/check-redis-outage.py "$base"
"${compose[@]}" up -d --wait redis
"${compose[@]}" stop worker rabbitmq
python3 scripts/demo-api.py --base-url "$base" --book-and-cancel
test "$("${compose[@]}" exec -T db psql -U slotbook -Atc 'SELECT count(*) FROM outbox_events')" = 2
"${compose[@]}" up -d --wait rabbitmq
for attempt in $(seq 1 90); do
  published=$("${compose[@]}" exec -T db psql -U slotbook -Atc 'SELECT count(*) FROM outbox_events WHERE published_at IS NOT NULL')
  [ "$published" = 2 ] && break
  sleep 1
done
test "$published" = 2
# Messages must survive a broker restart while the consumer remains stopped.
"${compose[@]}" restart rabbitmq
"${compose[@]}" up -d --wait rabbitmq
"${compose[@]}" up -d worker
for attempt in $(seq 1 90); do
  delivered=$("${compose[@]}" exec -T db psql -U slotbook -Atc "SELECT count(*) FROM notification_deliveries WHERE status='sent'")
  [ "$delivered" = 2 ] && break
  sleep 1
done
test "$delivered" = 2
"${compose[@]}" exec -T worker python -c 'from app.notifications.queue import celery; from app.core.config import Settings; from sqlalchemy import create_engine,text; e=create_engine(Settings().database_url); c=e.connect(); ids=c.execute(text("SELECT id FROM outbox_events")).scalars().all(); [celery.send_task("slotbook.deliver", args=[str(i)], retry=False) for i in ids]; c.close(); e.dispose()'
# Provider receipt identifiers are unique; no contacts are retained.
"${compose[@]}" exec -T mail-provider python -c 'import sqlite3; db=sqlite3.connect("/data/receipts.sqlite"); assert db.execute("SELECT count(*) FROM receipts").fetchone()[0] == 2'
echo 'Broker outage, durable queue restart and notification delivery passed.'
# Restore a synthetic dump into a separate database; never replace the source.
"${compose[@]}" exec -T db createdb -U slotbook slotbook_restore_check
"${compose[@]}" exec -T db pg_dump -U slotbook -Fc slotbook | \
  "${compose[@]}" exec -T db pg_restore -U slotbook --exit-on-error -d slotbook_restore_check
test "$("${compose[@]}" exec -T db psql -U slotbook -d slotbook_restore_check -Atc "SELECT count(*) FROM bookings WHERE status='cancelled'")" = 1
test "$("${compose[@]}" exec -T db psql -U slotbook -d slotbook_restore_check -Atc 'SELECT count(*) FROM slots')" = 4
"${compose[@]}" exec -T db dropdb -U slotbook slotbook_restore_check
echo 'Synthetic backup restoration passed.'
for path in / /dashboard /manage/00000000-0000-0000-0000-000000000000; do
  curl -fsS "$base$path" | grep -q '<div id="root">'
done
curl -fsS "$base/docs" | grep -q swagger
curl -fsS "$base/openapi.json" | python3 -c 'import json,sys; assert "/health/ready" in json.load(sys.stdin)["paths"]'
for path in /api /api/missing /api/v1/missing; do
  test "$(curl -sS -o /tmp/slotbook-response-$$ -w '%{http_code}' "$base$path")" = 404
  python3 -c 'import json,sys; assert json.load(open(sys.argv[1]))["error"]["code"] == "not_found"' /tmp/slotbook-response-$$
done
rm /tmp/slotbook-response-$$
# Database ports must have no host bindings.
docker inspect "$("${compose[@]}" ps -q db)" | python3 -c 'import json,sys; assert not any(json.load(sys.stdin)[0]["NetworkSettings"]["Ports"].values())'
node frontend/scripts/check-production.mjs "$base"
python3 scripts/check-proxy-error.py "$base/api/v1/slots" 413 payload_too_large
for path in /api/v1/auth/login /api/v1/bookings; do
  for attempt in $(seq 1 12); do
    code=$(curl -sS -X POST -o /dev/null -w '%{http_code}' "$base$path")
  done
  test "$code" = 429
  python3 scripts/check-proxy-error.py "$base$path" 429 rate_limited
done
# Force a different API address, as can happen during deployment/recovery.
old_ip=$(docker inspect --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$("${compose[@]}" ps -q api)")
"${compose[@]}" rm -s -f api
python3 scripts/check-proxy-error.py "$base/api/v1/slots" 503 service_unavailable
docker run -d --name "$project-ip-holder" --network "${project}_default" \
  --entrypoint python "slotbook-api:$IMAGE_TAG" -c 'import time; time.sleep(120)' >/dev/null
"${compose[@]}" up -d --no-deps --wait --wait-timeout 60 api
new_ip=$(docker inspect --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$("${compose[@]}" ps -q api)")
test "$new_ip" != "$old_ip"
recovered=false
for attempt in $(seq 1 15); do
  if curl -fsS --max-time 6 "$base/health/ready" >/dev/null; then
    recovered=true
    break
  fi
  sleep 2
done
if [ "$recovered" != true ]; then
  echo 'Proxy did not recover after the API address changed' >&2
  exit 1
fi
docker rm -f "$project-ip-holder" >/dev/null
# Recover the DB connection pool without restarting the API.
"${compose[@]}" stop db
test "$(curl -s --max-time 6 -o /dev/null -w '%{http_code}' "$base/health/ready")" = 503
curl -fsS "$base/health/live"
"${compose[@]}" up -d --wait db
curl -fsS "$base/health/ready"
# A running DB with an incorrect migration must not be ready.
"${compose[@]}" exec -T db psql -U slotbook -c "UPDATE alembic_version SET version_num='wrong'"
test "$(curl -s -o /dev/null -w '%{http_code}' "$base/health/ready")" = 503
"${compose[@]}" exec -T db psql -U slotbook -c 'DROP TABLE alembic_version'
test "$(curl -s -o /dev/null -w '%{http_code}' "$base/health/ready")" = 503
"${compose[@]}" stop db
test "$(curl -s -o /dev/null -w '%{http_code}' "$base/health/ready")" = 503
curl -fsS "$base/health/live"
# Bundle must not contain the runtime password or backend configuration.
"${compose[@]}" exec -T nginx sh -c '! grep -R -E "postgresql|SLOTBOOK_DATABASE_URL" /usr/share/nginx/html'
echo 'Production routing, readiness, isolation and bundle checks passed.'
