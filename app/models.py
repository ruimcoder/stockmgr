from datetime import UTC, date, datetime

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True, nullable=False)
    display_name: str = Field(nullable=False)
    oauth_provider: str = Field(default="dev", nullable=False)
    oauth_subject: str = Field(index=True, nullable=False)
    access_token: str | None = Field(default=None)
    refresh_token: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False)


class StockItem(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True, nullable=False)

    barcode: str | None = Field(default=None, index=True)
    batch_code: str | None = Field(default=None, index=True)
    name: str = Field(nullable=False)
    item_type: str = Field(nullable=False)
    storage_location: str = Field(nullable=False)
    storage_bucket: str = Field(default="", nullable=False)
    expiry_date: date = Field(nullable=False)
    temp_min_c: float | None = Field(default=None)
    temp_max_c: float | None = Field(default=None)
    humidity_min_pct: float | None = Field(default=None)
    humidity_max_pct: float | None = Field(default=None)
    renewal_date: date | None = Field(default=None)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False)
