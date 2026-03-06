from sqlmodel import Session, select

from app.db import engine
from app.models import User


def test_registration_pending_then_admin_approval(anon_client):
    register = anon_client.post(
        "/register",
        data={"email": "newuser@example.com", "display_name": "New User"},
        follow_redirects=False,
    )
    assert register.status_code == 303
    assert "/login?m=registration-pending" in register.headers["location"]

    login_pending = anon_client.post(
        "/auth/dev-login",
        data={"email": "newuser@example.com"},
        follow_redirects=False,
    )
    assert login_pending.status_code == 303
    assert "/login?m=login-pending-approval" in login_pending.headers["location"]

    anon_client.post("/auth/dev-login", data={"email": "admin@example.com"}, follow_redirects=False)
    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == "newuser@example.com")).first()
        assert user is not None
        user_id = user.id

    approve = anon_client.post(f"/admin/users/{user_id}/approve", follow_redirects=False)
    assert approve.status_code == 303

    anon_client.get("/auth/logout", follow_redirects=False)
    login_ok = anon_client.post(
        "/auth/dev-login",
        data={"email": "newuser@example.com"},
        follow_redirects=False,
    )
    assert login_ok.status_code == 303
    assert login_ok.headers["location"] == "/"
