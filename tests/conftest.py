import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel

TEST_DB = Path("test_stockmgr.db").resolve()
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["AUTH_MODE"] = "dev"
os.environ["CALENDAR_PROVIDER"] = "none"
os.environ["SECRET_KEY"] = "test-secret"

from app.db import engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def reset_db():
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    yield


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        test_client.post(
            "/auth/dev-login",
            data={"email": "tester@example.com", "display_name": "Tester"},
            follow_redirects=False,
        )
        yield test_client
