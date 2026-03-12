from __future__ import annotations

import hmac
from dataclasses import dataclass

import httpx

from app.config import Settings


class TelegramServiceError(RuntimeError):
    pass


class TelegramConfigError(TelegramServiceError):
    pass


class TelegramSecurityError(TelegramServiceError):
    pass


class TelegramDeliveryError(TelegramServiceError):
    pass


@dataclass(slots=True)
class TelegramIncomingMessage:
    user_id: int
    chat_id: int
    chat_type: str | None
    text: str


class TelegramService:
    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def is_enabled(self) -> bool:
        return all(
            (
                self.settings.telegram_bot_token.strip(),
                self.settings.telegram_webhook_secret.strip(),
                self.settings.telegram_allowed_user_id is not None,
                self.settings.telegram_allowed_chat_id is not None,
            )
        )

    def ensure_enabled(self) -> None:
        if self.is_enabled:
            return
        raise TelegramConfigError(
            "Telegram integration is not fully configured. "
            "Set TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_SECRET, "
            "TELEGRAM_ALLOWED_USER_ID, and TELEGRAM_ALLOWED_CHAT_ID."
        )

    def validate_webhook_secret(self, provided_secret: str | None) -> None:
        self.ensure_enabled()
        expected_secret = self.settings.telegram_webhook_secret.strip()
        if not provided_secret or not hmac.compare_digest(provided_secret, expected_secret):
            raise TelegramSecurityError("Invalid Telegram webhook secret.")

    def validate_sender(self, *, user_id: int, chat_id: int, chat_type: str | None) -> None:
        self.ensure_enabled()
        expected_user_id = int(self.settings.telegram_allowed_user_id or 0)
        expected_chat_id = int(self.settings.telegram_allowed_chat_id or 0)
        if user_id != expected_user_id:
            raise TelegramSecurityError("Unauthorized Telegram user.")
        if chat_id != expected_chat_id:
            raise TelegramSecurityError("Unauthorized Telegram chat.")
        if self.settings.telegram_require_private_chat and chat_type != "private":
            raise TelegramSecurityError("Telegram commands must come from a private chat.")

    def parse_incoming(
        self,
        *,
        text: str,
        user_id: int,
        chat_id: int,
        chat_type: str | None,
        provided_secret: str | None,
    ) -> TelegramIncomingMessage:
        self.validate_webhook_secret(provided_secret)
        self.validate_sender(user_id=user_id, chat_id=chat_id, chat_type=chat_type)
        content = text.strip()
        if not content:
            raise TelegramSecurityError("Empty Telegram message.")
        return TelegramIncomingMessage(
            user_id=user_id,
            chat_id=chat_id,
            chat_type=chat_type,
            text=content,
        )

    async def send_message(self, *, text: str, chat_id: int | None = None) -> dict:
        self.ensure_enabled()
        payload = self._payload(text=text, chat_id=chat_id)
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.post(self._send_message_url(), json=payload)
        return self._validate_delivery_response(response)

    def send_message_sync(self, *, text: str, chat_id: int | None = None) -> dict:
        self.ensure_enabled()
        payload = self._payload(text=text, chat_id=chat_id)
        with httpx.Client(timeout=8) as client:
            response = client.post(self._send_message_url(), json=payload)
        return self._validate_delivery_response(response)

    def _send_message_url(self) -> str:
        token = self.settings.telegram_bot_token.strip()
        return f"https://api.telegram.org/bot{token}/sendMessage"

    def _payload(self, *, text: str, chat_id: int | None) -> dict:
        target_chat_id = chat_id if chat_id is not None else self.settings.telegram_allowed_chat_id
        if target_chat_id is None:
            raise TelegramConfigError("Telegram target chat_id is not configured.")
        return {
            "chat_id": int(target_chat_id),
            "text": text,
            "disable_web_page_preview": True,
        }

    def _validate_delivery_response(self, response: httpx.Response) -> dict:
        if response.status_code >= 400:
            raise TelegramDeliveryError(f"Telegram delivery failed: {response.text}")
        body = response.json()
        if not body.get("ok"):
            raise TelegramDeliveryError(f"Telegram delivery was rejected: {body}")
        return body
