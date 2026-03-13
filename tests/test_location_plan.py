"""Tests for the Location Plan feature (issues #34 and #35)."""

import math

from sqlmodel import Session, select

from app.food_wheel import FOOD_GROUP_BY_KEY, FOOD_GROUPS
from app.models import LocationPlan

# ── Model computed properties ──────────────────────────────────────────────


def test_location_plan_main_meals_total():
    plan = LocationPlan(location="Garage", participants=4, stock_duration_days=30)
    assert plan.main_meals_total == 4 * 30 * 2  # 240


def test_location_plan_snack_meals_total():
    plan = LocationPlan(location="Garage", participants=4, stock_duration_days=30)
    assert plan.snack_meals_total == 4 * 30 * 2  # 240


def test_location_plan_total_meal_occasions():
    plan = LocationPlan(location="Garage", participants=4, stock_duration_days=30)
    assert plan.total_meal_occasions == 4 * 30 * 4  # 480


def test_location_plan_total_meal_occasions_single_person():
    plan = LocationPlan(location="Bunker", participants=1, stock_duration_days=7)
    assert plan.total_meal_occasions == 1 * 7 * 4  # 28


# ── Plan-based target computation ─────────────────────────────────────────


def test_plan_target_for_food_group():
    plan = LocationPlan(location="Garage", participants=4, stock_duration_days=30)
    fg = FOOD_GROUP_BY_KEY["cereais_tuberculos"]  # 28%
    expected = math.ceil(plan.total_meal_occasions * fg.target_pct / 100)
    assert expected == math.ceil(480 * 28 / 100)  # 135


def test_plan_target_all_food_groups_sum_approx_total():
    plan = LocationPlan(location="Test", participants=2, stock_duration_days=90)
    total = sum(
        math.ceil(plan.total_meal_occasions * fg.target_pct / 100) for fg in FOOD_GROUPS
    )
    # Due to rounding up, sum >= total_meal_occasions
    assert total >= plan.total_meal_occasions


# ── CRUD routes ────────────────────────────────────────────────────────────


def test_location_plans_page_loads(client):
    resp = client.get("/location-plans")
    assert resp.status_code == 200
    assert "location_plan" in resp.text or "plan" in resp.text.lower()


def test_location_plan_create(client):
    resp = client.post(
        "/location-plans",
        data={"location": "Garage", "participants": "4", "stock_duration_days": "30"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    # Verify in DB
    from app.db import engine

    with Session(engine) as session:
        plan = session.exec(
            select(LocationPlan).where(LocationPlan.location == "Garage")
        ).first()
    assert plan is not None
    assert plan.participants == 4
    assert plan.stock_duration_days == 30
    assert plan.total_meal_occasions == 480


def test_location_plan_create_upserts_on_same_location(client):
    client.post(
        "/location-plans",
        data={"location": "Garage", "participants": "4", "stock_duration_days": "30"},
        follow_redirects=False,
    )
    client.post(
        "/location-plans",
        data={"location": "Garage", "participants": "2", "stock_duration_days": "90"},
        follow_redirects=False,
    )
    from app.db import engine

    with Session(engine) as session:
        plans = session.exec(
            select(LocationPlan).where(LocationPlan.location == "Garage")
        ).all()
    assert len(plans) == 1
    assert plans[0].participants == 2
    assert plans[0].stock_duration_days == 90


def test_location_plan_delete(client):
    client.post(
        "/location-plans",
        data={"location": "Bunker", "participants": "1", "stock_duration_days": "7"},
        follow_redirects=False,
    )
    from app.db import engine

    with Session(engine) as session:
        plan = session.exec(
            select(LocationPlan).where(LocationPlan.location == "Bunker")
        ).first()
    assert plan is not None
    plan_id = plan.id

    resp = client.post(f"/location-plans/{plan_id}/delete", follow_redirects=False)
    assert resp.status_code == 303

    with Session(engine) as session:
        deleted = session.get(LocationPlan, plan_id)
    assert deleted is None


def test_location_plan_edit_page(client):
    client.post(
        "/location-plans",
        data={"location": "Cave", "participants": "3", "stock_duration_days": "14"},
        follow_redirects=False,
    )
    from app.db import engine

    with Session(engine) as session:
        plan = session.exec(
            select(LocationPlan).where(LocationPlan.location == "Cave")
        ).first()

    resp = client.get(f"/location-plans/{plan.id}/edit")
    assert resp.status_code == 200
    assert "Cave" in resp.text


def test_location_plan_update(client):
    client.post(
        "/location-plans",
        data={"location": "Cave", "participants": "3", "stock_duration_days": "14"},
        follow_redirects=False,
    )
    from app.db import engine

    with Session(engine) as session:
        plan = session.exec(
            select(LocationPlan).where(LocationPlan.location == "Cave")
        ).first()
    plan_id = plan.id

    resp = client.post(
        f"/location-plans/{plan_id}/update",
        data={"location": "Cave", "participants": "5", "stock_duration_days": "60"},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    with Session(engine) as session:
        updated = session.get(LocationPlan, plan_id)
    assert updated.participants == 5
    assert updated.stock_duration_days == 60
