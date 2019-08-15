from geoapi.models.users import User


def test_post_image_feature_asset(test_client, dbsession, projects_fixture, feature_fixture, image_file_fixture):
    u1 = dbsession.query(User).get(1)
    resp = test_client.post(
        '/projects/1/features/1/assets/',
        data={"file": image_file_fixture},
        headers={'x-jwt-assertion-test': u1.jwt})
    data = resp.get_json()
    assert resp.status_code == 200

    # Have to reload the User from the DB, in app.py in the teardown_appcontext callback
    # the session is removed, which causes u1 above to be undefined AFTER the request above.
    u1 = dbsession.query(User).get(1)
    resp2 = test_client.get("/projects/1/features/1/", headers={'x-jwt-assertion-test': u1.jwt})
    feat = resp2.get_json()
    assert len(feat["assets"]) == 1

def test_post_video_feature_asset(test_client, dbsession, projects_fixture, feature_fixture, video_file_fixture):
    u1 = dbsession.query(User).get(1)
    resp = test_client.post(
        '/projects/1/features/1/assets/',
        data={"file": video_file_fixture},
        headers={'x-jwt-assertion-test': u1.jwt})
    data = resp.get_json()
    assert resp.status_code == 200

    # Have to reload the User from the DB, in app.py in the teardown_appcontext callback
    # the session is removed, which causes u1 above to be undefined AFTER the request above.
    u1 = dbsession.query(User).get(1)
    resp2 = test_client.get("/projects/1/features/1/", headers={'x-jwt-assertion-test': u1.jwt})
    feat = resp2.get_json()
    assert len(feat["assets"]) == 1