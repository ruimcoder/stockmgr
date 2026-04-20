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
    expiry_date: date | None = Field(default=None)
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
    food_group: str | None = Field(default=None)
    weight_capacity: float | None = Field(default=None)
    uom: str | None = Field(default=None)
    item_category: str = Field(default="food", nullable=False)
    non_food_category: str | None = Field(default=None)

    created_at: datetime= Field(default_factory=lambda: datetime.now(UTC), nullable=False)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False)


class LocationPlan(SQLModel, table=True):
    """Stores per-location planning data: participants and supply duration."""

    id: int | None = Field(default=None, primary_key=True)
    location: str = Field(unique=True, index=True, nullable=False)
    participants: int = Field(ge=1, nullable=False)
    stock_duration_days: int = Field(ge=1, nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False)

    @property
    def main_meals_total(self) -> int:
        """Total main meal occasions (2 per person per day)."""
        return self.participants * self.stock_duration_days * 2

    @property
    def snack_meals_total(self) -> int:
        """Total snack/breakfast occasions (2 per person per day)."""
        return self.participants * self.stock_duration_days * 2

    @property
    def total_meal_occasions(self) -> int:
        """Total meal occasions (4 per person per day: 2 main + 2 snack)."""
        return self.participants * self.stock_duration_days * 4


class StockMovement(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    stock_item_id: int = Field(foreign_key="stockitem.id", index=True, nullable=False)
    user_id: int = Field(foreign_key="user.id", index=True, nullable=False)
    delta: int = Field(nullable=False)
    note: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False)
