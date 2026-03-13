from datetime import UTC, date, datetime

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True, nullable=False)
    display_name: str = Field(nullable=False)
    oauth_provider: str = Field(default="dev", nullable=False)
    oauth_subject: str = Field(index=True, nullable=False)
    approval_status: str = Field(default="pending", nullable=False)
    is_admin: bool = Field(default=False, nullable=False)
    access_token: str | None = Field(default=None)
    refresh_token: str | None = Field(default=None)
    requested_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False)
    approved_at: datetime | None = Field(default=None)
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
    quantity: int = Field(default=0, nullable=False)
    unidose_per_pack: int = Field(default=1, nullable=False)
    target_unidoses_location: int = Field(default=0, nullable=False)
    temp_min_c: float | None = Field(default=None)
    temp_max_c: float | None = Field(default=None)
    humidity_min_pct: float | None = Field(default=None)
    humidity_max_pct: float | None = Field(default=None)
    renewal_date: date | None = Field(default=None)
    comment: str | None = Field(default=None)
    image_url: str | None = Field(default=None)
    nutriscore: str | None = Field(default=None)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False)


class StockMovement(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    stock_item_id: int = Field(foreign_key="stockitem.id", index=True, nullable=False)
    user_id: int = Field(foreign_key="user.id", index=True, nullable=False)
    delta: int = Field(nullable=False)
    note: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False)
