
from geoapi.utils.tenants import get_api_server
from geoapi.settings import settings


def test_login(test_client, requests_mock):
    tapis_server = get_api_server("TEST")
    requests_mock.get(f'{tapis_server}/v3/oauth2/authorize', text='mocked response')

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
