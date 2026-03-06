from app.schemas import BarcodeLookupResult


def test_create_and_list_items(client):
    payload_a = {
        "barcode": "5600000000001",
        "batch_code": "LOT-A",
        "name": "Beans",
        "item_type": "food",
        "storage_location": "Pantry",
        "expiry_date": "2030-01-01",
        "renewal_date": "2029-12-01",
    }
    created = client.post("/api/items", json=payload_a)
    assert created.status_code == 200
    assert created.json()["name"] == "Beans"
    assert created.json()["batch_code"] == "LOT-A"

    payload_b = {
        "barcode": "5600000000001",
        "batch_code": "LOT-B",
        "name": "Beans",
        "item_type": "food",
        "storage_location": "Pantry",
        "expiry_date": "2030-03-01",
    }
    created_b = client.post("/api/items", json=payload_b)
    assert created_b.status_code == 200

    listed = client.get("/api/items")
    assert listed.status_code == 200
    assert len(listed.json()) == 2
    assert listed.json()[0]["storage_location"] == "Pantry"


def test_required_expiry_date_enforced(client):
    payload = {
        "name": "No Expiry Item",
        "item_type": "food",
        "storage_location": "Pantry",
    }
    response = client.post("/api/items", json=payload)
    assert response.status_code == 422


def test_language_switch_endpoint(client):
    response = client.get("/lang/pt", follow_redirects=False)
    assert response.status_code == 303


def test_barcode_lookup_endpoint(client, monkeypatch):
    async def fake_lookup(barcode: str, item_type: str):
        assert barcode == "5601234567890"
        assert item_type == "food"
        return BarcodeLookupResult(
            found=True,
            provider="open_food_facts",
            data={"name": "Canned Tuna", "brand": "Test Brand"},
            attempts=[],
        )

    monkeypatch.setattr("app.main.barcode_service.lookup", fake_lookup)
    response = client.post(
        "/api/barcode-lookup", json={"barcode": "5601234567890", "item_type": "food"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["found"] is True
    assert body["provider"] == "open_food_facts"
    assert body["data"]["name"] == "Canned Tuna"


def test_csv_import_route(client):
    csv_bytes = (
        b"name,item_type,storage_location,batch_code,expiry_date,renewal_date\n"
        b"Sugar,food,Pantry,LOT-55,2031-05-01,2031-04-01\n"
    )
    response = client.post(
        "/items/import",
        files={"file": ("items.csv", csv_bytes, "text/csv")},
    )
    assert response.status_code == 200
    assert "Imported: <strong>1</strong>" in response.text
