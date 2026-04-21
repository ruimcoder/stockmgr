"""Tests for LocationBenchmark model, sync helper, and gap calculation."""
from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.benchmark_seed import sync_location_benchmarks
from app.gap_utils import get_target_qty
from app.models import BenchmarkItem, LocationBenchmark, LocationPlan


@pytest.fixture()
def mem_engine():
    """In-memory SQLite engine with all tables created fresh."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)


def _make_item(**kwargs) -> BenchmarkItem:
    defaults = dict(
        name="Test Item",
        name_pt="Item de Teste",
        item_category="food",
        qty_per_day=1.0,
        uom="kg",
        scales_with_participants=True,
        is_active=True,
        sort_order=0,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    defaults.update(kwargs)
    return BenchmarkItem(**defaults)


def _make_location_plan(location: str, participants: int = 2, days: int = 7) -> LocationPlan:
    return LocationPlan(
        location=location,
        participants=participants,
        stock_duration_days=days,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


# ── get_target_qty tests ────────────────────────────────────────────────────


def test_get_target_qty_scales_with_participants():
    item = _make_item(qty_per_day=2.0, scales_with_participants=True)
    result = get_target_qty(item, None, participants=3, stock_duration_days=7)
    assert result == 42.0  # 2.0 × 3 × 7


def test_get_target_qty_no_scaling():
    item = _make_item(qty_per_day=0.3, scales_with_participants=False)
    result = get_target_qty(item, None, participants=3, stock_duration_days=7)
    assert pytest.approx(result) == 2.1  # 0.3 × 7


def test_get_target_qty_with_override():
    item = _make_item(qty_per_day=2.0, scales_with_participants=True)
    override = LocationBenchmark(
        location="A",
        benchmark_item_id=1,
        is_enabled=True,
        qty_override=1.0,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    result = get_target_qty(item, override, participants=2, stock_duration_days=7)
    assert result == 14.0  # 1.0 × 2 × 7


def test_get_target_qty_disabled():
    item = _make_item(qty_per_day=2.0)
    override = LocationBenchmark(
        location="A",
        benchmark_item_id=1,
        is_enabled=False,
        qty_override=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    result = get_target_qty(item, override, participants=3, stock_duration_days=7)
    assert result == 0.0


# ── sync_location_benchmarks tests ─────────────────────────────────────────


def test_sync_creates_location_benchmark_rows(mem_engine):
    with Session(mem_engine) as session:
        session.add(_make_location_plan("loc-A"))
        session.add(_make_location_plan("loc-B"))
        for i in range(3):
            session.add(_make_item(name=f"Item {i}", name_pt=f"Item PT {i}", sort_order=i))
        session.commit()

        created = sync_location_benchmarks(session)

        all_rows = session.exec(select(LocationBenchmark)).all()
    assert created == 6  # 2 locations × 3 items
    assert len(all_rows) == 6


def test_sync_is_idempotent(mem_engine):
    with Session(mem_engine) as session:
        session.add(_make_location_plan("loc-A"))
        session.add(_make_location_plan("loc-B"))
        for i in range(3):
            session.add(_make_item(name=f"Item {i}", name_pt=f"Item PT {i}", sort_order=i))
        session.commit()

        first = sync_location_benchmarks(session)
        second = sync_location_benchmarks(session)

        all_rows = session.exec(select(LocationBenchmark)).all()
    assert first == 6
    assert second == 0
    assert len(all_rows) == 6
