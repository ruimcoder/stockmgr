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
if [[ "$plan_reserved" != "true" ]]; then
  echo "App Service plan must be Linux (reserved=true)." >&2
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
if [[ "$webapp_plan_id" != "$plan_id" ]]; then
  echo "Web App is not attached to expected App Service plan." >&2
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
