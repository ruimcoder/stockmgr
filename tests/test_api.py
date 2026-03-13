from sqlmodel import Session

from app.db import engine
from app.models import User
from app.schemas import BarcodeLookupResult


def test_health_includes_status_and_version(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "test-suite"}


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


def test_inventory_is_shared_across_authorized_users(client):
    created = client.post(
        "/api/items",
        json={
            "barcode": "5601212121212",
            "batch_code": "SHARED-1",
            "name": "Shared Stock",
            "item_type": "food",
            "storage_location": "Pantry",
            "storage_bucket": "",
            "expiry_date": "2031-06-01",
            "quantity": 4,
            "unidose_per_pack": 1,
            "target_unidoses_location": 8,
        },
    )
    assert created.status_code == 200
    item_id = created.json()["id"]

    with Session(engine) as session:
        second_user = User(
            email="second.user@example.com",
            display_name="Second User",
            oauth_provider="dev",
            oauth_subject="second.user@example.com",
            approval_status="approved",
            is_admin=False,
        )
        session.add(second_user)
        session.commit()

    client.get("/auth/logout", follow_redirects=False)
    login = client.post(
        "/auth/dev-login",
        data={"email": "second.user@example.com"},
        follow_redirects=False,
    )
    assert login.status_code == 303
    assert login.headers["location"] == "/"

    listed = client.get("/api/items")
    assert listed.status_code == 200
    listed_item = next((item for item in listed.json() if item["id"] == item_id), None)
    assert listed_item is not None
    assert listed_item["name"] == "Shared Stock"

    moved = client.post(
        f"/items/{item_id}/move",
        data={"direction": "out", "quantity_step": "1", "note": "cross-user adjustment"},
        follow_redirects=False,
    )
    assert moved.status_code == 303

    after_move = client.get("/api/items")
    moved_item = next((item for item in after_move.json() if item["id"] == item_id), None)
    assert moved_item is not None
    assert moved_item["quantity"] == 3


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
    # Camera scanning has been removed; verify all UI elements are absent.
    assert "barcode-fallback-reader-container" not in response.text
    assert "start-camera-scan" not in response.text
    assert "barcode-camera.js" not in response.text
    assert "html5-qrcode" not in response.text
    assert "data-secure-context-required" not in response.text
    assert "data-permission-denied" not in response.text
    # The barcode lookup form should still be present.
    assert "barcode-lookup-form" in response.text


def test_pwa_routes_and_bootstrap_assets(client):
    home = client.get("/")
    assert home.status_code == 200
    assert 'rel="manifest"' in home.text
    assert "pwa-register.js" in home.text
    assert "icons/favicon.ico" in home.text
    assert "icon-180.png" in home.text

    manifest = client.get("/manifest.webmanifest")
    assert manifest.status_code == 200
    assert '"name": "stockmgr"' in manifest.text
    assert "icon-maskable-512.png" in manifest.text

    service_worker = client.get("/service-worker.js")
    assert service_worker.status_code == 200
    assert "stockmgr-v3" in service_worker.text

    offline_page = client.get("/offline.html")
    assert offline_page.status_code == 200
    assert "Offline mode" in offline_page.text

    assert client.get("/static/icons/favicon.ico").status_code == 200
    assert client.get("/static/icons/icon-16.png").status_code == 200
    assert client.get("/static/icons/icon-32.png").status_code == 200
    assert client.get("/static/icons/icon-180.png").status_code == 200
    assert client.get("/static/icons/icon-192.png").status_code == 200
    assert client.get("/static/icons/icon-512.png").status_code == 200
    assert client.get("/static/icons/icon-maskable-512.png").status_code == 200


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
    assert 'name="barcode"' in barcode_prefill.text
    assert "5603333333333" in barcode_prefill.text


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
    assert f"/items/{item_id}/edit" in detail.text
    assert "Add stock options" in detail.text
    assert "Add new storage location" in detail.text
    assert "Add new batch" in detail.text
    assert "Consumed one" in detail.text

    shopping = client.get("/shopping-list")
    assert shopping.status_code == 200
    assert "Pasta" in shopping.text
    assert "Pontevel: 6" in shopping.text


