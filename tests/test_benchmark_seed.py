"""Tests for BenchmarkItem model and seed data."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.benchmark_seed import seed_benchmark_if_empty
from app.models import BenchmarkItem


@pytest.fixture()
def mem_engine():
    """In-memory SQLite engine with all tables created fresh."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)


def test_seed_inserts_items_on_empty_db(mem_engine):
    with Session(mem_engine) as session:
        count = seed_benchmark_if_empty(session)
    assert count > 25, f"Expected >25 items seeded, got {count}"


def test_seed_is_idempotent(mem_engine):
    with Session(mem_engine) as session:
        first = seed_benchmark_if_empty(session)
        second = seed_benchmark_if_empty(session)
    assert first > 0
    assert second == 0
    with Session(mem_engine) as session:
        all_items = session.exec(select(BenchmarkItem)).all()
    assert len(all_items) == first


def test_benchmark_item_has_required_fields(mem_engine):
    with Session(mem_engine) as session:
        seed_benchmark_if_empty(session)
        food_items = session.exec(
            select(BenchmarkItem).where(BenchmarkItem.item_category == "food")
        ).all()
        non_food_items = session.exec(
            select(BenchmarkItem).where(BenchmarkItem.item_category == "non_food")
        ).all()
    assert len(food_items) > 0, "Expected at least one food item"
    assert len(non_food_items) > 0, "Expected at least one non_food item"
    for item in food_items + non_food_items:
        assert item.name, "Item must have a name"
        assert item.name_pt, "Item must have a PT name"
        assert item.uom, "Item must have a UOM"
        assert item.qty_per_day >= 0, "qty_per_day must be non-negative"


def test_scales_with_participants_flag(mem_engine):
    with Session(mem_engine) as session:
        seed_benchmark_if_empty(session)
        scales_true = session.exec(
            select(BenchmarkItem).where(BenchmarkItem.scales_with_participants == True)  # noqa: E712
        ).all()
        scales_false = session.exec(
            select(BenchmarkItem).where(BenchmarkItem.scales_with_participants == False)  # noqa: E712
        ).all()
    assert len(scales_true) > 0, "Expected items with scales_with_participants=True (water, rice…)"
    assert len(scales_false) > 0, "Expected items with scales_with_participants=False (fuel, candles…)"
    scales_true_names = {i.name for i in scales_true}
    scales_false_names = {i.name for i in scales_false}
    assert "Drinking water" in scales_true_names
    assert "Rice" in scales_true_names
    assert "Fuel (generator)" in scales_false_names
    assert "Candles" in scales_false_names
