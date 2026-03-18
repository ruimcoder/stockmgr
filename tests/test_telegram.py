def test_telegram_webhook_endpoint_is_gone(client):
    response = client.post("/api/telegram/webhook", json={"message": {"text": "hello"}})
    assert response.status_code == 410
    assert "moved out of FastAPI" in response.json()["detail"]


def test_stock_move_still_succeeds_without_app_level_telegram(client):
    created = client.post(
        "/api/items",
        json={
            "barcode": "5606161616161",
            "batch_code": "TG-MOVE-1",
            "name": "Telegram Oil",
            "item_type": "food",
            "storage_location": "Pantry",
            "storage_bucket": "",
            "expiry_date": "2032-08-01",
            "quantity": 3,
            "unidose_per_pack": 1,
            "target_unidoses_location": 6,
        },
    )
    assert created.status_code == 200
    item_id = created.json()["id"]
    moved = client.post(
        f"/items/{item_id}/move",
        data={"direction": "out", "quantity_step": "1", "note": "telegram-test"},
        follow_redirects=False,
    )
    assert moved.status_code == 303
