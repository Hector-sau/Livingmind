#!/usr/bin/env bash
# T1 verification: build the backend image, run the test suite inside it, start the API
# and prove the rest loop still works from the host.
#
# Run it on a machine with Docker Desktop (the Mac):
#     ./scripts/verify-t1.sh
# Only re-check the HTTP smoke against an already running backend:
#     SKIP_DOCKER=1 ./scripts/verify-t1.sh
#
# Everything is echoed and also written to dist/t1-verify.log (git-ignored).
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"
mkdir -p dist
LOG="$REPO/dist/t1-verify.log"
: > "$LOG"
exec > >(tee -a "$LOG") 2>&1

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
SKIP_DOCKER="${SKIP_DOCKER:-0}"
CTX='{"accountId":"demo-account","personId":"person-lin","spaceId":"space-home-bedroom"}'

step() { printf '\n=== %s ===\n' "$1"; }
fail() { printf '\nFAILED: %s\n' "$1"; exit 1; }
# Minimal JSON field reader: enough for these fixed demo responses, no jq needed.
field() { grep -o "\"$1\":\"[^\"]*\"" | head -1 | cut -d'"' -f4; }
num() { grep -o "\"$1\":[0-9.]*" | head -1 | cut -d: -f2; }

step "versions"
date
if [ "$SKIP_DOCKER" != "1" ]; then
  docker --version
  docker compose version
fi

if [ "$SKIP_DOCKER" != "1" ]; then
  step "compose config"
  docker compose config >/dev/null && echo "compose file is valid"

  step "build image"
  docker compose build api

  step "backend tests inside the container"
  docker compose run --rm --no-deps api pytest -q

  step "start api"
  docker compose up -d api
  for i in $(seq 1 30); do
    state="$(docker inspect --format '{{.State.Health.Status}}' "$(docker compose ps -q api)" 2>/dev/null || echo starting)"
    [ "$state" = "healthy" ] && break
    sleep 2
  done
  echo "health status: ${state:-unknown}"
  [ "${state:-}" = "healthy" ] || fail "container never became healthy (docker compose logs api)"

  step "image facts"
  docker image inspect livingmind-api:dev --format 'size: {{.Size}} bytes'
  echo -n "runs as user: "; docker compose run --rm --no-deps --entrypoint id api -un
  echo -n "secrets in image (expect none): "
  docker compose run --rm --no-deps --entrypoint sh api -c 'ls -a /app | grep -c "^\.env" || true'
fi

step "health from the host"
curl -fsS "$BASE_URL/health"; echo

step "rest loop through the API"
curl -fsS "$BASE_URL/api/demo/reset?accountId=demo-account" -X POST >/dev/null
before="$(curl -fsS "$BASE_URL/api/spaces/space-home-bedroom/devices?accountId=demo-account")"
echo "devices before: $(echo "$before" | num lightBrightness)% light"

plan="$(curl -fsS "$BASE_URL/api/plans/rest" -H 'content-type: application/json' \
  -d "{\"context\":$CTX,\"utterance\":\"我想休息\"}")"
plan_id="$(echo "$plan" | field planId)"
[ -n "$plan_id" ] || fail "no plan returned: $plan"
echo "plan: $plan_id"

mid="$(curl -fsS "$BASE_URL/api/spaces/space-home-bedroom/devices?accountId=demo-account" | num lightBrightness)"
[ "$mid" = "$(echo "$before" | num lightBrightness)" ] || fail "devices changed before confirmation"
echo "devices unchanged before confirmation: ok"

confirm="$(curl -fsS "$BASE_URL/api/plans/$plan_id/confirm" -H 'content-type: application/json' \
  -d "{\"context\":$CTX,\"planVersion\":1}")"
service_id="$(echo "$confirm" | field serviceId)"
[ -n "$service_id" ] || fail "no service started: $confirm"
after="$(curl -fsS "$BASE_URL/api/spaces/space-home-bedroom/devices?accountId=demo-account")"
light="$(echo "$after" | num lightBrightness)"
[ "$light" = "15" ] || fail "expected 林悦's 15% light after confirmation, got $light"
echo "service $service_id started; light now ${light}%"

curl -fsS "$BASE_URL/api/services/$service_id/stop" -H 'content-type: application/json' \
  -d "{\"context\":$CTX}" >/dev/null
echo "service stopped"
curl -fsS "$BASE_URL/api/demo/reset?accountId=demo-account" -X POST >/dev/null
echo "demo data reset"

if [ "$SKIP_DOCKER" != "1" ]; then
  step "stop"
  docker compose down
fi

step "result"
echo "T1 verification passed. Log: dist/t1-verify.log"
