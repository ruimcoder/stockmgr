"""Tests for stock gap analysis: compute_gap_rows and /gap-analysis routes."""
from __future__ import annotations

import pytest
from sqlmodel import Session

from app.db import engine
from app.gap_utils import compute_gap_rows
from app.models import BenchmarkItem, LocationBenchmark, LocationPlan, StockItem, User


# ---------------------------------------------------------------------------
# Helpers to build plain objects (no DB needed for unit tests)
# ---------------------------------------------------------------------------

def _b_item(
    id: int = 1,
    name: str = "Water",
    name_pt: str = "Água",
    item_category: str = "food",
    non_food_category: str | None = None,
    qty_per_day: float = 2.0,
    uom: str = "L",
    scales_with_participants: bool = True,
    is_active: bool = True,
) -> BenchmarkItem:
    b = BenchmarkItem(
        name=name,
        name_pt=name_pt,
        item_category=item_category,
        non_food_category=non_food_category,
        qty_per_day=qty_per_day,
        uom=uom,
        scales_with_participants=scales_with_participants,
        is_active=is_active,
    )
    b.id = id
    return b


def _lb(benchmark_item_id: int = 1, is_enabled: bool = True, qty_override: float | None = None) -> LocationBenchmark:
    lb = LocationBenchmark(
        location="TestLoc",
        benchmark_item_id=benchmark_item_id,
        is_enabled=is_enabled,
        qty_override=qty_override,
    )
    lb.id = 1
    return lb


def _stock(
    quantity: int = 10,
    unidose_per_pack: int = 1,
    item_category: str = "food",
    non_food_category: str | None = None,
) -> StockItem:
    s = StockItem(
        user_id=1,
        name="Test",
        item_type="food",
        storage_location="TestLoc",
        quantity=quantity,
        unidose_per_pack=unidose_per_pack,
        item_category=item_category,
        non_food_category=non_food_category,
    )
    s.id = 1
    return s


# ---------------------------------------------------------------------------
# Unit tests — no DB required
# ---------------------------------------------------------------------------

def test_compute_gap_rows_correct_coverage():
    b = _b_item(qty_per_day=2.0, scales_with_participants=True)
    lb = _lb(benchmark_item_id=1, is_enabled=True)
    stock = _stock(quantity=10, unidose_per_pack=1, item_category="food")

    rows = compute_gap_rows([b], {1: lb}, [stock], participants=1, stock_duration_days=7)

    assert len(rows) == 1
    row = rows[0]
    assert row["target_qty"] == 14.0
    assert row["current_stock"] == 10.0
    assert abs(row["coverage_pct"] - 71.4) < 0.2
    assert row["status"] == "partial"


def test_compute_gap_rows_disabled_excluded():
    b = _b_item()
    lb = _lb(benchmark_item_id=1, is_enabled=False)

    rows = compute_gap_rows([b], {1: lb}, [], participants=2, stock_duration_days=7)

    assert rows == []


def test_compute_gap_rows_no_stock_is_missing():
    b = _b_item(qty_per_day=1.0)

    rows = compute_gap_rows([b], {}, [], participants=1, stock_duration_days=7)

    assert len(rows) == 1
    assert rows[0]["status"] == "missing"
    assert rows[0]["current_stock"] == 0.0


def test_compute_gap_rows_sorted_by_coverage():
    b_full = _b_item(id=1, name="Water", qty_per_day=1.0, scales_with_participants=False)
    b_empty = _b_item(id=2, name="Meds", item_category="non_food", non_food_category="medicine", qty_per_day=1.0, scales_with_participants=False)

    stock_full = _stock(quantity=100, unidose_per_pack=1, item_category="food")

    rows = compute_gap_rows(
        [b_full, b_empty],
        {},
        [stock_full],
        participants=1,
        stock_duration_days=7,
    )

    assert len(rows) == 2
    # 0% coverage (missing meds) should come first
    assert rows[0]["benchmark_item"].item_category == "non_food"
    assert rows[0]["coverage_pct"] == 0.0
    assert rows[1]["coverage_pct"] == 100.0


# ---------------------------------------------------------------------------
# Integration tests — require DB + client fixture
# ---------------------------------------------------------------------------

def test_gap_analysis_page_renders(client):
    """GET /gap-analysis returns 200 for an authenticated user."""
    resp = client.get("/gap-analysis")
    assert resp.status_code == 200


def test_gap_analysis_no_plans_shows_empty(client):
    """GET /gap-analysis with no LocationPlan renders without error."""
    resp = client.get("/gap-analysis")
    assert resp.status_code == 200
    # No location plan → info alert shown, no traceback
    assert "gap" in resp.text.lower() or "analysis" in resp.text.lower()
