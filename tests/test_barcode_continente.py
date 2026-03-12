import asyncio

from app.config import Settings
from app.services.barcode import BarcodeLookupService


def _service() -> BarcodeLookupService:
    return BarcodeLookupService(Settings())


def test_extract_continente_product_url_from_search_result_card():
    service = _service()
    search_html = """
    <div class="ct-pdp-link ">
        <a href="https://www.continente.pt/produto/arroz-agulha-cigala-cigala-2305902.html">
            <h2>Arroz Agulha Cigala</h2>
        </a>
    </div>
    """
    product_url = service._extract_continente_product_url(search_html)
    assert product_url == "https://www.continente.pt/produto/arroz-agulha-cigala-cigala-2305902.html"


def test_lookup_continente_parses_search_and_product_page(monkeypatch):
    service = _service()
    provider_cfg = {
        "request": {
            "baseUrl": "https://www.continente.pt",
            "timeoutMs": 5000,
            "retries": 0,
            "userAgent": "stockmgr-test",
        }
    }
    barcode = "5601234567890"
    search_html = """
    <div class="ct-pdp-link ">
        <a href="/produto/arroz-carolino-malandrinho-pato-real-pato-real-2003662.html">
            <h2>Arroz Carolino Malandrinho Pato Real</h2>
        </a>
    </div>
    """
    product_html = """
    <meta
        name="description"
        content="Comprar Arroz Carolino Malandrinho Pato Real emb. 1 kg no Continente Online."
    />
    <div>"item_category3&quot;:&quot;Arroz&quot;</div>
    <div>"brand&quot;:&quot;Pato Real&quot;</div>
    <script type="application/ld+json">
    {
      "@context": "http://schema.org/",
      "@type": "Product",
      "name": "Arroz Carolino Malandrinho Pato Real",
      "description": "O arroz com a textura mais cremosa.",
      "brand": {"@type": "Thing", "name": "Pato Real"},
      "image": ["https://www.continente.pt/images/arroz.jpg"]
    }
    </script>
    """

    async def fake_fetch_text(url: str, *, timeout: float, user_agent: str) -> str:
        _ = timeout, user_agent
        if "pesquisa/?q=" in url:
            return search_html
        if "/produto/" in url:
            return product_html
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(service, "_fetch_text", fake_fetch_text)

    payload = asyncio.run(
        service._lookup_continente(
            provider_cfg=provider_cfg,
            barcode=barcode,
            timeout=5.0,
            user_agent="stockmgr-test",
        )
    )
    assert payload is not None
    assert payload["barcode"] == barcode
    assert payload["name"] == "Arroz Carolino Malandrinho Pato Real"
    assert payload["brand"] == "Pato Real"
    assert payload["category"] == "Arroz"
    assert payload["size"] == "1 kg"
    assert payload["imageUrl"] == "https://www.continente.pt/images/arroz.jpg"
    assert payload["_countryMatchPT"] is True
    assert payload["sourceUrl"].startswith("https://www.continente.pt/produto/")


def test_lookup_continente_returns_none_when_search_has_no_product_link(monkeypatch):
    service = _service()
    provider_cfg = {
        "request": {
            "baseUrl": "https://www.continente.pt",
            "timeoutMs": 5000,
            "retries": 0,
            "userAgent": "stockmgr-test",
        }
    }

    async def fake_fetch_text(url: str, *, timeout: float, user_agent: str) -> str:
        _ = timeout, user_agent, url
        return "<html><body><p>No results</p></body></html>"

    monkeypatch.setattr(service, "_fetch_text", fake_fetch_text)
    payload = asyncio.run(
        service._lookup_continente(
            provider_cfg=provider_cfg,
            barcode="5600000000000",
            timeout=5.0,
            user_agent="stockmgr-test",
        )
    )
    assert payload is None
