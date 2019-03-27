from geoapi.models.users import User

def test_get_auth(users_fixture, test_client):
    resp = test_client.get("/auth/")