def test_item_edit_page_shows_related_batches_and_log(client):
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
    first_created = client.post("/api/items", json=payload_a)
    second_created = client.post("/api/items", json=payload_b)
    assert first_created.status_code == 200
    assert second_created.status_code == 200
    first_id = first_created.json()["id"]

    move = client.post(
        f"/items/{first_id}/move",
        data={"direction": "out", "quantity_step": "1", "note": "edit-context-note"},
        follow_redirects=False,
    )
    assert move.status_code == 303

    edit_page = client.get(f"/items/{first_id}/edit")
    assert edit_page.status_code == 200
    assert "LOT-1" in edit_page.text
    assert "LOT-2" in edit_page.text
    assert "Stock movement log" in edit_page.text
    assert "edit-context-note" in edit_page.text
    assert 'id="storage-location-select"' in edit_page.text
    assert '<option value="LocA" selected>' in edit_page.text
    assert '<option value="LocB">' in edit_page.text
    assert 'value="__new__"' in edit_page.text


def test_item_edit_allows_selecting_add_new_storage_location(client):
    created = client.post(
        "/api/items",
        json={
            "barcode": "5607777777777",
            "batch_code": "LOT-N1",
            "name": "Oats",
            "item_type": "food",
            "storage_location": "Pantry",
            "storage_bucket": "A2",
            "expiry_date": "2031-03-01",
            "quantity": 6,
            "unidose_per_pack": 1,
            "target_unidoses_location": 10,
        },
    )
    assert created.status_code == 200
    item = created.json()

    update_response = client.post(
        f"/items/{item['id']}/update",
        data={
            "barcode": item["barcode"],
            "batch_code": item["batch_code"],
            "name": item["name"],
            "item_type": item["item_type"],
            "storage_location": "__new__",
            "storage_location_new": "Basement Shelf",
            "storage_bucket": item["storage_bucket"],
            "expiry_date": item["expiry_date"],
            "quantity": str(item["quantity"]),
            "unidose_per_pack": str(item["unidose_per_pack"]),
            "target_unidoses_location": str(item["target_unidoses_location"]),
            "temp_min_c": "",
            "temp_max_c": "",
            "humidity_min_pct": "",
            "humidity_max_pct": "",
            "renewal_date": "",
        },
        follow_redirects=False,
    )
    assert update_response.status_code == 303

    items = client.get("/api/items")
    assert items.status_code == 200
    assert items.json()[0]["storage_location"] == "Basement Shelf"


def test_new_item_page_prefills_product_and_location_from_query(client):
    create_response = client.post(
        "/api/items",
        json={
            "barcode": "5605555555555",
            "batch_code": "B-01",
            "name": "Olive Oil",
            "item_type": "food",
            "storage_location": "Kitchen",
            "storage_bucket": "Shelf 1",
            "expiry_date": "2031-01-01",
            "quantity": 2,
            "unidose_per_pack": 1,
            "target_unidoses_location": 5,
        },
    )
    assert create_response.status_code == 200

    prefilled_for_new_location = client.get(
        "/items/new?name=Olive%20Oil&item_type=food&barcode=5605555555555"
    )
    assert prefilled_for_new_location.status_code == 200
    assert 'name="name" value="Olive Oil"' in prefilled_for_new_location.text
    assert 'name="item_type" value="food"' in prefilled_for_new_location.text
    assert 'name="barcode"' in prefilled_for_new_location.text
    assert "5605555555555" in prefilled_for_new_location.text

    prefilled_for_batch = client.get(
        "/items/new?name=Olive%20Oil&item_type=food&barcode=5605555555555&storage_location=Kitchen"
    )
    assert prefilled_for_batch.status_code == 200
    assert 'id="location-entries"' in prefilled_for_batch.text
    assert 'name="loc_location"' in prefilled_for_batch.text


