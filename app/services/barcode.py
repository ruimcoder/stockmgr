from __future__ import annotations

import html
import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urljoin

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
        if provider == "continente_pt":
            return await self._lookup_continente(provider_cfg, barcode, timeout, user_agent)
        return None

    async def _fetch_text(self, url: str, *, timeout: float, user_agent: str) -> str:
        async with httpx.AsyncClient(timeout=timeout, headers={"User-Agent": user_agent}) as client:
            response = await client.get(url)
        response.raise_for_status()
        return response.text

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

    async def _lookup_continente(
        self,
        provider_cfg: dict[str, Any],
        barcode: str,
        timeout: float,
        user_agent: str,
    ) -> dict[str, Any] | None:
        base_url = provider_cfg["request"]["baseUrl"].rstrip("/")
        search_url = f"{base_url}/pesquisa/?q={quote_plus(barcode)}"
        search_html = await self._fetch_text(search_url, timeout=timeout, user_agent=user_agent)
        product_url = self._extract_continente_product_url(search_html)
        if not product_url:
            return None
        product_url = urljoin(f"{base_url}/", product_url)
        product_html = await self._fetch_text(product_url, timeout=timeout, user_agent=user_agent)
        return self._parse_continente_product_page(
            product_html=product_html,
            barcode=barcode,
            product_url=product_url,
        )

    def _extract_continente_product_url(self, search_html: str) -> str | None:
        # Search results render product cards with `ct-pdp-link` wrappers around anchors.
        card_link_match = re.search(
            r"<div[^>]*ct-pdp-link[^>]*>\s*<a[^>]*href=\"([^\"]+)\"",
            search_html,
            re.IGNORECASE,
        )
        if card_link_match:
            return html.unescape(card_link_match.group(1).strip())

        fallback_match = re.search(
            r"href=\"([^\"]*?/produto/[^\"]+?\.html)\"",
            search_html,
            re.IGNORECASE,
        )
        if not fallback_match:
            return None
        return html.unescape(fallback_match.group(1).strip())

    def _parse_continente_product_page(
        self,
        *,
        product_html: str,
        barcode: str,
        product_url: str,
    ) -> dict[str, Any] | None:
        product_json = self._extract_continente_product_json_ld(product_html)
        if not product_json:
            return None

        name = self._safe_text(product_json.get("name"))
        if not name:
            return None
        brand = self._safe_text(self._extract_continente_brand(product_json, product_html))
        category = self._safe_text(self._extract_continente_category(product_html))
        size = self._safe_text(self._extract_continente_size(product_html))
        image_url = self._safe_text(self._extract_continente_image(product_json))
        description = self._safe_text(product_json.get("description"))

        return {
            "barcode": barcode,
            "name": name,
            "brand": brand,
            "category": category,
            "imageUrl": image_url,
            "size": size,
            "ingredients": description,
            "sourceUrl": product_url,
            "_countryMatchPT": True,
        }

    def _extract_continente_product_json_ld(self, page_html: str) -> dict[str, Any] | None:
        script_matches = re.finditer(
            r"<script\s+type=\"application/ld\+json\">(.*?)</script>",
            page_html,
            re.IGNORECASE | re.DOTALL,
        )
        for match in script_matches:
            raw_payload = match.group(1).strip()
            if not raw_payload:
                continue
            try:
                payload = json.loads(raw_payload)
            except json.JSONDecodeError:
                continue
            product = self._resolve_json_ld_product(payload)
            if product:
                return product
        return None

    def _resolve_json_ld_product(self, payload: Any) -> dict[str, Any] | None:
        if isinstance(payload, dict):
            payload_type = str(payload.get("@type", "")).lower()
            if payload_type == "product":
                return payload
            graph = payload.get("@graph")
            if isinstance(graph, list):
                for item in graph:
                    resolved = self._resolve_json_ld_product(item)
                    if resolved:
                        return resolved
        if isinstance(payload, list):
            for item in payload:
                resolved = self._resolve_json_ld_product(item)
                if resolved:
                    return resolved
        return None

    def _extract_continente_image(self, product_json: dict[str, Any]) -> str | None:
        image_value = product_json.get("image")
        if isinstance(image_value, str):
            return image_value
        if isinstance(image_value, list):
            for item in image_value:
                if isinstance(item, str) and item.strip():
                    return item
        return None

    def _extract_continente_brand(
        self,
        product_json: dict[str, Any],
        product_html: str,
    ) -> str | None:
        brand_value = product_json.get("brand")
        if isinstance(brand_value, dict):
            brand_name = brand_value.get("name")
            if isinstance(brand_name, str) and brand_name.strip():
                return brand_name
        if isinstance(brand_value, str) and brand_value.strip():
            return brand_value

        data_layer_match = re.search(
            r'"brand&quot;:&quot;([^"]+?)&quot;',
            product_html,
            re.IGNORECASE,
        )
        if data_layer_match:
            return html.unescape(data_layer_match.group(1))
        return None

    def _extract_continente_category(self, product_html: str) -> str | None:
        for key in ("item_category3", "item_category2", "item_category"):
            category_match = re.search(
                rf'"{key}&quot;:&quot;([^"]+?)&quot;',
                product_html,
                re.IGNORECASE,
            )
            if category_match:
                return html.unescape(category_match.group(1))
        return None

    def _extract_continente_size(self, product_html: str) -> str | None:
        meta_match = re.search(
            r'<meta\s+name="description"\s+content="([^"]+)"',
            product_html,
            re.IGNORECASE,
        )
        if not meta_match:
            return None
        description = html.unescape(meta_match.group(1))
        size_match = re.search(
            r"\b\d+(?:[.,]\d+)?\s?(?:kg|g|mg|l|ml|cl|un)\b",
            description,
            re.IGNORECASE,
        )
        if not size_match:
            return None
        return size_match.group(0)

    def _safe_text(self, value: Any) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None
