import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel

TEST_DB = Path("test_stockmgr.db").resolve()
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["AUTH_MODE"] = "dev"
os.environ["CALENDAR_PROVIDER"] = "none"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["ADMIN_EMAILS"] = "admin@example.com"

from app.db import engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402


@pytest.fixture(autouse=True)
def reset_db():
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    yield


@pytest.fixture
def client():
    with Session(engine) as session:
        admin = User(
            email="tester@example.com",
            display_name="Tester",
            oauth_provider="dev",
            oauth_subject="tester@example.com",
            approval_status="approved",
            is_admin=True,
        )
        session.add(admin)
        session.commit()
    with TestClient(app) as test_client:
        test_client.post(
            "/auth/dev-login",
            data={"email": "tester@example.com"},
            follow_redirects=False,
        )
        yield test_client


@pytest.fixture
def anon_client():
    with Session(engine) as session:
        admin = User(
            email="admin@example.com",
            display_name="Admin",
            oauth_provider="dev",
            oauth_subject="admin@example.com",
            approval_status="approved",
            is_admin=True,
        )
        session.add(admin)
        session.commit()
    with TestClient(app) as test_client:
        yield test_client
