"""Gap analysis calculation helpers."""
from __future__ import annotations

from app.models import BenchmarkItem, LocationBenchmark


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
