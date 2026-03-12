from app.main import _build_oauth_redirect_uri


def test_oauth_redirect_uri_prefers_configured_public_base_url():
    callback_uri = "http://10.0.0.4:8000/auth/google/callback"
    redirect_uri = _build_oauth_redirect_uri(
        callback_uri=callback_uri,
        public_base_url="https://stockmgr-prod-01.azurewebsites.net",
        forwarded_proto=None,
    )
    assert redirect_uri == "https://stockmgr-prod-01.azurewebsites.net/auth/google/callback"


def test_oauth_redirect_uri_honors_public_base_path_prefix():
    callback_uri = "http://127.0.0.1:8000/auth/microsoft/callback"
    redirect_uri = _build_oauth_redirect_uri(
        callback_uri=callback_uri,
        public_base_url="https://example.com/stockmgr",
        forwarded_proto=None,
    )
    assert redirect_uri == "https://example.com/stockmgr/auth/microsoft/callback"


def test_oauth_redirect_uri_upgrades_http_when_forwarded_proto_is_https():
    callback_uri = "http://stockmgr-prod-01.azurewebsites.net/auth/google/callback"
    redirect_uri = _build_oauth_redirect_uri(
        callback_uri=callback_uri,
        public_base_url=None,
        forwarded_proto="https",
    )
    assert redirect_uri == "https://stockmgr-prod-01.azurewebsites.net/auth/google/callback"
