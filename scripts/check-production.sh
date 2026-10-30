#!/usr/bin/env bash
# Disposable stack; never uses the normal production volume or environment file.
set -euo pipefail
cd "$(dirname "$0")/.."
export POSTGRES_PASSWORD="container-test-$(date +%s)-$$"
export SLOTBOOK_DATABASE_URL="postgresql+psycopg://slotbook:${POSTGRES_PASSWORD}@db:5432/slotbook"
export SLOTBOOK_PUBLIC_ORIGIN=https://slotbook.example.invalid
export HTTP_PORT=${SLOTBOOK_CHECK_PORT:-18080}
export IMAGE_TAG=check-$$
project="slotbook-check-$$"
compose=(docker compose --env-file /dev/null -p "$project" -f compose.production.yaml)
cleanup() {
  result=$?
  if [ "$result" != 0 ]; then "${compose[@]}" logs --tail=60; fi
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
for path in /api/v1/auth/login /api/v1/bookings; do
  for attempt in $(seq 1 12); do
    code=$(curl -sS -X POST -o /dev/null -w '%{http_code}' "$base$path")
  done
  test "$code" = 429
done
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
