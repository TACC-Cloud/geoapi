def test_get_status_unauthorized_guest(test_client, projects_fixture):
    resp = test_client.get("/status/")
    data = resp.get_json()
    assert resp.status_code == 200
    assert data == {"status": "OK"}


def test_get_status(test_client, user1):
    resp = test_client.get("/status/", headers={"X-Tapis-Token": user1.jwt})
    data = resp.get_json()
    assert resp.status_code == 200
    assert data == {"status": "OK"}
