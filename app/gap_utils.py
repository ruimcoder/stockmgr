"""Gap analysis calculation helpers."""
from __future__ import annotations

from app.models import BenchmarkItem, LocationBenchmark, StockItem


def get_target_qty(
    benchmark_item: BenchmarkItem,
    location_override: LocationBenchmark | None,
    participants: int,
    stock_duration_days: int,
) -> float:
    """Calculate target quantity for a benchmark item at a location.

    Returns 0.0 if the item is disabled for the location.
    Uses qty_override if set, otherwise uses benchmark_item.qty_per_day.
    Scales by participants if benchmark_item.scales_with_participants is True.
    """
    if location_override is not None and not location_override.is_enabled:
        return 0.0
    qty_per_day = (
        location_override.qty_override
        if (location_override and location_override.qty_override is not None)
        else benchmark_item.qty_per_day
    )
    if benchmark_item.scales_with_participants:
        return qty_per_day * participants * stock_duration_days
    return qty_per_day * stock_duration_days


def compute_gap_rows(
    benchmark_items: list,
    lb_map: dict,
    stock_items: list,
    participants: int,
    stock_duration_days: int,
) -> list[dict]:
    """Compute gap analysis rows for a location.

    Matching strategy:
    - non_food items: match StockItems where non_food_category == benchmark_item.non_food_category
    - food items: match StockItems where item_category == 'food' OR item_category is None (legacy)

    Returns list of dicts with keys:
      benchmark_item, lb, target_qty, current_stock, gap, coverage_pct, days_covered, status
    where status is "ok" (>=100%), "partial" (>=10%), or "missing" (<10%)
    """
    rows = []
    for b_item in benchmark_items:
        lb = lb_map.get(b_item.id)
        if lb is not None and not lb.is_enabled:
            continue  # skip disabled items

        target_qty = get_target_qty(b_item, lb, participants, stock_duration_days)
        daily_need = get_target_qty(b_item, lb, participants, 1)

        # Match stock items
        if b_item.item_category == "non_food" and b_item.non_food_category:
            matched = [s for s in stock_items if s.non_food_category == b_item.non_food_category]
        else:
            matched = [s for s in stock_items if s.item_category == "food" or s.item_category is None]

        current_stock = sum(
            (s.quantity or 0) * (s.unidose_per_pack or 1)
            for s in matched
        )

        if target_qty > 0:
            coverage_pct = min(100.0, (current_stock / target_qty) * 100)
            days_covered = current_stock / daily_need if daily_need > 0 else 0.0
        else:
            coverage_pct = 100.0
            days_covered = float(stock_duration_days)

        if coverage_pct >= 100:
            status = "ok"
        elif coverage_pct >= 10:
            status = "partial"
        else:
            status = "missing"

        rows.append({
            "benchmark_item": b_item,
            "lb": lb,
            "target_qty": round(target_qty, 3),
            "current_stock": round(current_stock, 3),
            "gap": round(max(0.0, target_qty - current_stock), 3),
            "coverage_pct": round(coverage_pct, 1),
            "days_covered": round(days_covered, 1),
            "status": status,
        })

    rows.sort(key=lambda r: r["coverage_pct"])
    return rows
