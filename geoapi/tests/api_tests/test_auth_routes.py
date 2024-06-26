
from geoapi.utils.tenants import get_api_server
from geoapi.settings import settings
import time


def test_login(test_client):
    tapis_server = get_api_server("TEST")
    resp = test_client.get('/auth/login?to=/somewhere', headers={'Referer': 'http://localhost:4200/'})

    assert resp.status_code == 302

    with test_client.session_transaction() as sess:
        assert 'auth_state' in sess
        assert 'clientBaseUrl' in sess
        assert sess['clientBaseUrl'] == 'http://localhost:4200'
        assert sess['to'] == "/somewhere"

        assert (f'{tapis_server}/v3/oauth2/authorize?'
                f'client_id={settings.TAPIS_CLIENT_ID}'
                f'&redirect_uri=http://test:8888/auth/callback'
                f'&response_type=code') in resp.location
        assert f'state={sess["auth_state"]}' in resp.location


def test_callback(test_client, requests_mock):
    current_time = int(time.time())
    access_token_expires_in = 14400
    access_token_expires_at = current_time + access_token_expires_in
    refresh_token_expires_at = current_time + 31556926 # year from now

    tapis_server = get_api_server("TEST")
    requests_mock.post(f'{tapis_server}/v3/oauth2/tokens', json={
        "result": {
            "access_token": {
                "access_token": "mocked_access_token",
                "expires_in": access_token_expires_in,
                "expires_at": access_token_expires_at
            },
            "refresh_token": {
                "refresh_token": "mocked_refresh_token",
                "expires_at": refresh_token_expires_at
            }
        }
    })

    with test_client.session_transaction() as sess:
        sess['auth_state'] = 'mocked_auth_state'
        sess['to'] = '/somewhere'
        sess['clientBaseUrl'] = 'http://localhost:4200'

    resp = test_client.get('/auth/callback?state=mocked_auth_state&code=mocked_code')

    assert resp.status_code == 302
    assert resp.location.startswith('http://localhost:4200/handle-login')
    assert 'access_token=mocked_access_token' in resp.location
    assert f'expires_in={access_token_expires_in}' in resp.location
    assert f'expires_at={access_token_expires_at}' in resp.location
    assert 'to=/' in resp.location

    with test_client.session_transaction() as sess:
        assert 'auth_state' not in sess
        assert 'to' not in sess
        assert 'clientBaseUrl' not in sess