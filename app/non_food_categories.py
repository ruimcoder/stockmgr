"""Non-food item category constants with EN/PT translations."""

from __future__ import annotations

NON_FOOD_CATEGORIES: dict[str, dict[str, str]] = {
    "medicine":      {"en": "Medicine",      "pt": "Medicina"},
    "energy":        {"en": "Energy",        "pt": "Energia"},
    "tools":         {"en": "Tools",         "pt": "Ferramentas"},
    "hygiene":       {"en": "Hygiene",       "pt": "Higiene"},
    "seeds":         {"en": "Seeds",         "pt": "Sementes"},
    "communication": {"en": "Communication", "pt": "Comunicação"},
    "security":      {"en": "Security",      "pt": "Segurança"},
    "other":         {"en": "Other",         "pt": "Outro"},
}

ITEM_CATEGORIES: dict[str, dict[str, str]] = {
    "food":     {"en": "Food",     "pt": "Alimentar"},
    "non_food": {"en": "Non-food", "pt": "Não-alimentar"},
}

NON_FOOD_CATEGORY_KEYS = list(NON_FOOD_CATEGORIES.keys())
ITEM_CATEGORY_KEYS = list(ITEM_CATEGORIES.keys())
