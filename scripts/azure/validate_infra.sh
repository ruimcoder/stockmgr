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

require_cmd az

require_var AZURE_RESOURCE_GROUP
require_var AZURE_WEBAPP_NAME
require_var AZURE_APPSERVICE_PLAN

if [[ -n "${AZURE_SUBSCRIPTION_ID:-}" ]]; then
  az account set --subscription "$AZURE_SUBSCRIPTION_ID"
fi

plan_rg="${AZURE_APPSERVICE_PLAN_RESOURCE_GROUP:-$AZURE_RESOURCE_GROUP}"

echo "Validating resource group..."
az group show --name "$AZURE_RESOURCE_GROUP" --query "id" --output tsv >/dev/null

echo "Validating App Service plan..."
plan_id="$(
  az appservice plan show \
    --name "$AZURE_APPSERVICE_PLAN" \
    --resource-group "$plan_rg" \
    --query "id" \
    --output tsv
)"
plan_reserved="$(
  az appservice plan show \
    --name "$AZURE_APPSERVICE_PLAN" \
    --resource-group "$plan_rg" \
    --query "reserved" \
    --output tsv
)"
plan_kind="$(
  az appservice plan show \
    --name "$AZURE_APPSERVICE_PLAN" \
    --resource-group "$plan_rg" \
    --query "kind" \
    --output tsv
)"
plan_reserved_normalized="${plan_reserved,,}"
plan_kind_normalized="${plan_kind,,}"
if [[ "$plan_reserved_normalized" != "true" && "$plan_kind_normalized" != *linux* ]]; then
  echo "App Service plan '$AZURE_APPSERVICE_PLAN' is not Linux." >&2
  echo "Current plan details: reserved=$plan_reserved (normalized=$plan_reserved_normalized) kind=${plan_kind:-<unknown>}." >&2
  echo "Create/use a Linux plan (az appservice plan create --is-linux ...) and update AZURE_APPSERVICE_PLAN." >&2
  exit 1
fi

echo "Validating Web App..."
webapp_plan_id="$(
  az webapp show \
    --name "$AZURE_WEBAPP_NAME" \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --query "serverFarmId" \
    --output tsv
)"
webapp_kind="$(
  az webapp show \
    --name "$AZURE_WEBAPP_NAME" \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --query "kind" \
    --output tsv
)"
plan_id_normalized="${plan_id,,}"
webapp_plan_id_normalized="${webapp_plan_id,,}"
if [[ "$webapp_plan_id_normalized" != "$plan_id_normalized" ]]; then
  echo "Web App is not attached to expected App Service plan." >&2
  echo "Expected plan id: $plan_id" >&2
  echo "Web app plan id: $webapp_plan_id" >&2
  exit 1
fi
if [[ "${webapp_kind,,}" != *linux* ]]; then
  echo "Web App '$AZURE_WEBAPP_NAME' is not Linux-capable (kind=${webapp_kind:-<unknown>})." >&2
  echo "Use a Linux Web App for container deployment and update AZURE_WEBAPP_NAME." >&2
  exit 1
fi

webapp_url="https://$(
  az webapp show \
    --name "$AZURE_WEBAPP_NAME" \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --query "defaultHostName" \
    --output tsv
)"
echo "Infrastructure validation passed for: $webapp_url"

if [[ -n "${OUTPUT_ENV_FILE:-}" ]]; then
  echo "AZURE_WEBAPP_URL=$webapp_url" >>"$OUTPUT_ENV_FILE"
fi
