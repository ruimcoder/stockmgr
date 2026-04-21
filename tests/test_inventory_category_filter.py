"""Tests for data-category/data-nfc attributes and category filter on inventory list (#131)."""


def _create_food_item(client):
    client.post(
        "/items",
        data={
            "name": "Canned Beans",
            "item_type": "legumes",
            "item_category": "food",
            "storage_location": "Pantry",
            "expiry_date": "2028-01-01",
            "quantity": "5",
            "unidose_per_pack": "1",
        },
        follow_redirects=False,
    )


def _create_medicine_item(client):
    client.post(
        "/items",
        data={
            "name": "Ibuprofen",
            "item_type": "medicine",
            "item_category": "non_food",
            "non_food_category": "medicine",
            "storage_location": "Medicine Cabinet",
            "expiry_date": "2027-06-01",
            "quantity": "2",
            "unidose_per_pack": "1",
        },
        follow_redirects=False,
    )


def test_inventory_rows_have_data_category_attribute(client):
    """Inventory list <tr> rows carry data-category for food and non_food items."""
    _create_food_item(client)
    _create_medicine_item(client)

    resp = client.get("/")
    assert resp.status_code == 200
    assert 'data-category="food"' in resp.text
    assert 'data-category="non_food"' in resp.text


def test_inventory_non_food_row_has_nfc_attribute(client):
    """Non-food medicine item row has data-nfc="medicine"."""
    _create_medicine_item(client)

    resp = client.get("/")
    assert resp.status_code == 200
    assert 'data-nfc="medicine"' in resp.text


def test_inventory_food_row_nfc_is_empty(client):
    """Food item row has data-nfc=""."""
    _create_food_item(client)

    resp = client.get("/")
    assert resp.status_code == 200
    assert 'data-nfc=""' in resp.text
