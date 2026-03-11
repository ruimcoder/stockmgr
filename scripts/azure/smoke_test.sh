#!/usr/bin/env bash
set -euo pipefail

require_var() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "Missing required variable: $name" >&2
    exit 1
  fi
}

require_cmd() {
  local name="$1"
  if ! command -v "$name" >/dev/null 2>&1; then
    echo "Missing required command: $name" >&2
    exit 1
  fi
}

require_cmd curl

require_var AZURE_WEBAPP_URL

health_path="${HEALTH_PATH:-/health}"
manifest_path="${MANIFEST_PATH:-/manifest.webmanifest}"
attempts="${SMOKE_ATTEMPTS:-30}"
sleep_seconds="${SMOKE_SLEEP_SECONDS:-10}"

echo "Running smoke tests against $AZURE_WEBAPP_URL"

health_ok="false"
for attempt in $(seq 1 "$attempts"); do
  health_body="$(curl -fsS --max-time 20 "${AZURE_WEBAPP_URL}${health_path}" || true)"
  if [[ "$health_body" == *"\"status\":\"ok\""* ]]; then
    health_ok="true"
    break
  fi
  echo "Health check attempt $attempt/$attempts failed; retrying in ${sleep_seconds}s..."
  sleep "$sleep_seconds"
done

if [[ "$health_ok" != "true" ]]; then
  echo "Health check failed after $attempts attempts." >&2
  exit 1
fi

manifest_code="$(
  curl -sS -o /dev/null -w "%{http_code}" "${AZURE_WEBAPP_URL}${manifest_path}"
)"
if [[ "$manifest_code" != "200" ]]; then
  echo "Manifest smoke check failed with HTTP $manifest_code" >&2
  exit 1
fi

excel_code="$(
  curl -sS -o /dev/null -w "%{http_code}" "${AZURE_WEBAPP_URL}/api/excel/stocks"
)"
if [[ "$excel_code" != "401" && "$excel_code" != "503" ]]; then
  echo "Excel API smoke check failed with HTTP $excel_code" >&2
  exit 1
fi

echo "Smoke tests passed."
