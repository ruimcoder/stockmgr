from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx
from jsonschema import validate

from app.config import Settings
from app.schemas import BarcodeLookupResult, ProviderAttempt


class BarcodeLookupService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.root = Path(__file__).resolve().parents[2]
        self._config: dict[str, Any] = self._load_provider_config()

    @property
    def config(self) -> dict[str, Any]:
        return self._config

    def _load_provider_config(self) -> dict[str, Any]:
        schema_path = self.root / self.settings.provider_schema_path
        config_path = self.root / self.settings.provider_config_path
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        config = json.loads(config_path.read_text(encoding="utf-8"))
        validate(instance=config, schema=schema)
        return config

    def _chain_for_item_type(self, item_type: str) -> list[str]:
        normalized = item_type.lower().strip()
        if normalized in {"food", "pantry"}:
            key = "food"
        elif normalized in {"medical", "medicine", "drug"}:
            key = "medical"
        elif normalized in {"nonfood", "non_food", "household"}:
            key = "nonFood"
        else:
            key = "unknown"
        return self._config["lookup"]["chains"][key]

    def _is_sufficient(self, payload: dict[str, Any]) -> bool:
        rules = self._config["lookup"]["sufficiency"]
        required = rules["requiredFields"]
        minimum = rules["minimumFieldMatch"]
        hits = sum(1 for field in required if payload.get(field))
        return hits >= minimum

    async def lookup(self, barcode: str, item_type: str = "unknown") -> BarcodeLookupResult:
        attempts: list[ProviderAttempt] = []
        best_payload: dict[str, Any] | None = None
        best_provider: str | None = None
        best_score = -1

        for provider in self._chain_for_item_type(item_type):
            provider_cfg = self._config["providers"].get(provider)
            if provider_cfg is None:
                attempts.append(
                    ProviderAttempt(
                        provider=provider, status="skipped", message="Provider is undefined."
                    )
                )
                continue
            if not provider_cfg.get("enabled", False):
                attempts.append(
                    ProviderAttempt(
                        provider=provider, status="skipped", message="Provider is disabled."
                    )
                )
                continue

            api_key = self._get_api_key(provider_cfg)
            if (
                provider_cfg["kind"] in {"commercial", "enterprise"}
                and provider != "upcitemdb"
                and not api_key
            ):
                attempts.append(
                    ProviderAttempt(
                        provider=provider,
                        status="skipped",
                        message="Missing required API key environment variable.",
                    )
                )
                continue

            try:
                payload = await self._lookup_with_provider(provider, provider_cfg, barcode, api_key)
            except Exception as exc:
                attempts.append(
                    ProviderAttempt(provider=provider, status="error", message=str(exc))
                )
                continue

            if not payload:
                attempts.append(
                    ProviderAttempt(provider=provider, status="not_found", message=None)
                )
                continue

            attempts.append(ProviderAttempt(provider=provider, status="success", message=None))
            score = self._score_payload(payload, provider_cfg)
            if score > best_score:
                best_score = score
                best_payload = payload
                best_provider = provider
            if (
                self._is_sufficient(payload)
                and self._config["lookup"]["sufficiency"]["stopOnFirstSufficientMatch"]
            ):
                return BarcodeLookupResult(
                    found=True,
                    provider=provider,
                    data=payload,
                    attempts=attempts,
                )

        if best_payload and best_provider:
            return BarcodeLookupResult(
                found=True,
                provider=best_provider,
                data=best_payload,
                attempts=attempts,
            )
        return BarcodeLookupResult(found=False, provider=None, data=None, attempts=attempts)

    def _get_api_key(self, provider_cfg: dict[str, Any]) -> str | None:
        env_var = provider_cfg.get("credentials", {}).get("apiKeyEnvVar")
        if not env_var:
            return None
        return os.getenv(env_var)

    def _score_payload(self, payload: dict[str, Any], provider_cfg: dict[str, Any]) -> int:
        country_priority = provider_cfg.get("defaultCountryPriority", [])
        country_bonus = 0
        if country_priority and "PT" in country_priority and payload.get("_countryMatchPT"):
            country_bonus = 2
        field_score = sum(
            1 for k in ("name", "brand", "category", "size", "imageUrl") if payload.get(k)
        )
        return field_score + country_bonus

    async def _lookup_with_provider(
        self,
        provider: str,
        provider_cfg: dict[str, Any],
        barcode: str,
        api_key: str | None,
    ) -> dict[str, Any] | None:
        timeout = provider_cfg["request"]["timeoutMs"] / 1000
        user_agent = provider_cfg["request"]["userAgent"]
        if provider == "open_food_facts":
            return await self._lookup_open_food_facts(provider_cfg, barcode, timeout, user_agent)
        if provider == "open_products_facts":
            return await self._lookup_open_products_facts(
                provider_cfg, barcode, timeout, user_agent
            )
        if provider == "openfda_ndc":
            return await self._lookup_openfda(provider_cfg, barcode, timeout, user_agent, api_key)
        if provider == "usda_fooddata_central":
            return await self._lookup_usda(provider_cfg, barcode, timeout, user_agent, api_key)
        if provider == "upcitemdb":
            return await self._lookup_upcitemdb(provider_cfg, barcode, timeout, user_agent, api_key)
        return None

    async def _lookup_open_food_facts(
        self, provider_cfg: dict[str, Any], barcode: str, timeout: float, user_agent: str
    ) -> dict[str, Any] | None:
        url = f"{provider_cfg['request']['baseUrl']}/product/{barcode}.json"
        async with httpx.AsyncClient(timeout=timeout, headers={"User-Agent": user_agent}) as client:
            response = await client.get(url)
        response.raise_for_status()
        body = response.json()
        product = body.get("product")
        if not product:
            return None
        countries = product.get("countries_tags", [])
        return {
            "barcode": barcode,
            "name": product.get("product_name"),
            "brand": product.get("brands"),
            "category": product.get("categories"),
            "imageUrl": product.get("image_url"),
            "size": product.get("quantity"),
            "ingredients": product.get("ingredients_text"),
            "nutrition": product.get("nutriments"),
            "_countryMatchPT": any("portugal" in str(c).lower() for c in countries),
        }

    async def _lookup_open_products_facts(
        self, provider_cfg: dict[str, Any], barcode: str, timeout: float, user_agent: str
    ) -> dict[str, Any] | None:
        url = f"{provider_cfg['request']['baseUrl']}/product/{barcode}.json"
        async with httpx.AsyncClient(timeout=timeout, headers={"User-Agent": user_agent}) as client:
            response = await client.get(url)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        body = response.json()
        product = body.get("product")
        if not product:
            return None
        countries = product.get("countries_tags", [])
        return {
            "barcode": barcode,
            "name": product.get("product_name"),
            "brand": product.get("brands"),
            "category": product.get("categories"),
            "imageUrl": product.get("image_url"),
            "size": product.get("quantity"),
            "ingredients": product.get("ingredients_text"),
            "nutrition": product.get("nutriments"),
            "_countryMatchPT": any("portugal" in str(c).lower() for c in countries),
        }

    async def _lookup_openfda(
        self,
        provider_cfg: dict[str, Any],
        barcode: str,
        timeout: float,
        user_agent: str,
        api_key: str | None,
    ) -> dict[str, Any] | None:
        params: dict[str, str] = {"search": f"upc:{barcode}", "limit": "1"}
        if api_key:
            params["api_key"] = api_key
        async with httpx.AsyncClient(timeout=timeout, headers={"User-Agent": user_agent}) as client:
            response = await client.get(provider_cfg["request"]["baseUrl"], params=params)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        results = response.json().get("results", [])
        if not results:
            return None
        row = results[0]
        return {
            "barcode": barcode,
            "name": row.get("brand_name"),
            "brand": row.get("labeler_name"),
            "category": "medical",
            "size": row.get("dosage_form"),
            "ingredients": row.get("active_ingredients"),
            "_countryMatchPT": False,
        }

    async def _lookup_usda(
        self,
        provider_cfg: dict[str, Any],
        barcode: str,
        timeout: float,
        user_agent: str,
        api_key: str | None,
    ) -> dict[str, Any] | None:
        if not api_key:
            return None
        url = f"{provider_cfg['request']['baseUrl']}/foods/search"
        params = {"query": barcode, "pageSize": "1", "api_key": api_key}
        async with httpx.AsyncClient(timeout=timeout, headers={"User-Agent": user_agent}) as client:
            response = await client.get(url, params=params)
        response.raise_for_status()
        foods = response.json().get("foods", [])
        if not foods:
            return None
        row = foods[0]
        return {
            "barcode": barcode,
            "name": row.get("description"),
            "brand": row.get("brandOwner"),
            "category": "food",
            "size": row.get("servingSize"),
            "ingredients": row.get("ingredients"),
            "_countryMatchPT": False,
        }

    async def _lookup_upcitemdb(
        self,
        provider_cfg: dict[str, Any],
        barcode: str,
        timeout: float,
        user_agent: str,
        api_key: str | None,
    ) -> dict[str, Any] | None:
        base_url = provider_cfg["request"]["baseUrl"]
        url = f"{base_url}/lookup"
        headers = {"User-Agent": user_agent}
        params = {"upc": barcode}
        if api_key:
            headers["user_key"] = api_key
        else:
            url = "https://api.upcitemdb.com/prod/trial/lookup"
        async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
            response = await client.get(url, params=params)
        if response.status_code in {401, 403, 429}:
            return None
        response.raise_for_status()
        items = response.json().get("items", [])
        if not items:
            return None
        row = items[0]
        return {
            "barcode": barcode,
            "name": row.get("title"),
            "brand": row.get("brand"),
            "category": row.get("category"),
            "imageUrl": (row.get("images") or [None])[0],
            "size": row.get("size"),
            "_countryMatchPT": False,
        }
