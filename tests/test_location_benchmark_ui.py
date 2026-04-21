"""Tests for per-location benchmark configuration UI (#129)."""
from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from sqlmodel import Session

from app.benchmark_seed import sync_location_benchmarks
from app.db import engine
from app.models import BenchmarkItem, LocationBenchmark, LocationPlan


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


def _make_plan(location: str = "TestLoc", participants: int = 2, days: int = 7) -> LocationPlan:
    return LocationPlan(
        location=location,
        participants=participants,
        stock_duration_days=days,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _make_lb(location: str, benchmark_item_id: int, **kwargs) -> LocationBenchmark:
    defaults = dict(
        location=location,
        benchmark_item_id=benchmark_item_id,
        is_enabled=True,
        qty_override=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    defaults.update(kwargs)
    return LocationBenchmark(**defaults)


def test_location_benchmark_page_404_for_unknown_location(client):
    resp = client.get("/location-plans/nonexistent/benchmark", follow_redirects=False)
    assert resp.status_code == 404


def test_location_benchmark_page_renders_for_known_location(client):
    with Session(engine) as session:
        plan = _make_plan(location="Shelter")
        session.add(plan)
        session.add(_make_item(name="Water", name_pt="Água"))
        session.commit()
        sync_location_benchmarks(session)

    resp = client.get("/location-plans/Shelter/benchmark")
    assert resp.status_code == 200
    assert "Shelter" in resp.text
    assert "Water" in resp.text


def test_toggle_location_benchmark(client):
    with Session(engine) as session:
        item = _make_item(name="Rice", name_pt="Arroz")
        session.add(item)
        session.commit()
        session.refresh(item)
        lb = _make_lb("Shelter2", item.id, is_enabled=True)
        session.add(lb)
        session.commit()
        session.refresh(lb)
        lb_id = lb.id

    resp = client.patch(
        f"/api/location-benchmark/{lb_id}/toggle",
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == lb_id
    assert data["is_enabled"] is False

    # Toggle back
    resp2 = client.patch(
        f"/api/location-benchmark/{lb_id}/toggle",
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert resp2.json()["is_enabled"] is True


def test_set_override(client):
    with Session(engine) as session:
        item = _make_item(name="Salt", name_pt="Sal")
        session.add(item)
        session.commit()
        session.refresh(item)
        lb = _make_lb("Shelter3", item.id)
        session.add(lb)
        session.commit()
        session.refresh(lb)
        lb_id = lb.id

    resp = client.patch(
        f"/api/location-benchmark/{lb_id}/override",
        content=json.dumps({"qty": 1.5}),
        headers={"Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == lb_id
    assert data["qty_override"] == 1.5


def test_clear_override(client):
    with Session(engine) as session:
        item = _make_item(name="Oil", name_pt="Óleo")
        session.add(item)
        session.commit()
        session.refresh(item)
        lb = _make_lb("Shelter4", item.id, qty_override=2.0)
        session.add(lb)
        session.commit()
        session.refresh(lb)
        lb_id = lb.id

    resp = client.patch(
        f"/api/location-benchmark/{lb_id}/override",
        content=json.dumps({"qty": None}),
        headers={"Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["qty_override"] is None