def test_multi_location_create_produces_one_item_per_row(client):
    """Submitting loc_* multi-row fields creates one StockItem per location row."""
    csrf = client.get("/items/new").text
    import re
    token = re.search(r'name="_csrf_token" value="([^"]+)"', csrf).group(1)

    response = client.post(
        "/items",
        data={
            "_csrf_token": token,
            "name": "Canned Tomatoes",
            "item_type": "food",
            "barcode": "5601111111111",
            "unidose_per_pack": "2",
            "loc_location": ["Pantry A", "Basement"],
            "loc_batch_code": ["B01", "B02"],
            "loc_expiry": ["2032-01-01", "2033-06-01"],
            "loc_quantity": ["10", "5"],
            "loc_bucket": ["Shelf 1", ""],
            "loc_renewal": ["", ""],
            "loc_target": ["0", "0"],
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    items = client.get("/api/items").json()
    tomato_items = [i for i in items if i["name"] == "Canned Tomatoes"]
    assert len(tomato_items) == 2
    locations = {i["storage_location"] for i in tomato_items}
    assert locations == {"Pantry A", "Basement"}
    assert tomato_items[0]["barcode"] == "5601111111111"


def test_multi_location_create_skips_empty_rows(client):
    """Rows with empty location or expiry are skipped."""
    csrf = client.get("/items/new").text
    import re
    token = re.search(r'name="_csrf_token" value="([^"]+)"', csrf).group(1)

    response = client.post(
        "/items",
        data={
            "_csrf_token": token,
            "name": "Rice",
            "item_type": "food",
            "barcode": "5602222222222",
            "unidose_per_pack": "1",
            "loc_location": ["Kitchen", ""],
            "loc_batch_code": ["", ""],
            "loc_expiry": ["2030-12-31", ""],
            "loc_quantity": ["3", "0"],
            "loc_bucket": ["", ""],
            "loc_renewal": ["", ""],
            "loc_target": ["0", "0"],
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    items = client.get("/api/items").json()
    rice_items = [i for i in items if i["name"] == "Rice"]
    assert len(rice_items) == 1
    assert rice_items[0]["storage_location"] == "Kitchen"


def test_create_form_shows_plan_locations_datalist(client):
    """The create form datalist includes locations from existing items."""
    client.post(
        "/api/items",
        json={
            "name": "Pasta",
            "item_type": "food",
            "barcode": "5603333333333",
            "storage_location": "StorageRoom",
            "expiry_date": "2031-01-01",
            "quantity": 1,
            "unidose_per_pack": 1,
            "target_unidoses_location": 0,
        },
    )
    page = client.get("/items/new")
    assert page.status_code == 200
    assert "StorageRoom" in page.text
    assert 'id="plan-locations-list"' in page.text


def test_product_detail_shows_batches_grouped_by_location(client):
    """Product detail page groups batches by location."""
    for loc in ["Pantry", "Garage"]:
        client.post(
            "/api/items",
            json={
                "name": "Lentils",
                "item_type": "food",
                "barcode": "5604444444444",
                "storage_location": loc,
                "expiry_date": "2031-06-01",
                "quantity": 5,
                "unidose_per_pack": 1,
                "target_unidoses_location": 10,
            },
        )
    page = client.get("/products/by-name/food/Lentils")
    assert page.status_code == 200
    assert "Pantry" in page.text
    assert "Garage" in page.text



    unauthorized = client.get("/api/excel/stocks")
    assert unauthorized.status_code == 401

    authorized = client.get(
        "/api/excel/stocks",
        headers={"x-excel-api-key": "excel-test-key"},
    )
    assert authorized.status_code == 200
    assert isinstance(authorized.json(), list)


def test_excel_api_update_and_upsert(client):
    created = client.post(
        "/api/items",
        json={
            "barcode": "5608888888888",
            "batch_code": "XLS-1",
            "name": "Chickpeas",
            "item_type": "food",
            "storage_location": "Pantry",
            "storage_bucket": "A1",
            "expiry_date": "2032-01-01",
            "quantity": 4,
            "unidose_per_pack": 1,
            "target_unidoses_location": 10,
        },
    )
    assert created.status_code == 200
    item_id = created.json()["id"]

    updated = client.put(
        f"/api/excel/stocks/{item_id}",
        headers={"x-excel-api-key": "excel-test-key"},
        json={
            "barcode": "5608888888888",
            "batch_code": "XLS-1",
            "name": "Chickpeas",
            "item_type": "food",
            "storage_location": "Pantry",
            "storage_bucket": "A1",
            "expiry_date": "2032-01-01",
            "quantity": 9,
            "unidose_per_pack": 1,
            "target_unidoses_location": 10,
            "renewal_date": "2031-12-01",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["quantity"] == 9

    upsert = client.post(
        "/api/excel/stocks/upsert",
        headers={"x-excel-api-key": "excel-test-key"},
        json={
            "rows": [
                {
                    "id": item_id,
                    "barcode": "5608888888888",
                    "batch_code": "XLS-1",
                    "name": "Chickpeas",
                    "item_type": "food",
                    "storage_location": "Pantry",
                    "storage_bucket": "A1",
                    "expiry_date": "2032-01-01",
                    "quantity": 11,
                    "unidose_per_pack": 1,
                    "target_unidoses_location": 10,
                },
                {
                    "barcode": "5609999990000",
                    "batch_code": "XLS-2",
                    "name": "Chickpeas",
                    "item_type": "food",
                    "storage_location": "Backup",
                    "storage_bucket": "B2",
                    "expiry_date": "2032-04-01",
                    "quantity": 3,
                    "unidose_per_pack": 1,
                    "target_unidoses_location": 8,
                },
            ]
        },
    )
    assert upsert.status_code == 200
    body = upsert.json()
    assert body["updated"] == 1
    assert body["created"] == 1
    assert len(body["rows"]) == 2
