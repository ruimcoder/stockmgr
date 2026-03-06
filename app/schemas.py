from datetime import date
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ItemBase(BaseModel):
    barcode: str | None = None
    batch_code: str | None = None
    name: str = Field(min_length=1)
    item_type: str = Field(min_length=1)
    storage_location: str = Field(min_length=1)
    storage_bucket: str = ""
    expiry_date: date
    temp_min_c: float | None = None
    temp_max_c: float | None = None
    humidity_min_pct: float | None = None
    humidity_max_pct: float | None = None
    renewal_date: date | None = None

    @field_validator("name", "item_type", "storage_location")
    @classmethod
    def non_empty_text(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Value cannot be empty.")
        return trimmed

    @field_validator("storage_bucket", mode="before")
    @classmethod
    def normalize_storage_bucket(cls, value: str | None) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @field_validator("batch_code", mode="before")
    @classmethod
    def normalize_batch_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = str(value).strip()
        return trimmed or None


class ItemCreate(ItemBase):
    pass


class ItemRead(ItemBase):
    id: int


class BarcodeLookupRequest(BaseModel):
    barcode: str = Field(min_length=8, max_length=20)
    item_type: str = "unknown"


class ProviderAttempt(BaseModel):
    provider: str
    status: str
    message: str | None = None


class BarcodeLookupResult(BaseModel):
    found: bool
    provider: str | None = None
    data: dict[str, Any] | None = None
    attempts: list[ProviderAttempt] = []


class ImportResult(BaseModel):
    imported: int
    failed: int
    errors: list[str]
