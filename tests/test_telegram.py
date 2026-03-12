def _configure_telegram(monkeypatch):
    from app.main import telegram_service

    monkeypatch.setattr(telegram_service.settings, "telegram_bot_token", "test-bot-token")
    monkeypatch.setattr(telegram_service.settings, "telegram_webhook_secret", "top-secret")
    monkeypatch.setattr(telegram_service.settings, "telegram_allowed_user_id", 111111)
    monkeypatch.setattr(telegram_service.settings, "telegram_allowed_chat_id", 222222)
    monkeypatch.setattr(telegram_service.settings, "telegram_require_private_chat", True)


def _telegram_update_payload(text: str, user_id: int = 111111, chat_id: int = 222222) -> dict:
    return {
        "update_id": 9001,
        "message": {
            "message_id": 42,
            "from": {"id": user_id, "username": "authorized-user"},
            "chat": {"id": chat_id, "type": "private"},
            "text": text,
        },
    }


def test_telegram_webhook_requires_configuration(client):
    response = client.post("/api/telegram/webhook", json=_telegram_update_payload("/health"))
    assert response.status_code == 503


def test_telegram_webhook_rejects_invalid_secret(client, monkeypatch):
    _configure_telegram(monkeypatch)
    response = client.post(
        "/api/telegram/webhook",
        headers={"x-telegram-bot-api-secret-token": "wrong-secret"},
        json=_telegram_update_payload("/health"),
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid Telegram webhook secret."


def test_telegram_webhook_rejects_unauthorized_sender(client, monkeypatch):
    _configure_telegram(monkeypatch)
    response = client.post(
        "/api/telegram/webhook",
        headers={"x-telegram-bot-api-secret-token": "top-secret"},
        json=_telegram_update_payload("/health", user_id=999999),
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Unauthorized Telegram user."


def test_telegram_webhook_accepts_authorized_command(client, monkeypatch):
    _configure_telegram(monkeypatch)
    sent_messages: list[tuple[str, int | None]] = []

    async def fake_send_message(*, text: str, chat_id: int | None = None):
        sent_messages.append((text, chat_id))
        return {"ok": True}

    monkeypatch.setattr("app.main.telegram_service.send_message", fake_send_message)
    response = client.post(
        "/api/telegram/webhook",
        headers={"x-telegram-bot-api-secret-token": "top-secret"},
        json=_telegram_update_payload("/health"),
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert sent_messages
    assert sent_messages[0][1] == 222222
    assert "Health: ok" in sent_messages[0][0]
    assert "Version: test-suite" in sent_messages[0][0]


def test_stock_move_sends_telegram_operation_output_when_enabled(client, monkeypatch):
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

    _configure_telegram(monkeypatch)
    sent_messages: list[tuple[str, int | None]] = []

    def fake_send_message_sync(*, text: str, chat_id: int | None = None):
        sent_messages.append((text, chat_id))
        return {"ok": True}

    monkeypatch.setattr("app.main.telegram_service.send_message_sync", fake_send_message_sync)
    moved = client.post(
        f"/items/{item_id}/move",
        data={"direction": "out", "quantity_step": "1", "note": "telegram-test"},
        follow_redirects=False,
    )
    assert moved.status_code == 303
    assert sent_messages
    assert "[stockmgr] stock-move" in sent_messages[0][0]
    assert "name=Telegram Oil" in sent_messages[0][0]
