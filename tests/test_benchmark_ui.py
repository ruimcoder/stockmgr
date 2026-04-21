"""Tests for benchmark management UI routes (#127)."""
import pytest
from sqlmodel import Session

from app.db import engine
from app.models import BenchmarkItem
from datetime import datetime, UTC


def _make_item(**kwargs) -> BenchmarkItem:
    defaults = dict(
        name="Test Rice",
        name_pt="Arroz Teste",
        item_category="food",
        non_food_category=None,
        qty_per_day=0.1,
        uom="kg",
        scales_with_participants=True,
        notes=None,
        notes_pt=None,
        sort_order=0,
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    defaults.update(kwargs)
    return BenchmarkItem(**defaults)


def test_benchmark_page_accessible_to_admin(client):
    resp = client.get("/benchmark")
    assert resp.status_code == 200
    assert "benchmark" in resp.text.lower()


def test_benchmark_page_forbidden_for_unauthenticated(anon_client):
    resp = anon_client.get("/benchmark", follow_redirects=False)
    assert resp.status_code in (302, 303, 401)


def test_create_benchmark_item(client):
    resp = client.post(
        "/benchmark",
        data={
            "name": "Salt",
            "name_pt": "Sal",
            "item_category": "food",
            "non_food_category": "",
            "qty_per_day": "0.005",
            "uom": "kg",
            "scales_with_participants": "on",
            "is_active": "on",
            "sort_order": "1",
            "notes": "",
            "notes_pt": "",
        },
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)

    # Verify item appears in list page
    page = client.get("/benchmark")
    assert page.status_code == 200
    assert "Salt" in page.text


def test_delete_benchmark_item(client):
    with Session(engine) as session:
        item = _make_item(name="ToDelete", name_pt="ToDelete PT")
        session.add(item)
        session.commit()
        session.refresh(item)
        item_id = item.id

    resp = client.delete(f"/benchmark/{item_id}")
    assert resp.status_code == 200

    # Confirm item is gone
    with Session(engine) as session:
        assert session.get(BenchmarkItem, item_id) is None


def test_toggle_benchmark_item(client):
    with Session(engine) as session:
        item = _make_item(name="ToggleItem", name_pt="ToggleItem PT", is_active=True)
        session.add(item)
        session.commit()
        session.refresh(item)
        item_id = item.id

    resp = client.post(f"/benchmark/{item_id}/toggle")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_active"] is False

    # Toggle back
    resp2 = client.post(f"/benchmark/{item_id}/toggle")
    assert resp2.status_code == 200
    assert resp2.json()["is_active"] is True


def test_update_benchmark_item(client):
    with Session(engine) as session:
        item = _make_item(name="Original", name_pt="Original PT")
        session.add(item)
        session.commit()
        session.refresh(item)
        item_id = item.id

    resp = client.post(
        f"/benchmark/{item_id}/update",
        json={"name": "Updated", "qty_per_day": 0.2},
    )
    assert resp.status_code == 200

    with Session(engine) as session:
        updated = session.get(BenchmarkItem, item_id)
        assert updated.name == "Updated"
        assert updated.qty_per_day == pytest.approx(0.2)
