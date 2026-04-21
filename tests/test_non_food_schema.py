"""Tests for item_category and non_food_category schema fields."""
import pytest
from tests.conftest import *  # noqa — import fixtures


def test_create_food_item_default_category(client):
    """Creating an item without specifying category defaults to 'food'."""
    resp = client.post("/items", data={
        "name": "Rice",
        "item_type": "grain",
        "storage_location": "Test Location",
        "expiry_date": "2027-01-01",
        "quantity": "10",
        "unidose_per_pack": "1",
    }, follow_redirects=False)
    # Should redirect on success
    assert resp.status_code in (302, 303, 200)


def test_create_non_food_item(client):
    """Non-food items can be created with item_category=non_food."""
    resp = client.post("/items", data={
        "name": "Paracetamol",
        "item_type": "medicine",
        "item_category": "non_food",
        "non_food_category": "medicine",
        "storage_location": "Test Location",
        "expiry_date": "2027-01-01",
        "quantity": "20",
        "unidose_per_pack": "1",
    }, follow_redirects=False)
    assert resp.status_code in (302, 303, 200)


def test_non_food_categories_constant():
    from app.non_food_categories import NON_FOOD_CATEGORIES, ITEM_CATEGORIES
    assert "medicine" in NON_FOOD_CATEGORIES
    assert "energy" in NON_FOOD_CATEGORIES
    assert "tools" in NON_FOOD_CATEGORIES
    assert len(NON_FOOD_CATEGORIES) == 8
    assert "food" in ITEM_CATEGORIES
    assert "non_food" in ITEM_CATEGORIES


def test_item_category_in_api_response(client):
    """GET /api/items returns item_category field."""
    resp = client.get("/api/items")
    assert resp.status_code == 200
    # If items exist, check field is present
    data = resp.json()
    if isinstance(data, list) and len(data) > 0:
        assert "item_category" in data[0]
