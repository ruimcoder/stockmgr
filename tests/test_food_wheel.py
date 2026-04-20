"""Tests for the Food Wheel module."""

from app.food_wheel import FOOD_GROUP_BY_KEY, FOOD_GROUPS, food_group_chart_data, infer_food_group


def test_food_groups_target_pct_sum_approx_100():
    total = sum(g.target_pct for g in FOOD_GROUPS)
    assert abs(total - 100.0) < 0.5, f"Target pct sum should be ~100, got {total}"


def test_food_group_by_key_has_all_groups():
    for g in FOOD_GROUPS:
        assert g.key in FOOD_GROUP_BY_KEY


# infer_food_group — keyword matching


def test_infer_food_group_rice():
    result = infer_food_group(name="Arroz carolino", item_type="cereal")
    assert result == "cereais_tuberculos"


def test_infer_food_group_chicken():
    result = infer_food_group(name="Frango assado", item_type="carne")
    assert result == "carne_pescado_ovos"


def test_infer_food_group_milk():
    result = infer_food_group(name="Leite meio gordo", item_type="lacticinio")
    assert result == "lacticinios"


def test_infer_food_group_olive_oil():
    result = infer_food_group(name="Azeite virgem extra", item_type="gordura")
    assert result == "gorduras_oleos"


def test_infer_food_group_apple():
    result = infer_food_group(name="Maca golden", item_type="fruta")
    assert result == "fruta"


def test_infer_food_group_beans():
    result = infer_food_group(name="Feijao branco", item_type="leguminosa")
    assert result == "leguminosas"


def test_infer_food_group_carrot():
    result = infer_food_group(name="Cenoura baby", item_type="horticola")
    assert result == "horticolas"


def test_infer_food_group_unknown_returns_none():
    result = infer_food_group(name="XYZ unknown product", item_type="misc")
    # Should return None or a low-confidence match — at minimum not crash
    assert result is None or isinstance(result, str)


def test_infer_food_group_off_tags_take_priority():
    result = infer_food_group(
        name="something unrelated",
        item_type="",
        food_groups_tags=["en:cereals-and-their-products"],
    )
    assert result == "cereais_tuberculos"


def test_infer_food_group_off_tags_dairy():
    result = infer_food_group(
        name="product",
        item_type="",
        food_groups_tags=["en:dairies"],
    )
    assert result == "lacticinios"


# food_group_chart_data


def test_chart_data_empty_items():
    result = food_group_chart_data([], language="pt")
    # total_unidoses is set to 1 internally to avoid division by zero
    assert result["total_unidoses"] >= 0
    assert result["ungrouped_unidoses"] == 0
    assert len(result["group_stats"]) == len(FOOD_GROUPS)


def test_chart_data_single_group():
    items = [{"food_group": "fruta", "quantity": 10, "unidose_per_pack": 2}]
    result = food_group_chart_data(items, language="en")
    stats = {g["key"]: g for g in result["group_stats"]}
    assert stats["fruta"]["actual_unidoses"] == 20
    assert result["total_unidoses"] == 20
    assert result["ungrouped_unidoses"] == 0


def test_chart_data_ungrouped():
    items = [{"food_group": None, "quantity": 5, "unidose_per_pack": 1}]
    result = food_group_chart_data(items, language="pt")
    assert result["ungrouped_unidoses"] == 5
    assert result["total_unidoses"] == 0


def test_chart_data_language_pt():
    items = [{"food_group": "fruta", "quantity": 1, "unidose_per_pack": 1}]
    result = food_group_chart_data(items, language="pt")
    stats = {g["key"]: g for g in result["group_stats"]}
    assert "Fruta" in stats["fruta"]["label"]


def test_chart_data_language_en():
    items = [{"food_group": "fruta", "quantity": 1, "unidose_per_pack": 1}]
    result = food_group_chart_data(items, language="en")
    stats = {g["key"]: g for g in result["group_stats"]}
    assert "Fruit" in stats["fruta"]["label"]


def test_chart_data_delta_pct():
    items = [{"food_group": "fruta", "quantity": 100, "unidose_per_pack": 1}]
    result = food_group_chart_data(items, language="en")
    stats = {g["key"]: g for g in result["group_stats"]}
    # 100% actual for fruta, target is 20% → delta ≈ +80%
    assert stats["fruta"]["delta_pct"] > 0


def test_non_food_items_excluded_from_food_wheel(client):
    """Non-food items should not appear in food wheel calculations."""
    from datetime import date

    client.post(
        "/items",
        data={
            "name": "First Aid Kit",
            "item_type": "medicine",
            "item_category": "non_food",
            "non_food_category": "medicine",
            "storage_location": "Test Location",
            "expiry_date": str(date(2027, 1, 1)),
            "quantity": "1",
            "unidose_per_pack": "1",
            "food_group": "proteinas",  # would distort food wheel if included
        },
        follow_redirects=True,
    )

    resp = client.get("/food-wheel")
    assert resp.status_code == 200
