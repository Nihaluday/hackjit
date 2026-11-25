#!/usr/bin/env bash
set -euo pipefail
BASE="${BASE_URL:-http://127.0.0.1:8080}"

curl -fsS "$BASE/api/health" >/dev/null
curl -fsS "$BASE/api/dashboard" >/dev/null
curl -fsS "$BASE/api/resources" >/dev/null
curl -fsS "$BASE/api/resources/cl" >/dev/null
curl -fsS "$BASE/api/dependencies" >/dev/null
curl -fsS "$BASE/api/incidents" >/dev/null
curl -fsS "$BASE/api/simulations" >/dev/null
curl -fsS "$BASE/api/analytics" >/dev/null

LOGIN=$(curl -fsS -X POST "$BASE/api/login" \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}')
TOKEN=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])' <<<"$LOGIN")

curl -fsS -X POST "$BASE/api/incidents" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"resource_id":"cl","type":"Power failure","severity":"Critical","duration":3,"description":"Computer Lab power failure test"}' >/tmp/omnisx-incident.json

SIM=$(curl -fsS -X POST "$BASE/api/simulations" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"resource_id":"cl","type":"Power failure","severity":"Critical","duration":3}')
echo "$SIM" >/tmp/omnisx-simulation.json

INCIDENT_ID=$(python3 -c 'import json; print(json.load(open("/tmp/omnisx-incident.json"))["id"])')
SIMULATION_ID=$(python3 -c 'import json; print(json.load(open("/tmp/omnisx-simulation.json"))["id"])')

curl -fsS "$BASE/api/recovery/$SIMULATION_ID" >/dev/null
curl -fsS -X PATCH "$BASE/api/incidents/$INCIDENT_ID/resolve" \
  -H "Authorization: Bearer $TOKEN" >/dev/null

echo "OMNIS-X API workflow passed"
