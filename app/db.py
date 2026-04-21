from collections.abc import Generator
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings

settings = get_settings()


def _sqlite_path_from_url(database_url: str) -> Path | None:
    if not database_url.startswith("sqlite"):
        return None
    normalized = database_url.split("?", 1)[0]
    if normalized.endswith(":memory:"):
        return None

    if normalized.startswith("sqlite:////"):
        return Path("/") / normalized.removeprefix("sqlite:////")
    if normalized.startswith("sqlite:///"):
        raw_path = normalized.removeprefix("sqlite:///")
        if not raw_path:
            return None
        return Path(raw_path)
    return None


def _ensure_sqlite_directory(database_url: str) -> None:
    db_path = _sqlite_path_from_url(database_url)
    if not db_path:
        return
    if not db_path.is_absolute():
        db_path = (Path.cwd() / db_path).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)


_ensure_sqlite_directory(settings.database_url)
connect_args: dict[str, object] = {}
if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(settings.database_url, echo=False, connect_args=connect_args)


def _migrate_legacy_schema() -> None:
    if not settings.database_url.startswith("sqlite"):
        return
    with engine.begin() as connection:
        has_user = connection.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='user';"
        ).fetchone()
        if has_user:
            user_columns = connection.exec_driver_sql("PRAGMA table_info(user);").fetchall()
            user_names = {row[1] for row in user_columns}
            if "approval_status" not in user_names:
                connection.exec_driver_sql(
                    "ALTER TABLE user ADD COLUMN approval_status TEXT DEFAULT 'approved';"
                )
            if "is_admin" not in user_names:
                connection.exec_driver_sql(
                    "ALTER TABLE user ADD COLUMN is_admin INTEGER DEFAULT 0;"
                )
            if "requested_at" not in user_names:
                connection.exec_driver_sql("ALTER TABLE user ADD COLUMN requested_at TEXT;")
            if "approved_at" not in user_names:
                connection.exec_driver_sql("ALTER TABLE user ADD COLUMN approved_at TEXT;")
            connection.exec_driver_sql(
                "UPDATE user SET approval_status='approved' WHERE approval_status IS NULL;"
            )
            connection.exec_driver_sql(
                "UPDATE user SET requested_at = COALESCE(requested_at, created_at);"
            )
            connection.exec_driver_sql(
                "UPDATE user SET approved_at = COALESCE(approved_at, created_at) "
                "WHERE approval_status='approved';"
            )

        has_stockitem = connection.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='stockitem';"
        ).fetchone()
        if not has_stockitem:
            return
        columns = connection.exec_driver_sql("PRAGMA table_info(stockitem);").fetchall()
        existing_names = {row[1] for row in columns}
        if "batch_code" not in existing_names:
            connection.exec_driver_sql("ALTER TABLE stockitem ADD COLUMN batch_code TEXT;")
        if "quantity" not in existing_names:
            connection.exec_driver_sql(
                "ALTER TABLE stockitem ADD COLUMN quantity INTEGER DEFAULT 0;"
            )
        if "unidose_per_pack" not in existing_names:
            connection.exec_driver_sql(
                "ALTER TABLE stockitem ADD COLUMN unidose_per_pack INTEGER DEFAULT 1;"
            )
        if "target_unidoses_location" not in existing_names:
            connection.exec_driver_sql(
                "ALTER TABLE stockitem ADD COLUMN target_unidoses_location INTEGER DEFAULT 0;"
            )
        if "comment" not in existing_names:
            connection.exec_driver_sql("ALTER TABLE stockitem ADD COLUMN comment TEXT;")
        if "image_url" not in existing_names:
            connection.exec_driver_sql("ALTER TABLE stockitem ADD COLUMN image_url TEXT;")
        if "nutriscore" not in existing_names:
            connection.exec_driver_sql("ALTER TABLE stockitem ADD COLUMN nutriscore TEXT;")
        if "food_group" not in existing_names:
            connection.exec_driver_sql("ALTER TABLE stockitem ADD COLUMN food_group TEXT;")
        if "weight_capacity" not in existing_names:
            connection.exec_driver_sql("ALTER TABLE stockitem ADD COLUMN weight_capacity REAL;")
        if "uom" not in existing_names:
            connection.exec_driver_sql("ALTER TABLE stockitem ADD COLUMN uom TEXT;")
        if "item_category" not in existing_names:
            connection.exec_driver_sql(
                "ALTER TABLE stockitem ADD COLUMN item_category TEXT NOT NULL DEFAULT 'food';"
            )
        if "non_food_category" not in existing_names:
            connection.exec_driver_sql(
                "ALTER TABLE stockitem ADD COLUMN non_food_category TEXT;"
            )
        connection.exec_driver_sql(
            "UPDATE stockitem SET expiry_date = date('now') WHERE expiry_date IS NULL;"
        )
        connection.exec_driver_sql("UPDATE stockitem SET quantity = COALESCE(quantity, 0);")
        connection.exec_driver_sql(
            "UPDATE stockitem SET unidose_per_pack = COALESCE(NULLIF(unidose_per_pack, 0), 1);"
        )
        connection.exec_driver_sql(
            "UPDATE stockitem SET target_unidoses_location = COALESCE(target_unidoses_location, 0);"
        )

        # benchmarkitem table -- add qty_period if missing (issue #157)
        has_bi = connection.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='benchmarkitem';"
        ).fetchone()
        if has_bi:
            bi_cols = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(benchmarkitem);").fetchall()}
            if "qty_period" not in bi_cols:
                connection.exec_driver_sql(
                    "ALTER TABLE benchmarkitem ADD COLUMN qty_period TEXT NOT NULL DEFAULT 'day';"
                )

        # locationplan table — created by create_all but ensure for older DBs
        has_locationplan = connection.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='locationplan';"
        ).fetchone()
        if not has_locationplan:
            connection.exec_driver_sql(
                """CREATE TABLE IF NOT EXISTS locationplan (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    location TEXT NOT NULL UNIQUE,
                    participants INTEGER NOT NULL,
                    stock_duration_days INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                )"""
            )


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    _migrate_legacy_schema()


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
