def test_get_openapi_schema(test_client):
    resp = test_client.get("/schema/openapi.json")
    assert resp.status_code == 200
    assert "/projects" in resp.json()["paths"]
