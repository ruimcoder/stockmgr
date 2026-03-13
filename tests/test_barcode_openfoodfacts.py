import asyncio

from app.config import Settings
from app.services.barcode import BarcodeLookupService


def _service() -> BarcodeLookupService:
    return BarcodeLookupService(Settings())


def _provider_cfg(base_url: str = "https://pt.openfoodfacts.org/api/v2") -> dict:
    return {
        "request": {
            "baseUrl": base_url,
            "timeoutMs": 5000,
            "retries": 1,
            "userAgent": "stockmgr-test",
        }
    }


def _make_off_response(product: dict | None) -> dict:
    if product is None:
        return {"status": 0, "product": None}
    return {"status": 1, "product": product}


def _run_lookup(service: BarcodeLookupService, provider_cfg: dict, barcode: str) -> dict | None:
    async def _inner():
        return await service._lookup_open_food_facts(
            provider_cfg=provider_cfg,
            barcode=barcode,
            timeout=5.0,
            user_agent="stockmgr-test",
        )

    return asyncio.run(_inner())


def test_lookup_off_returns_nutriscore_grade(monkeypatch):
    service = _service()
    barcode = "5601326000122"
    product = {
        "product_name": "Bolo de Arroz",
        "brands": "Panrico",
        "categories": "Bolachas",
        "quantity": "200 g",
        "image_front_url": "https://images.openfoodfacts.org/bolo.jpg",
        "image_url": "https://images.openfoodfacts.org/bolo_old.jpg",
        "nutriscore_grade": "c",
        "nutrition_grade_fr": "c",
        "nutriments": {},
        "countries_tags": ["en:portugal"],
        "ingredients_text": "Farinha de arroz, acucar, ovos.",
    }

    import httpx

    class FakeResponse:
        status_code = 200

        def json(self):
            return _make_off_response(product)

        def raise_for_status(self):
            pass

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    result = _run_lookup(service, _provider_cfg(), barcode)
    assert result is not None
    assert result["barcode"] == barcode
    assert result["name"] == "Bolo de Arroz"
    assert result["brand"] == "Panrico"
    assert result["nutriscore"] == "c"
    # Prefers image_front_url over image_url
    assert result["imageUrl"] == "https://images.openfoodfacts.org/bolo.jpg"
    assert result["_countryMatchPT"] is True


def test_lookup_off_ignores_not_applicable_nutriscore(monkeypatch):
    service = _service()
    barcode = "1234567890123"
    product = {
        "product_name": "Water",
        "brands": "Brand",
        "categories": "Beverages",
        "quantity": "1 l",
        "image_front_url": None,
        "image_url": "https://images.openfoodfacts.org/water.jpg",
        "nutriscore_grade": "not-applicable",
        "nutriments": {},
        "countries_tags": [],
    }

    import httpx

    class FakeResponse:
        status_code = 200

        def json(self):
            return _make_off_response(product)

        def raise_for_status(self):
            pass

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    result = _run_lookup(service, _provider_cfg(), barcode)
    assert result is not None
    assert result["nutriscore"] is None
    # Falls back to image_url when image_front_url is None
    assert result["imageUrl"] == "https://images.openfoodfacts.org/water.jpg"


def test_lookup_off_returns_none_when_product_missing(monkeypatch):
    service = _service()

    import httpx

    class FakeResponse:
        status_code = 200

        def json(self):
            return _make_off_response(None)

        def raise_for_status(self):
            pass

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    result = _run_lookup(service, _provider_cfg(), "0000000000000")
    assert result is None


def test_lookup_off_chain_order():
    """open_food_facts must be first in food, nonFood, and unknown chains."""
    service = _service()
    chains = service.config["lookup"]["chains"]
    assert chains["food"][0] == "open_food_facts"
    assert chains["nonFood"][0] == "open_food_facts"
    assert chains["unknown"][0] == "open_food_facts"
