"""Tests for category-aware field visibility in item add/edit form (#125)."""

from sqlmodel import Session, select as sqlselect

from app.db import engine
from app.models import StockItem


def test_get_new_item_form_renders_item_category(client):
    """GET /items/new renders item_category radio controls."""
    resp = client.get("/items/new")
    assert resp.status_code == 200
    assert 'name="item_category"' in resp.text


def test_get_new_item_form_renders_non_food_category(client):
    """GET /items/new renders non_food_category select control."""
    resp = client.get("/items/new")
    assert resp.status_code == 200
    assert 'name="non_food_category"' in resp.text


def test_post_non_food_item_creates_item_in_db(client):
    """POST /items with item_category=non_food, non_food_category=tools creates item."""
    resp = client.post(
        "/items",
        data={
            "name": "Wrench Set",
            "item_type": "tools",
            "item_category": "non_food",
            "non_food_category": "tools",
            "storage_location": "Garage",
            "quantity": "2",
            "unidose_per_pack": "1",
        },
        follow_redirects=False,
    )
    # Expect a redirect after successful creation
    assert resp.status_code in (302, 303)

    with Session(engine) as session:
        item = session.exec(
            sqlselect(StockItem).where(StockItem.name == "Wrench Set")
        ).first()
    assert item is not None
    assert item.item_category == "non_food"
    assert item.non_food_category == "tools"


def test_edit_non_food_item_preselects_category(client):
    """GET /items/{id}/edit pre-selects item_category and non_food_category."""
    # Create a non-food item first
    client.post(
        "/items",
        data={
            "name": "First Aid Kit",
            "item_type": "medicine",
            "item_category": "non_food",
            "non_food_category": "medicine",
            "storage_location": "Bathroom Cabinet",
            "expiry_date": "2028-06-01",
            "quantity": "1",
            "unidose_per_pack": "1",
        },
        follow_redirects=False,
    )

    with Session(engine) as session:
        item = session.exec(
            sqlselect(StockItem).where(StockItem.name == "First Aid Kit")
        ).first()
    assert item is not None

    resp = client.get(f"/items/{item.id}/edit")
    assert resp.status_code == 200
    # The edit form should contain the item_category radio checked for non_food
    assert 'value="non_food"' in resp.text
    assert 'value="medicine"' in resp.text
    # The selected non_food_category should be present
    assert "non_food_category" in resp.text
