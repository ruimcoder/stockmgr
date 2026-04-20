"""Unit of Measure constants with EN/PT translations."""
from __future__ import annotations

UOM_OPTIONS: dict[str, dict[str, str]] = {
    # Volume
    "L":    {"en": "Litres (L)",            "pt": "Litros (L)"},
    "mL":   {"en": "Millilitres (mL)",      "pt": "Mililitros (mL)"},
    # Weight
    "kg":   {"en": "Kilograms (kg)",        "pt": "Quilogramas (kg)"},
    "g":    {"en": "Grams (g)",             "pt": "Gramas (g)"},
    # Count / pack
    "unit": {"en": "Units",                 "pt": "Unidades"},
    "pack": {"en": "Packs",                 "pt": "Embalagens"},
    "dose": {"en": "Doses",                 "pt": "Doses"},
    "roll": {"en": "Rolls",                 "pt": "Rolos"},
    # Area
    "m2":   {"en": "Square metres (m2)",    "pt": "Metros quadrados (m2)"},
    # Energy
    "kWh":  {"en": "Kilowatt-hours (kWh)",  "pt": "Quilowatt-hora (kWh)"},
}

UOM_KEYS = list(UOM_OPTIONS.keys())

UOM_ALIASES: dict[str, str] = {
    "litros": "L", "lts": "L", "liters": "L", "litres": "L", "l": "L",
    "ml": "mL", "millilitres": "mL", "milliliters": "mL",
    "kg": "kg", "kilograms": "kg", "quilogramas": "kg",
    "g": "g", "grams": "g", "gramas": "g", "gr": "g",
    "unit": "unit", "units": "unit", "unidade": "unit", "unidades": "unit",
    "pack": "pack", "packs": "pack", "embalagem": "pack", "embalagens": "pack",
    "dose": "dose", "doses": "dose",
    "roll": "roll", "rolls": "roll", "rolo": "roll", "rolos": "roll",
    "m2": "m2",
    "kwh": "kWh",
}


def normalize_uom(raw: str | None) -> str | None:
    if not raw:
        return None
    return UOM_ALIASES.get(raw.strip().lower(), raw)