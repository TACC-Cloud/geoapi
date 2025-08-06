import urllib
from geoapi.utils.tenants import get_tapis_api_server
from geoapi.settings import settings
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from litestar import Litestar
    from litestar.testing import TestClient


def test_login(test_client: "TestClient[Litestar]"):
    tapis_server = get_tapis_api_server("TEST")
    resp = test_client.get(
        "/auth/login?to=/somewhere",
        headers={"Referer": "http://localhost:4200/"},
    )
    sess = test_client.get_session_data()
    resp_url = (
        f"{resp.url.scheme}://{resp.url.netloc.decode()}{resp.url.raw_path.decode()}"
    )
    assert resp.history[-1].status_code == 302
    assert "auth_state" in sess
    assert "clientBaseUrl" in sess
    assert sess["clientBaseUrl"] == "http://localhost:4200"
    assert sess["to"] == "/somewhere"
    assert (
        f"{tapis_server}/v3/oauth2/authorize?"
        f"client_id={settings.TAPIS_CLIENT_ID}"
        f"&redirect_uri=http://test:8888/auth/callback"
        f"&response_type=code"
    ) in resp_url
    assert f'state={sess["auth_state"]}' in resp_url


def test_callback(test_client_user1, requests_mock, user1):
    current_time = datetime.now(timezone.utc)
    access_token = user1.auth.access_token
    access_token_expires_in = 14400
    access_token_expires_at = (
        current_time + timedelta(seconds=access_token_expires_in)
    ).isoformat()
    refresh_token_expires_at = (
        current_time + timedelta(days=365)
    ).isoformat()  # 1 year from now

    tapis_server = get_tapis_api_server("TEST")
    requests_mock.post(
        f"{tapis_server}/v3/oauth2/tokens",
        json={
            "result": {
                "access_token": {
                    "access_token": access_token,
                    "expires_in": access_token_expires_in,
                    "expires_at": access_token_expires_at,
                },
                "refresh_token": {
                    "refresh_token": "mocked_refresh_token",
                    "expires_at": refresh_token_expires_at,
                },
            }
        },
    )

    test_client_user1.set_session_data(
        {
            "auth_state": "mocked_auth_state",
            "to": "/somewhere",
            "clientBaseUrl": "http://localhost:4200",
        }
    )

    resp = test_client_user1.get(
        "/auth/callback?state=mocked_auth_state&code=mocked_code"
    )
    resp_url = (
        f"{resp.url.scheme}://{resp.url.netloc.decode()}{resp.url.raw_path.decode()}"
    )

    assert resp.history[-1].status_code == 302
    assert resp_url.startswith("http://localhost:4200/handle-login")
    assert f"access_token={access_token}" in resp_url
    assert f"expires_in={access_token_expires_in}" in resp_url
    assert f"expires_at={urllib.parse.quote_plus(access_token_expires_at)}" in resp_url
    assert "to=%2Fsomewhere" in resp_url

    sess = test_client_user1.get_session_data()
    assert "auth_state" not in sess
    assert "to" not in sess
    assert "clientBaseUrl" not in sess


def test_callback_missing_state_or_code(test_client):
    resp = test_client.get("/auth/callback?state=mocked_auth_state")
    assert resp.status_code == 400
    resp2 = test_client.get("/auth/callback?code=mocked_code")
    assert resp2.status_code == 400


def test_callback_invalid_state(test_client):
    test_client.set_session_data({"auth_state": "expected_state"})
    resp = test_client.get("/auth/callback?state=wrong_state&code=mocked_code")
    assert resp.status_code == 400
