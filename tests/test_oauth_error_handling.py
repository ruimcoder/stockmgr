from authlib.integrations.base_client.errors import OAuthError
from authlib.jose.errors import InvalidClaimError


class _OAuthFailingClient:
    async def authorize_access_token(self, request, **kwargs):
        raise OAuthError(error="server_error", description="upstream error")


class _JoseFailingClient:
    async def authorize_access_token(self, request, **kwargs):
        raise InvalidClaimError("iss")


class _CapturingClient:
    def __init__(self):
        self.kwargs = None

    async def authorize_access_token(self, request, **kwargs):
        self.kwargs = kwargs
        return {
            "access_token": "test-access",
            "userinfo": {
                "id": "provider-subject-1",
                "email": "new-oauth-user@example.com",
                "name": "New OAuth User",
            },
        }


def test_oauth_callback_redirects_when_provider_returns_error_query(client, monkeypatch):
    monkeypatch.setattr("app.main.oauth.create_client", lambda provider: _OAuthFailingClient())

    response = client.get(
        "/auth/microsoft/callback?error=server_error&state=test-state",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/login?m=oauth-provider-error"


def test_oauth_callback_redirects_when_token_exchange_raises(client, monkeypatch):
    monkeypatch.setattr("app.main.oauth.create_client", lambda provider: _OAuthFailingClient())

    response = client.get("/auth/microsoft/callback?state=test-state", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login?m=oauth-provider-error"


def test_oauth_callback_maps_access_denied_to_cancelled_message(client, monkeypatch):
    monkeypatch.setattr("app.main.oauth.create_client", lambda provider: _OAuthFailingClient())

    response = client.get(
        "/auth/microsoft/callback?error=access_denied&state=test-state",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/login?m=oauth-cancelled"


def test_oauth_callback_redirects_when_id_token_claim_validation_fails(client, monkeypatch):
    monkeypatch.setattr("app.main.oauth.create_client", lambda provider: _JoseFailingClient())

    response = client.get("/auth/microsoft/callback?state=test-state", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login?m=oauth-provider-error"


def test_oauth_callback_uses_relaxed_claims_options_for_microsoft(client, monkeypatch):
    captured = _CapturingClient()
    monkeypatch.setattr("app.main.oauth.create_client", lambda provider: captured)

    response = client.get("/auth/microsoft/callback?state=test-state", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login?m=login-pending-approval"
    assert captured.kwargs == {"claims_options": {}}
