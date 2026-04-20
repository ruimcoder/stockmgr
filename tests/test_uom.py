"""Tests for UOM constants and form integration."""


def test_uom_constants():
    from app.uom_constants import UOM_OPTIONS, UOM_KEYS

    assert "L" in UOM_OPTIONS
    assert "kg" in UOM_OPTIONS
    assert "dose" in UOM_OPTIONS
    assert len(UOM_OPTIONS) == 10
    assert "L" in UOM_KEYS


def test_uom_options_have_en_and_pt_labels():
    from app.uom_constants import UOM_OPTIONS

    for key, labels in UOM_OPTIONS.items():
        assert "en" in labels, f"Missing EN label for {key}"
        assert "pt" in labels, f"Missing PT label for {key}"
        assert labels["en"], f"Empty EN label for {key}"
        assert labels["pt"], f"Empty PT label for {key}"


def test_normalize_uom_aliases():
    from app.uom_constants import normalize_uom

    assert normalize_uom("kg") == "kg"
    assert normalize_uom("litros") == "L"
    assert normalize_uom("ml") == "mL"
    assert normalize_uom("unidades") == "unit"
    assert normalize_uom("rolos") == "roll"
    assert normalize_uom("kwh") == "kWh"
    assert normalize_uom(None) is None
    assert normalize_uom("") is None
    assert normalize_uom("unknown_uom") == "unknown_uom"


def test_uom_options_injected_in_form(client):
    """Item form GET renders UOM select dropdown."""
    resp = client.get("/items/new")
    assert resp.status_code == 200
    assert 'name="uom"' in resp.text
    assert "<select" in resp.text
    assert "Litres" in resp.text or "Litros" in resp.text


def test_uom_preserved_on_edit(client):
    """Edit form pre-selects existing UOM value."""
    resp = client.post(
        "/items",
        data={
            "name": "Rice",
            "item_type": "grain",
            "item_category": "food",
            "storage_location": "Pantry",
            "expiry_date": "2027-01-01",
            "quantity": "5",
            "unidose_per_pack": "1",
            "uom": "kg",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    from sqlmodel import Session, select as sqlselect
    from app.db import engine
    from app.models import StockItem

    with Session(engine) as session:
        item = session.exec(sqlselect(StockItem).where(StockItem.name == "Rice")).first()
    assert item is not None
    assert item.uom == "kg"

    resp3 = client.get(f"/items/{item.id}/edit")
    assert resp3.status_code == 200
    assert 'value="kg"' in resp3.text
    assert "selected" in resp3.text