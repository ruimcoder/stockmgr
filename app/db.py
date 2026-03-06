from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings

settings = get_settings()
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
        connection.exec_driver_sql(
            "UPDATE stockitem SET expiry_date = date('now') WHERE expiry_date IS NULL;"
        )
        connection.exec_driver_sql("UPDATE stockitem SET quantity = COALESCE(quantity, 0);")


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    _migrate_legacy_schema()


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
