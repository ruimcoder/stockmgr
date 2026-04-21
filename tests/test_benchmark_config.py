"""Tests for BenchmarkItem qty_period field, _effective_daily_qty, and gap normalisation."""
from __future__ import annotations

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.benchmark_seed import seed_benchmark_if_empty
from app.gap_utils import _effective_daily_qty, compute_gap_rows, get_target_qty
from app.models import BenchmarkItem, LocationBenchmark, StockItem


def _b_item(
    id: int = 1,
    name: str = "Test",
    name_pt: str = "Teste",
    item_category: str = "food",
    non_food_category: str | None = None,
    qty_per_day: float = 1.0,
    qty_period: str = "day",
    uom: str = "unit",
    scales_with_participants: bool = True,
    is_active: bool = True,
) -> BenchmarkItem:
    b = BenchmarkItem(
        name=name,
        name_pt=name_pt,
        item_category=item_category,
        non_food_category=non_food_category,
        qty_per_day=qty_per_day,
        qty_period=qty_period,
        uom=uom,
        scales_with_participants=scales_with_participants,
        is_active=is_active,
    )
    b.id = id
    return b


def _lb(
    benchmark_item_id: int = 1,
    is_enabled: bool = True,
    qty_override: float | None = None,
) -> LocationBenchmark:
    lb = LocationBenchmark(
        location="TestLoc",
        benchmark_item_id=benchmark_item_id,
        is_enabled=is_enabled,
        qty_override=qty_override,
    )
    lb.id = 1
    return lb


def test_benchmark_item_default_qty_period():
    item = BenchmarkItem(name="Water", name_pt="Agua", item_category="food", qty_per_day=2.0, uom="L")
    assert item.qty_period == "day"


def test_benchmark_item_accepts_week_period():
    item = BenchmarkItem(name="Salt", name_pt="Sal", item_category="food", qty_per_day=0.07, qty_period="week", uom="kg")
    assert item.qty_period == "week"


def test_benchmark_item_accepts_all_periods():
    for period in ("day", "week", "month", "fixed"):
        item = _b_item(qty_period=period)
        assert item.qty_period == period


def test_effective_daily_qty_day():
    item = _b_item(qty_per_day=2.0, qty_period="day")
    assert _effective_daily_qty(item, 2.0) == 2.0


def test_effective_daily_qty_week():
    item = _b_item(qty_per_day=7.0, qty_period="week")
    assert abs(_effective_daily_qty(item, 7.0) - 1.0) < 1e-9


def test_effective_daily_qty_month():
    item = _b_item(qty_per_day=30.0, qty_period="month")
    assert abs(_effective_daily_qty(item, 30.0) - 1.0) < 1e-9


def test_effective_daily_qty_fixed():
    item = _b_item(qty_per_day=5.0, qty_period="fixed")
    assert _effective_daily_qty(item, 5.0) == 5.0


def test_target_qty_day_scales():
    item = _b_item(qty_per_day=2.0, qty_period="day", scales_with_participants=True)
    assert get_target_qty(item, None, participants=3, stock_duration_days=7) == 2.0 * 3 * 7


def test_target_qty_week_scales():
    item = _b_item(qty_per_day=7.0, qty_period="week", scales_with_participants=True)
    assert abs(get_target_qty(item, None, participants=2, stock_duration_days=14) - 28.0) < 1e-9


def test_target_qty_month_scales():
    item = _b_item(qty_per_day=30.0, qty_period="month", scales_with_participants=True)
    assert abs(get_target_qty(item, None, participants=1, stock_duration_days=30) - 30.0) < 1e-9


def test_target_qty_fixed_is_absolute():
    item = _b_item(qty_per_day=1.0, qty_period="fixed", scales_with_participants=False)
    assert get_target_qty(item, None, participants=5, stock_duration_days=90) == 1.0


def test_target_qty_fixed_ignores_scales_flag():
    item = _b_item(qty_per_day=2.0, qty_period="fixed", scales_with_participants=True)
    assert get_target_qty(item, None, participants=10, stock_duration_days=365) == 2.0


def test_target_qty_disabled_returns_zero():
    item = _b_item(qty_period="week")
    lb = _lb(is_enabled=False)
    assert get_target_qty(item, lb, participants=3, stock_duration_days=7) == 0.0


def test_compute_gap_fixed_item_coverage():
    item = _b_item(id=1, name="Generator", item_category="non_food", non_food_category="energy",
                   qty_per_day=1.0, qty_period="fixed", scales_with_participants=False)
    stock = StockItem(user_id=1, name="Generator", item_type="non_food",
                      storage_location="TestLoc", quantity=1, unidose_per_pack=1,
                      item_category="non_food", non_food_category="energy")
    stock.id = 1
    rows = compute_gap_rows([item], {}, [stock], participants=5, stock_duration_days=30)
    assert rows[0]["target_qty"] == 1.0
    assert rows[0]["coverage_pct"] == 100.0
    assert rows[0]["status"] == "ok"


def test_compute_gap_fixed_item_missing():
    item = _b_item(id=1, name="Axe", item_category="non_food", non_food_category="tools",
                   qty_per_day=1.0, qty_period="fixed", scales_with_participants=False)
    rows = compute_gap_rows([item], {}, [], participants=5, stock_duration_days=30)
    assert rows[0]["target_qty"] == 1.0
    assert rows[0]["current_stock"] == 0.0
    assert rows[0]["status"] == "missing"


@pytest.fixture()
def mem_engine():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)


def test_seed_items_have_qty_period(mem_engine):
    with Session(mem_engine) as session:
        seed_benchmark_if_empty(session)
        items = session.exec(select(BenchmarkItem)).all()
    assert all(item.qty_period in ("day", "week", "month", "fixed") for item in items)


def test_seed_fixed_items_are_tools_seeds_comms(mem_engine):
    with Session(mem_engine) as session:
        seed_benchmark_if_empty(session)
        fixed = session.exec(select(BenchmarkItem).where(BenchmarkItem.qty_period == "fixed")).all()
    fixed_cats = {i.non_food_category for i in fixed}
    assert "tools" in fixed_cats
    assert "seeds" in fixed_cats
    assert "communication" in fixed_cats


def test_seed_food_items_are_day_period(mem_engine):
    with Session(mem_engine) as session:
        seed_benchmark_if_empty(session)
        food_items = session.exec(select(BenchmarkItem).where(BenchmarkItem.item_category == "food")).all()
    assert all(i.qty_period == "day" for i in food_items)
