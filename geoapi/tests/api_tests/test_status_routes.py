def test_get_status_unauthorized_guest(test_client, projects_fixture):
    resp = test_client.get('/status/')
    assert resp.status_code == 403


def test_get_status(test_client, user1):
    resp = test_client.get('/status/',
                           headers={'x-jwt-assertion-test': user1.jwt})
    data = resp.get_json()
    assert resp.status_code == 200
    assert data == {'status': 'OK'}
