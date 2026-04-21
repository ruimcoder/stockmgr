"""Tests for correct expiry filtering for non-food items in renewals (#133)."""
from datetime import date, timedelta


def _create_tool_item(client, name="Shovel"):
    """Tools have no expiry_date."""
    client.post(
        "/items",
        data={
            "name": name,
            "item_type": "tools",
            "item_category": "non_food",
            "non_food_category": "tools",
            "storage_location": "Shed",
            "quantity": "1",
            "unidose_per_pack": "1",
        },
        follow_redirects=False,
    )


def _create_food_item_expiring_soon(client, name="Canned Peas", days=15):
    expiry = (date.today() + timedelta(days=days)).isoformat()
    client.post(
        "/items",
        data={
            "name": name,
            "item_type": "legumes",
            "item_category": "food",
            "storage_location": "Pantry",
            "expiry_date": expiry,
            "quantity": "2",
            "unidose_per_pack": "1",
        },
        follow_redirects=False,
    )


def _create_medicine_item_expiring_soon(client, name="Aspirin", days=15):
    expiry = (date.today() + timedelta(days=days)).isoformat()
    client.post(
        "/items",
        data={
            "name": name,
            "item_type": "medicine",
            "item_category": "non_food",
            "non_food_category": "medicine",
            "storage_location": "Medicine Cabinet",
            "expiry_date": expiry,
            "quantity": "1",
            "unidose_per_pack": "1",
        },
        follow_redirects=False,
    )


def test_renewals_excludes_null_expiry_items(client):
    """Tools (no expiry) do not appear in renewals; food with expiry does."""
    _create_tool_item(client, name="Unique Shovel 99")
    _create_food_item_expiring_soon(client, name="Unique Peas 99", days=15)

    resp = client.get("/renewals?days=30")
    assert resp.status_code == 200
    assert "Unique Shovel 99" not in resp.text
    assert "Unique Peas 99" in resp.text


def test_renewals_includes_medicine_with_expiry(client):
    """Medicine items with an expiry date within the window appear in renewals."""
    _create_medicine_item_expiring_soon(client, name="Unique Aspirin 77", days=15)

    resp = client.get("/renewals?days=30")
    assert resp.status_code == 200
    assert "Unique Aspirin 77" in resp.text
