from app.services.imports import parse_import_file


def test_parse_csv_import():
    csv_bytes = (
        b"name,item_type,storage_location,batch_code,expiry_date,renewal_date\n"
        b"Rice,food,Shelf A,LOT-R1,2030-01-01,2029-12-01\n"
    )
    items, result = parse_import_file(csv_bytes, "items.csv")
    assert result.imported == 1
    assert result.failed == 0
    assert items[0].name == "Rice"
    assert items[0].batch_code == "LOT-R1"


def test_parse_excel_import():
    from io import BytesIO

    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.append(
        ["name", "item_type", "storage_location", "batch_code", "expiry_date", "renewal_date"]
    )
    sheet.append(["Flour", "food", "Pantry", "LOT-F1", "2030-06-01", "2030-05-01"])
    stream = BytesIO()
    workbook.save(stream)
    items, result = parse_import_file(stream.getvalue(), "items.xlsx")
    assert result.imported == 1
    assert result.failed == 0
    assert items[0].name == "Flour"
    assert items[0].batch_code == "LOT-F1"


def test_parse_import_requires_expiry_date():
    csv_bytes = b"name,item_type,storage_location\nRice,food,Shelf A\n"
    items, result = parse_import_file(csv_bytes, "items.csv")
    assert len(items) == 0
    assert result.imported == 0
    assert result.failed == 1


def test_parse_import_rejects_unknown_file():
    try:
        parse_import_file(b"hello", "items.txt")
    except ValueError as exc:
        assert "Unsupported file format" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unsupported file type")
