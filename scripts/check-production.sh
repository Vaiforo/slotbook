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
python3 scripts/demo-api.py --base-url "$base" --book-and-cancel
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
