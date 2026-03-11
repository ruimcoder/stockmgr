from pathlib import Path

from app.db import _sqlite_path_from_url


def test_sqlite_path_from_url_handles_absolute_posix_path():
    resolved = _sqlite_path_from_url("sqlite:////home/site/data/stockmgr.db")
    assert resolved == Path("/home/site/data/stockmgr.db")


def test_sqlite_path_from_url_handles_relative_file_path():
    resolved = _sqlite_path_from_url("sqlite:///./stockmgr.db")
    assert resolved == Path("./stockmgr.db")


def test_sqlite_path_from_url_ignores_non_sqlite_and_memory():
    assert _sqlite_path_from_url("postgresql://localhost/db") is None
    assert _sqlite_path_from_url("sqlite:///:memory:") is None
