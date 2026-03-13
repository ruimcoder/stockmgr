"""Portuguese Food Wheel (Roda dos Alimentos) - food group definitions, inference logic."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field


@dataclass(frozen=True)
class FoodGroup:
    key: str
    name_pt: str
    name_en: str
    color: str
    target_pct: float  # DGS recommended proportion (%)
    keywords: frozenset[str] = field(default_factory=frozenset)
    off_tags: frozenset[str] = field(default_factory=frozenset)  # OpenFoodFacts food_groups_tags


# Official Portuguese Food Wheel groups with DGS proportions
FOOD_GROUPS: list[FoodGroup] = [
    FoodGroup(
        key="cereais_tuberculos",
        name_pt="Cereais e derivados, tubérculos",
        name_en="Cereals, derivatives & tubers",
        color="#F5C842",
        target_pct=28.0,
        keywords=frozenset(
            [
                "cereal", "cereais", "arroz", "rice", "massa", "pasta", "pao", "bread", "batata",
                "potato", "tuberculo", "trigo", "wheat", "aveia", "oats", "centeio", "rye",
                "milho", "corn", "farinha", "flour", "bolacha", "biscoito", "biscuit", "cookie",
                "crackers", "tosta", "toast", "cuscus", "couscous", "quinoa", "espelta", "spelt",
                "granola", "muesli", "flocos", "flakes", "tapioca", "semola", "semolina",
                "noodles", "macarrao", "spaghetti", "lasanha", "lasagna",
            ]
        ),
        off_tags=frozenset(
            [
                "en:cereals-and-their-products",
                "en:grains",
                "en:breads",
                "en:pastas",
                "en:potatoes",
                "en:starchy-foods",
                "en:tubers",
            ]
        ),
    ),
    FoodGroup(
        key="horticolas",
        name_pt="Hortícolas",
        name_en="Vegetables",
        color="#4C9A2A",
        target_pct=23.0,
        keywords=frozenset(
            [
                "horticola", "vegetal", "vegetais", "legume", "salada", "salad", "cenoura",
                "carrot", "espinafre", "spinach", "alface", "lettuce", "tomate", "tomato",
                "pepino", "cucumber", "cebola", "onion", "alho", "garlic", "brocolo", "broccoli",
                "courgette", "zucchini", "pimento", "pepper", "beringela", "eggplant",
                "couve", "cabbage", "nabo", "turnip", "beterraba", "beetroot", "aipo", "celery",
                "alho-frances", "leek", "cogumelo", "mushroom", "espargo", "asparagus",
                "abobora", "pumpkin", "squash", "feijao-verde", "green-beans", "pissarra",
                "ervilha-torta", "snap-pea", "rabanete", "radish", "endivias", "endive",
                "grelos", "agriao", "watercress", "rucula", "arugula", "rocketleaf",
            ]
        ),
        off_tags=frozenset(
            [
                "en:vegetables",
                "en:vegetables-based-foods",
                "en:fresh-vegetables",
                "en:salads",
                "en:greens",
            ]
        ),
    ),
    FoodGroup(
        key="fruta",
        name_pt="Fruta",
        name_en="Fruit",
        color="#E85E1E",
        target_pct=20.0,
        keywords=frozenset(
            [
                "fruta", "fruit", "maca", "apple", "pera", "pear", "laranja", "orange",
                "banana", "uva", "grape", "morango", "strawberry", "kiwi", "manga", "mango",
                "ananás", "ananas", "pineapple", "melao", "melon", "melancia", "watermelon",
                "cereja", "cherry", "pessego", "peach", "ameixa", "plum", "figo", "fig",
                "abacate", "avocado", "limao", "lemon", "lima", "lime", "toranja", "grapefruit",
                "framboesa", "raspberry", "mirtilo", "blueberry", "groselha", "currant",
                "papaia", "papaya", "coco", "coconut", "dátil", "date", "passas", "raisins",
            ]
        ),
        off_tags=frozenset(
            [
                "en:fruits",
                "en:fruits-based-foods",
                "en:fresh-fruits",
                "en:dried-fruits",
                "en:fruit-juices",
            ]
        ),
    ),
    FoodGroup(
        key="lacticinios",
        name_pt="Lacticínios",
        name_en="Dairy",
        color="#4DA8DA",
        target_pct=18.0,
        keywords=frozenset(
            [
                "lacticinio", "dairy", "leite", "milk", "queijo", "cheese", "iogurte",
                "yogurt", "yoghurt", "manteiga", "butter", "natas", "cream", "creme",
                "requeijao", "ricotta", "mozzarella", "parmesao", "parmesan", "brie",
                "camembert", "gouda", "edam", "cottage", "kefir", "skyr",
            ]
        ),
        off_tags=frozenset(
            [
                "en:dairies",
                "en:dairy-products",
                "en:milks",
                "en:cheeses",
                "en:yogurts",
                "en:fermented-milk-products",
            ]
        ),
    ),
    FoodGroup(
        key="carne_pescado_ovos",
        name_pt="Carne, pescado e ovos",
        name_en="Meat, fish & eggs",
        color="#C0392B",
        target_pct=5.0,
        keywords=frozenset(
            [
                "carne", "meat", "frango", "chicken", "peru", "turkey", "vaca", "beef",
                "porco", "pork", "cordeiro", "lamb", "vitela", "veal", "pato", "duck",
                "coelho", "rabbit", "peixe", "fish", "atum", "tuna", "salmao", "salmon",
                "bacalhau", "cod", "sardinha", "sardine", "cavala", "mackerel", "dourada",
                "sea-bass", "robalo", "camarao", "shrimp", "prawn", "lagosta", "lobster",
                "carangueijo", "crab", "mexilhao", "mussel", "amêijoa", "clam", "lulas",
                "squid", "polvo", "octopus", "ovos", "eggs", "ovo", "egg", "fiambre", "ham",
                "presunto", "salpicao", "chourizo", "linguiça", "mortadela",
            ]
        ),
        off_tags=frozenset(
            [
                "en:meats",
                "en:meat-products",
                "en:fish-and-seafood",
                "en:fishes",
                "en:seafood",
                "en:eggs",
                "en:poultry",
            ]
        ),
    ),
    FoodGroup(
        key="leguminosas",
        name_pt="Leguminosas",
        name_en="Legumes",
        color="#8B6914",
        target_pct=4.0,
        keywords=frozenset(
            [
                "leguminosa", "legume", "feijao", "bean", "beans", "grao", "chickpea",
                "lentilha", "lentil", "fava", "broad-bean", "ervilha", "pea", "peas",
                "soja", "soy", "soybean", "tofu", "tempeh", "edamame", "lupin", "lupino",
            ]
        ),
        off_tags=frozenset(
            [
                "en:legumes",
                "en:pulses",
                "en:beans",
                "en:lentils",
                "en:chickpeas",
                "en:peas",
            ]
        ),
    ),
    FoodGroup(
        key="gorduras_oleos",
        name_pt="Gorduras e óleos",
        name_en="Fats & oils",
        color="#D4AC0D",
        target_pct=2.0,
        keywords=frozenset(
            [
                "gordura", "fat", "oleo", "oil", "azeite", "olive-oil", "margarina",
                "margarine", "banha", "lard", "óleo", "girassol", "sunflower",
                "colza", "rapeseed", "sésamo", "sesame", "coco-oil", "coconut-oil",
            ]
        ),
        off_tags=frozenset(
            [
                "en:fats",
                "en:oils",
                "en:vegetable-oils",
                "en:animal-fats",
            ]
        ),
    ),
]

FOOD_GROUP_BY_KEY: dict[str, FoodGroup] = {g.key: g for g in FOOD_GROUPS}


def _normalize(text: str) -> str:
    """Lowercase, strip accents, remove punctuation."""
    nfkd = unicodedata.normalize("NFKD", text.lower())
    ascii_text = "".join(c for c in nfkd if not unicodedata.combining(c))
    return ascii_text.replace("-", " ").replace("_", " ").strip()


def infer_food_group(
    name: str,
    item_type: str | None = None,
    food_groups_tags: list[str] | None = None,
) -> str | None:
    """Infer food group key from product data.

    Priority:
    1. OpenFoodFacts food_groups_tags (most authoritative)
    2. Keyword matching on item name
    3. Keyword matching on item_type
    Returns None if no confident match found.
    """
    # 1. Try OpenFoodFacts food_groups_tags
    if food_groups_tags:
        for tag in food_groups_tags:
            tag_lower = tag.lower()
            for group in FOOD_GROUPS:
                if any(off_tag in tag_lower for off_tag in group.off_tags):
                    return group.key

    # 2. Keyword matching — score each group by number of keyword hits
    texts = [_normalize(t) for t in [name, item_type or ""] if t]
    combined = " ".join(texts)
    tokens = set(combined.split())

    best_key: str | None = None
    best_score = 0

    for group in FOOD_GROUPS:
        score = sum(
            1 for kw in group.keywords
            if kw in combined or kw in tokens
        )
        if score > best_score:
            best_score = score
            best_key = group.key

    return best_key if best_score > 0 else None


def food_group_chart_data(
    items: list[dict],
    language: str = "pt",
) -> dict:
    """Build chart data for the food wheel visualization.

    items: list of dicts with keys: food_group, quantity, unidose_per_pack
    Returns data for a Chart.js doughnut chart comparing actual vs target distribution.
    """
    # Aggregate unidoses per food group
    actual: dict[str, float] = {g.key: 0.0 for g in FOOD_GROUPS}
    ungrouped_unidoses = 0.0

    for item in items:
        key = item.get("food_group")
        qty = int(item.get("quantity") or 0)
        udp = int(item.get("unidose_per_pack") or 1)
        unidoses = qty * udp
        if key and key in actual:
            actual[key] += unidoses
        else:
            ungrouped_unidoses += unidoses

    total_unidoses = sum(actual.values()) + ungrouped_unidoses
    if total_unidoses == 0:
        total_unidoses = 1  # avoid division by zero

    labels = []
    actual_pcts = []
    target_pcts = []
    colors = []
    group_stats = []

    for group in FOOD_GROUPS:
        label = group.name_pt if language == "pt" else group.name_en
        labels.append(label)
        a_pct = round(actual[group.key] / total_unidoses * 100, 1)
        actual_pcts.append(a_pct)
        target_pcts.append(group.target_pct)
        colors.append(group.color)
        group_stats.append(
            {
                "key": group.key,
                "label": label,
                "color": group.color,
                "actual_unidoses": actual[group.key],
                "actual_pct": a_pct,
                "target_pct": group.target_pct,
                "delta_pct": round(a_pct - group.target_pct, 1),
            }
        )

    return {
        "labels": labels,
        "actual_pcts": actual_pcts,
        "target_pcts": target_pcts,
        "colors": colors,
        "group_stats": group_stats,
        "total_unidoses": total_unidoses - ungrouped_unidoses,
        "ungrouped_unidoses": ungrouped_unidoses,
    }
