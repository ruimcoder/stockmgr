"""Tests for the enhanced GET /api/gap-analysis endpoint (#136)."""
from __future__ import annotations

from datetime import date, timedelta

import pytest


def _create_location_plan(client, location: str, participants: int = 2, days: int = 14):
    resp = client.post(
        "/location-plans",
        data={
            "_csrf_token": client.cookies.get("session", "test"),
            "location": location,
            "participants": participants,
            "stock_duration_days": days,
        },
        follow_redirects=False,
    )
    return resp


def test_api_gap_analysis_missing_location_param(client):
    """GET /api/gap-analysis without location param returns 400."""
    resp = client.get("/api/gap-analysis")
    assert resp.status_code == 400
    assert "location" in resp.json()["detail"].lower()


def test_api_gap_analysis_unknown_location_returns_404(client):
    """GET /api/gap-analysis?location=nonexistent returns 404."""
    resp = client.get("/api/gap-analysis?location=nonexistent_xyz")
    assert resp.status_code == 404


def test_api_gap_analysis_returns_envelope(client):
    """GET /api/gap-analysis?location=X returns structured envelope with summary and items."""
    loc = "TestGapLoc"
    _create_location_plan(client, loc, participants=2, days=7)

    resp = client.get(f"/api/gap-analysis?location={loc}")
    assert resp.status_code == 200

    data = resp.json()
    assert data["location"] == loc
    assert data["participants"] == 2
    assert data["stock_duration_days"] == 7
    assert "summary" in data
    assert "items" in data

    summary = data["summary"]
    assert "total_items" in summary
    assert "fully_stocked" in summary
    assert "partially_stocked" in summary
    assert "missing" in summary
    assert summary["total_items"] == summary["fully_stocked"] + summary["partially_stocked"] + summary["missing"]


def test_api_gap_analysis_items_have_required_fields(client):
    """Each item in /api/gap-analysis response has all required fields including new ones."""
    loc = "TestGapFields"
    _create_location_plan(client, loc, participants=1, days=7)

    resp = client.get(f"/api/gap-analysis?location={loc}")
    assert resp.status_code == 200

    data = resp.json()
    if data["items"]:
        item = data["items"][0]
        required_fields = {
            "benchmark_item_id", "name", "name_pt", "item_category",
            "non_food_category", "uom", "scales_with_participants", "qty_per_day",
            "target_stock", "current_stock", "gap", "coverage_pct",
            "days_covered", "status",
        }
        assert required_fields.issubset(item.keys()), f"Missing fields: {required_fields - item.keys()}"


def test_api_gap_analysis_items_sorted_by_coverage(client):
    """Items are sorted by coverage_pct ascending (worst gaps first)."""
    loc = "TestGapSort"
    _create_location_plan(client, loc, participants=1, days=7)

    resp = client.get(f"/api/gap-analysis?location={loc}")
    assert resp.status_code == 200

    items = resp.json()["items"]
    if len(items) > 1:
        coverages = [i["coverage_pct"] for i in items]
        assert coverages == sorted(coverages), "Items not sorted by coverage_pct ascending"


def test_api_gap_analysis_unauthenticated(client):
    """GET /api/gap-analysis without session returns 401."""
    from starlette.testclient import TestClient
    from app.main import app
    anon = TestClient(app, raise_server_exceptions=False)
    resp = anon.get("/api/gap-analysis?location=anywhere")
    assert resp.status_code in (401, 403)
