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


def test_pwa_routes_and_bootstrap_assets(client):
    home = client.get("/")
    assert home.status_code == 200
    assert 'rel="manifest"' in home.text
    assert "pwa-register.js" in home.text

    manifest = client.get("/manifest.webmanifest")
    assert manifest.status_code == 200
    assert '"name": "stockmgr"' in manifest.text

    service_worker = client.get("/service-worker.js")
    assert service_worker.status_code == 200
    assert "CACHE_NAME" in service_worker.text

    offline_page = client.get("/offline.html")
    assert offline_page.status_code == 200
    assert "Offline mode" in offline_page.text


def test_device_check_page(client):
    response = client.get("/device-check")
    assert response.status_code == 200
    assert "Device Compatibility Check" in response.text
    assert "device-check.js" in response.text


def test_home_search_routes_to_detail_or_prefilled_new_item(client):
    in_stock_payload = {
        "barcode": "5602222222222",
        "batch_code": "LOT-S1",
        "name": "Lentils",
        "item_type": "food",
        "storage_location": "Pantry",
        "storage_bucket": "A1",
        "expiry_date": "2029-10-01",
        "quantity": 3,
        "unidose_per_pack": 1,
        "target_unidoses_location": 5,
    }
    created = client.post("/api/items", json=in_stock_payload)
    assert created.status_code == 200

    to_detail = client.post(
        "/items/search",
        data={"query": "5602222222222"},
        follow_redirects=False,
    )
    assert to_detail.status_code == 303
    assert "/products/by-name/food/Lentils" in to_detail.headers["location"]

    to_new_by_name = client.post(
        "/items/search",
        data={"query": "NotInStockYet"},
        follow_redirects=False,
    )
    assert to_new_by_name.status_code == 303
    assert "/items/new?name=NotInStockYet" in to_new_by_name.headers["location"]

    name_prefill = client.get("/items/new?name=NotInStockYet")
    assert name_prefill.status_code == 200
    assert 'name="name" value="NotInStockYet"' in name_prefill.text

    out_of_stock_payload = {
        "barcode": "5603333333333",
        "batch_code": "LOT-S0",
        "name": "ZeroQty",
        "item_type": "food",
        "storage_location": "Pantry",
        "storage_bucket": "",
        "expiry_date": "2029-11-01",
        "quantity": 0,
        "unidose_per_pack": 1,
        "target_unidoses_location": 5,
    }
    created_zero = client.post("/api/items", json=out_of_stock_payload)
    assert created_zero.status_code == 200

    to_new_by_barcode = client.post(
        "/items/search", data={"query": "5603333333333"}, follow_redirects=False
    )
    assert to_new_by_barcode.status_code == 303
    assert "/items/new?barcode=5603333333333" in to_new_by_barcode.headers["location"]

    barcode_prefill = client.get("/items/new?barcode=5603333333333")
    assert barcode_prefill.status_code == 200
    assert 'name="barcode" value="5603333333333"' in barcode_prefill.text


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
    assert "Product details" in detail.text
    assert "/products/by-name/food/Pasta/edit" in detail.text
    assert "Consumed one" in detail.text

    shopping = client.get("/shopping-list")
    assert shopping.status_code == 200
    assert "Pasta" in shopping.text
    assert "Pontevel: 6" in shopping.text


def test_product_detail_edit_updates_all_batches(client):
    payload_a = {
        "barcode": "5604444444444",
        "batch_code": "LOT-1",
        "name": "Rice",
        "item_type": "food",
        "storage_location": "LocA",
        "storage_bucket": "B1",
        "expiry_date": "2030-01-01",
        "quantity": 4,
        "unidose_per_pack": 2,
        "target_unidoses_location": 10,
    }
    payload_b = {
        "barcode": "5604444444444",
        "batch_code": "LOT-2",
        "name": "Rice",
        "item_type": "food",
        "storage_location": "LocB",
        "storage_bucket": "B2",
        "expiry_date": "2030-02-01",
        "quantity": 6,
        "unidose_per_pack": 2,
        "target_unidoses_location": 12,
    }
    assert client.post("/api/items", json=payload_a).status_code == 200
    assert client.post("/api/items", json=payload_b).status_code == 200

    edit_page = client.get("/products/by-name/food/Rice/edit")
    assert edit_page.status_code == 200
    assert "Edit product details" in edit_page.text

    edited = client.post(
        "/products/by-name/food/Rice/edit",
        data={
            "name": "Rice Premium",
            "item_type": "food",
            "barcode": "5609999999999",
            "temp_min_c": "4",
            "temp_max_c": "20",
            "humidity_min_pct": "30",
            "humidity_max_pct": "70",
            "renewal_date": "2029-12-01",
        },
        follow_redirects=False,
    )
    assert edited.status_code == 303
    assert "/products/by-name/food/Rice%20Premium?m=product-updated" in edited.headers["location"]

    detail = client.get("/products/by-name/food/Rice%20Premium")
    assert detail.status_code == 200
    assert "5609999999999" in detail.text
    assert "Total stock quantity" in detail.text
    assert "LOT-1" in detail.text
    assert "LOT-2" in detail.text

    old_detail = client.get("/products/by-name/food/Rice")
    assert old_detail.status_code == 404
