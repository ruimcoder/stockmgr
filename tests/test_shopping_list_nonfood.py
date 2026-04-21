"""Tests for non-food item support in shopping list (#132)."""
from datetime import date, timedelta


def _create_tool_item(client, name="Hammer", target=5):
    client.post(
        "/items",
        data={
            "name": name,
            "item_type": "tools",
            "item_category": "non_food",
            "non_food_category": "tools",
            "storage_location": "Garage",
            "quantity": "0",
            "unidose_per_pack": "1",
            "target_unidoses_location": str(target),
        },
        follow_redirects=False,
    )


def _create_food_item(client, name="Canned Soup", target=5):
    expiry = (date.today() + timedelta(days=365)).isoformat()
    client.post(
        "/items",
        data={
            "name": name,
            "item_type": "legumes",
            "item_category": "food",
            "storage_location": "Pantry",
            "expiry_date": expiry,
            "quantity": "0",
            "unidose_per_pack": "1",
            "target_unidoses_location": str(target),
        },
        follow_redirects=False,
    )


def test_shopping_list_includes_nonfood_items(client):
    """Non-food items with unmet targets appear in the shopping list."""
    _create_tool_item(client, name="Hammer 5lb", target=5)

    resp = client.get("/shopping-list")
    assert resp.status_code == 200
    assert "Hammer 5lb" in resp.text


def test_shopping_list_has_data_category_attribute(client):
    """Shopping list rows carry data-category for food and non_food items."""
    _create_food_item(client, name="Canned Soup X", target=5)
    _create_tool_item(client, name="Wrench 10mm", target=3)

    resp = client.get("/shopping-list")
    assert resp.status_code == 200
    assert 'data-category="food"' in resp.text
    assert 'data-category="non_food"' in resp.text
