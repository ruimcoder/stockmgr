"""Idempotent seeder for BenchmarkItem curated prepper data."""
from __future__ import annotations

from app.models import BenchmarkItem
from sqlmodel import Session, select


def seed_benchmark_if_empty(session: Session) -> int:
    """Insert benchmark items if the table is empty. Returns count inserted."""
    existing = session.exec(select(BenchmarkItem)).first()
    if existing:
        return 0
    items = _get_seed_data()
    for item in items:
        session.add(item)
    session.commit()
    return len(items)


def _get_seed_data() -> list[BenchmarkItem]:  # noqa: PLR0915
    return [
        # ── Water ──────────────────────────────────────────────────────────────
        BenchmarkItem(
            name="Drinking water", name_pt="Água potável",
            item_category="food", qty_per_day=2.0, uom="L",
            scales_with_participants=True,
            notes="Minimum 2L; 4L recommended including cooking",
            notes_pt="Mínimo 2L; 4L recomendado incluindo cozinha",
            sort_order=0,
        ),
        BenchmarkItem(
            name="Water purification tablets", name_pt="Comprimidos purificação água",
            item_category="food", qty_per_day=2.0, uom="unit",
            scales_with_participants=True, sort_order=1,
        ),
        # ── Food ───────────────────────────────────────────────────────────────
        BenchmarkItem(
            name="Rice", name_pt="Arroz",
            item_category="food", qty_per_day=0.2, uom="kg",
            scales_with_participants=True, sort_order=2,
        ),
        BenchmarkItem(
            name="Legumes (beans/lentils)", name_pt="Leguminosas (feijão/lentilhas)",
            item_category="food", qty_per_day=0.1, uom="kg",
            scales_with_participants=True, sort_order=3,
        ),
        BenchmarkItem(
            name="Cooking oil", name_pt="Óleo de cozinha",
            item_category="food", qty_per_day=0.04, uom="L",
            scales_with_participants=True, sort_order=4,
        ),
        BenchmarkItem(
            name="Salt", name_pt="Sal",
            item_category="food", qty_per_day=0.01, uom="kg",
            scales_with_participants=True, sort_order=5,
        ),
        BenchmarkItem(
            name="Sugar", name_pt="Açúcar",
            item_category="food", qty_per_day=0.05, uom="kg",
            scales_with_participants=True, sort_order=6,
        ),
        BenchmarkItem(
            name="Flour", name_pt="Farinha",
            item_category="food", qty_per_day=0.15, uom="kg",
            scales_with_participants=True, sort_order=7,
        ),
        BenchmarkItem(
            name="Canned vegetables", name_pt="Vegetais em lata",
            item_category="food", qty_per_day=1.0, uom="unit",
            scales_with_participants=True, sort_order=8,
        ),
        BenchmarkItem(
            name="Canned fish/meat", name_pt="Peixe/carne em lata",
            item_category="food", qty_per_day=1.0, uom="unit",
            scales_with_participants=True, sort_order=9,
        ),
        BenchmarkItem(
            name="Dried fruit/nuts", name_pt="Frutos secos",
            item_category="food", qty_per_day=0.05, uom="kg",
            scales_with_participants=True, sort_order=10,
        ),
        BenchmarkItem(
            name="Honey", name_pt="Mel",
            item_category="food", qty_per_day=0.02, uom="kg",
            scales_with_participants=True, sort_order=11,
        ),
        # ── Medicine ───────────────────────────────────────────────────────────
        BenchmarkItem(
            name="Paracetamol 500mg", name_pt="Paracetamol 500mg",
            item_category="non_food", non_food_category="medicine",
            qty_per_day=2.0, uom="dose",
            scales_with_participants=True, sort_order=12,
        ),
        BenchmarkItem(
            name="Ibuprofen 400mg", name_pt="Ibuprofeno 400mg",
            item_category="non_food", non_food_category="medicine",
            qty_per_day=2.0, uom="dose",
            scales_with_participants=True, sort_order=13,
        ),
        BenchmarkItem(
            name="Oral rehydration salts", name_pt="Sais de rehidratação oral",
            item_category="non_food", non_food_category="medicine",
            qty_per_day=1.0, uom="pack",
            scales_with_participants=True, sort_order=14,
        ),
        BenchmarkItem(
            name="Antiseptic solution", name_pt="Solução antisséptica",
            item_category="non_food", non_food_category="medicine",
            qty_per_day=0.01, uom="L",
            scales_with_participants=False, sort_order=15,
        ),
        BenchmarkItem(
            name="Bandages (sterile)", name_pt="Ligaduras (estéreis)",
            item_category="non_food", non_food_category="medicine",
            qty_per_day=0.1, uom="unit",
            scales_with_participants=True, sort_order=16,
        ),
        # ── Hygiene ────────────────────────────────────────────────────────────
        BenchmarkItem(
            name="Toilet paper", name_pt="Papel higiénico",
            item_category="non_food", non_food_category="hygiene",
            qty_per_day=0.14, uom="roll",
            scales_with_participants=True, sort_order=17,
        ),
        BenchmarkItem(
            name="Soap (bar)", name_pt="Sabão (barra)",
            item_category="non_food", non_food_category="hygiene",
            qty_per_day=0.033, uom="unit",
            scales_with_participants=True, sort_order=18,
        ),
        BenchmarkItem(
            name="Toothpaste", name_pt="Pasta de dentes",
            item_category="non_food", non_food_category="hygiene",
            qty_per_day=0.007, uom="unit",
            scales_with_participants=True, sort_order=19,
        ),
        BenchmarkItem(
            name="Hand sanitiser", name_pt="Gel desinfetante",
            item_category="non_food", non_food_category="hygiene",
            qty_per_day=0.01, uom="L",
            scales_with_participants=True, sort_order=20,
        ),
        # ── Energy ─────────────────────────────────────────────────────────────
        BenchmarkItem(
            name="Fuel (generator)", name_pt="Combustível (gerador)",
            item_category="non_food", non_food_category="energy",
            qty_per_day=0.3, uom="L",
            scales_with_participants=False,
            notes="Per kWh produced; household level",
            notes_pt="Por kWh produzido; nível doméstico",
            sort_order=21,
        ),
        BenchmarkItem(
            name="Candles", name_pt="Velas",
            item_category="non_food", non_food_category="energy",
            qty_per_day=2.0, uom="unit",
            scales_with_participants=False, sort_order=22,
        ),
        BenchmarkItem(
            name="Batteries (AA)", name_pt="Pilhas AA",
            item_category="non_food", non_food_category="energy",
            qty_per_day=0.1, uom="unit",
            scales_with_participants=False, sort_order=23,
        ),
        BenchmarkItem(
            name="Firewood/charcoal", name_pt="Lenha/carvão",
            item_category="non_food", non_food_category="energy",
            qty_per_day=2.0, uom="kg",
            scales_with_participants=False, sort_order=24,
        ),
        # ── Seeds ──────────────────────────────────────────────────────────────
        BenchmarkItem(
            name="Tomato seeds", name_pt="Sementes de tomate",
            item_category="non_food", non_food_category="seeds",
            qty_per_day=0.011, uom="pack",
            scales_with_participants=False, sort_order=25,
        ),
        BenchmarkItem(
            name="Potato seeds", name_pt="Batata-semente",
            item_category="non_food", non_food_category="seeds",
            qty_per_day=0.055, uom="kg",
            scales_with_participants=False, sort_order=26,
        ),
        BenchmarkItem(
            name="Bean seeds", name_pt="Sementes de feijão",
            item_category="non_food", non_food_category="seeds",
            qty_per_day=0.022, uom="kg",
            scales_with_participants=False, sort_order=27,
        ),
        BenchmarkItem(
            name="Root vegetable seeds", name_pt="Sementes de raízes",
            item_category="non_food", non_food_category="seeds",
            qty_per_day=0.011, uom="pack",
            scales_with_participants=False, sort_order=28,
        ),
        # ── Tools ──────────────────────────────────────────────────────────────
        BenchmarkItem(
            name="Multi-tool", name_pt="Canivete/ferramenta",
            item_category="non_food", non_food_category="tools",
            qty_per_day=0.003, uom="unit",
            scales_with_participants=False, sort_order=29,
        ),
        BenchmarkItem(
            name="Axe/hatchet", name_pt="Machado/machadinha",
            item_category="non_food", non_food_category="tools",
            qty_per_day=0.003, uom="unit",
            scales_with_participants=False, sort_order=30,
        ),
        BenchmarkItem(
            name="Rope (paracord 50m)", name_pt="Corda (paracord 50m)",
            item_category="non_food", non_food_category="tools",
            qty_per_day=0.003, uom="unit",
            scales_with_participants=False, sort_order=31,
        ),
        BenchmarkItem(
            name="Flashlight", name_pt="Lanterna",
            item_category="non_food", non_food_category="tools",
            qty_per_day=0.003, uom="unit",
            scales_with_participants=True, sort_order=32,
        ),
        # ── Communication ──────────────────────────────────────────────────────
        BenchmarkItem(
            name="Hand-crank radio", name_pt="Rádio de manivela",
            item_category="non_food", non_food_category="communication",
            qty_per_day=0.003, uom="unit",
            scales_with_participants=False, sort_order=33,
        ),
        BenchmarkItem(
            name="Walkie-talkies (pair)", name_pt="Walkie-talkies (par)",
            item_category="non_food", non_food_category="communication",
            qty_per_day=0.003, uom="unit",
            scales_with_participants=False, sort_order=34,
        ),
    ]
