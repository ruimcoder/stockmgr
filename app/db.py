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
        has_stockitem = connection.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='stockitem';"
        ).fetchone()
        if not has_stockitem:
            return
        columns = connection.exec_driver_sql("PRAGMA table_info(stockitem);").fetchall()
        existing_names = {row[1] for row in columns}
        if "batch_code" not in existing_names:
            connection.exec_driver_sql("ALTER TABLE stockitem ADD COLUMN batch_code TEXT;")
        connection.exec_driver_sql(
            "UPDATE stockitem SET expiry_date = date('now') WHERE expiry_date IS NULL;"
        )


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    _migrate_legacy_schema()


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
