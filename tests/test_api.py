from app.schemas import BarcodeLookupResult


def test_create_and_list_items(client):
    payload_a = {
        "barcode": "5600000000001",
        "batch_code": "LOT-A",
        "name": "Beans",
        "item_type": "food",
        "storage_location": "Pantry",
        "storage_bucket": "",
        "expiry_date": "2030-01-01",
        "quantity": 5,
        "unidose_per_pack": 2,
        "target_unidoses_location": 20,
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
        "storage_bucket": "B3",
        "expiry_date": "2030-03-01",
        "quantity": 2,
        "unidose_per_pack": 2,
        "target_unidoses_location": 20,
    }
    created_b = client.post("/api/items", json=payload_b)
    assert created_b.status_code == 200

    listed = client.get("/api/items")
    assert listed.status_code == 200
    assert len(listed.json()) == 2
    assert listed.json()[0]["storage_location"] == "Pantry"
    assert listed.json()[0]["quantity"] >= 0

    filtered_unassigned = client.get("/?bucket_filter=unassigned")
    assert filtered_unassigned.status_code == 200
    assert "LOT-A" in filtered_unassigned.text
    assert "LOT-B" not in filtered_unassigned.text

    filtered_location = client.get("/?location_filter=Pantry")
    assert filtered_location.status_code == 200
    assert "Pantry" in filtered_location.text


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


def test_item_form_camera_compatibility_elements(client):
    response = client.get("/items/new")
    assert response.status_code == 200
    assert "barcode-fallback-reader-container" in response.text
    assert "html5-qrcode" in response.text
    assert "data-secure-context-required" in response.text
    assert "data-permission-denied" in response.text


def test_csv_import_route(client):
    csv_bytes = (
        b"name,item_type,storage_location,batch_code,expiry_date,quantity,renewal_date\n"
        b"Sugar,food,Pantry,LOT-55,2031-05-01,8,2031-04-01\n"
    )
    response = client.post(
        "/items/import",
        files={"file": ("items.csv", csv_bytes, "text/csv")},
    )
    assert response.status_code == 200
    assert "Imported: <strong>1</strong>" in response.text


def test_stock_views_and_product_detail_with_movement_log(client):
    payload = {
        "barcode": "5601111111111",
        "batch_code": "LOT-XYZ",
        "name": "Pasta",
        "item_type": "food",
        "storage_location": "Pontevel",
        "storage_bucket": "Bucket 3",
        "expiry_date": "2028-11-11",
        "quantity": 10,
        "unidose_per_pack": 2,
        "target_unidoses_location": 30,
    }
    created = client.post("/api/items", json=payload)
    assert created.status_code == 200
    item_id = created.json()["id"]

    views = client.get("/stock/views")
    assert views.status_code == 200
    assert "Per product (overall)" in views.text
    assert "Pasta" in views.text
    assert "Total unidoses" in views.text

    move = client.post(
        f"/items/{item_id}/move",
        data={"direction": "out", "quantity_step": "1", "note": "Consumed one"},
        follow_redirects=True,
    )
    assert move.status_code == 200

    detail = client.get("/products/by-name/food/Pasta")
    assert detail.status_code == 200
    assert "Consumed one" in detail.text

    shopping = client.get("/shopping-list")
    assert shopping.status_code == 200
    assert "Pasta" in shopping.text
    assert "Pontevel: 6" in shopping.text
