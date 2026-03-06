from __future__ import annotations

from datetime import datetime, timedelta

import httpx

from app.config import Settings
from app.models import StockItem, User


class CalendarSyncError(RuntimeError):
    pass


class CalendarSyncService:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def schedule_renewal(self, user: User, item: StockItem) -> str:
        if item.renewal_date is None:
            return "no_renewal_date"
        if self.settings.calendar_provider == "none":
            return "calendar_disabled"

        if self.settings.calendar_provider == "google":
            return await self._create_google_event(user, item)
        if self.settings.calendar_provider == "microsoft":
            return await self._create_microsoft_event(user, item)
        raise CalendarSyncError(
            f"Unsupported calendar provider '{self.settings.calendar_provider}'"
        )

    async def _create_google_event(self, user: User, item: StockItem) -> str:
        if user.oauth_provider != "google" or not user.access_token:
            raise CalendarSyncError(
                "Google calendar sync requires Google OAuth login and an access token."
            )

        start_at = datetime.combine(item.renewal_date, datetime.min.time())
        end_at = start_at + timedelta(hours=1)
        body = {
            "summary": f"Renew stock item: {item.name}",
            "description": (
                f"Renewal reminder for {item.name} ({item.storage_location}/{item.storage_bucket})"
            ),
            "start": {"dateTime": start_at.isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": end_at.isoformat(), "timeZone": "UTC"},
        }
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.post(
                "https://www.googleapis.com/calendar/v3/calendars/primary/events",
                headers={"Authorization": f"Bearer {user.access_token}"},
                json=body,
            )
        if response.status_code >= 400:
            raise CalendarSyncError(f"Google calendar sync failed: {response.text}")
        return f"google:{response.json().get('id', 'unknown')}"

    async def _create_microsoft_event(self, user: User, item: StockItem) -> str:
        if user.oauth_provider != "microsoft" or not user.access_token:
            raise CalendarSyncError(
                "Microsoft calendar sync requires Microsoft OAuth login and an access token."
            )

        start_at = datetime.combine(item.renewal_date, datetime.min.time())
        end_at = start_at + timedelta(hours=1)
        body = {
            "subject": f"Renew stock item: {item.name}",
            "body": {"contentType": "Text", "content": f"Renewal reminder for {item.name}"},
            "start": {"dateTime": start_at.isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": end_at.isoformat(), "timeZone": "UTC"},
        }
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.post(
                "https://graph.microsoft.com/v1.0/me/events",
                headers={"Authorization": f"Bearer {user.access_token}"},
                json=body,
            )
        if response.status_code >= 400:
            raise CalendarSyncError(f"Microsoft calendar sync failed: {response.text}")
        return f"microsoft:{response.json().get('id', 'unknown')}"
