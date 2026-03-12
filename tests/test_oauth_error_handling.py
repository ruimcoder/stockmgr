from authlib.integrations.base_client.errors import OAuthError


class _OAuthFailingClient:
    async def authorize_access_token(self, request):
        raise OAuthError(error="server_error", description="upstream error")


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
