"""Tests for optional expiry_date on non-food items (#123)."""
import pytest
from app.schemas import ItemBase

REQUIRED_BASE = {"name":"Test","item_type":"test","storage_location":"Loc","quantity":1,"unidose_per_pack":1}

def test_food_item_requires_expiry():
    from pydantic import ValidationError
    with pytest.raises(ValidationError, match="expiry_date"):
        ItemBase(**{**REQUIRED_BASE,"item_category":"food","expiry_date":None})

def test_medicine_requires_expiry():
    from pydantic import ValidationError
    with pytest.raises(ValidationError, match="expiry_date"):
        ItemBase(**{**REQUIRED_BASE,"item_category":"non_food","non_food_category":"medicine","expiry_date":None})

def test_seeds_require_expiry():
    from pydantic import ValidationError
    with pytest.raises(ValidationError, match="expiry_date"):
        ItemBase(**{**REQUIRED_BASE,"item_category":"non_food","non_food_category":"seeds","expiry_date":None})

def test_energy_requires_expiry():
    from pydantic import ValidationError
    with pytest.raises(ValidationError, match="expiry_date"):
        ItemBase(**{**REQUIRED_BASE,"item_category":"non_food","non_food_category":"energy","expiry_date":None})

def test_tools_no_expiry_ok():
    item = ItemBase(**{**REQUIRED_BASE,"item_category":"non_food","non_food_category":"tools","expiry_date":None})
    assert item.expiry_date is None

def test_hygiene_no_expiry_ok():
    item = ItemBase(**{**REQUIRED_BASE,"item_category":"non_food","non_food_category":"hygiene","expiry_date":None})
    assert item.expiry_date is None

def test_communication_no_expiry_ok():
    item = ItemBase(**{**REQUIRED_BASE,"item_category":"non_food","non_food_category":"communication","expiry_date":None})
    assert item.expiry_date is None

def test_food_with_expiry_ok():
    from datetime import date
    item = ItemBase(**{**REQUIRED_BASE,"item_category":"food","expiry_date":date(2027,1,1)})
    assert item.expiry_date == date(2027,1,1)

def test_default_category_food_requires_expiry():
    from pydantic import ValidationError
    with pytest.raises(ValidationError, match="expiry_date"):
        ItemBase(**{**REQUIRED_BASE,"expiry_date":None})

def test_tools_post_endpoint(client):
    resp = client.post("/items",data={"name":"Axe","item_type":"tool","item_category":"non_food",
        "non_food_category":"tools","storage_location":"Test Location","quantity":"1",
        "unidose_per_pack":"1","loc_location":"Test Location","loc_expiry":"","loc_quantity":"1"},
        follow_redirects=False)
    assert resp.status_code in (200,302,303)
