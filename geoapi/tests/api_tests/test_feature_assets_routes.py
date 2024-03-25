from unittest.mock import patch

from geoapi.models.users import User
from geoapi.db import db_session


@patch("geoapi.services.features.AgaveUtils")
def test_post_image_feature_asset(MockAgaveUtils, test_client, projects_fixture, feature_fixture, image_file_fixture):
    MockAgaveUtils().getFile.return_value = image_file_fixture
    u1 = db_session.query(User).filter(User.username == "test1").first()
    resp = test_client.post(
        '/projects/1/features/1/assets/',
        json={"system_id": 'test', 'path': '/test/corrected_image.jpg'},
        headers={'X-Tapis-Token': u1.jwt})
    data = resp.get_json() # noqa
    assert resp.status_code == 200

    # Have to reload the User from the DB, in app.py in the teardown_appcontext callback
    # the session is removed, which causes u1 above to be undefined AFTER the request above.
    u1 = db_session.query(User).get(1)
    resp2 = test_client.get("/projects/1/features/1/", headers={'X-Tapis-Token': u1.jwt})
    feat = resp2.get_json()
    assert len(feat["assets"]) == 1


@patch("geoapi.services.features.AgaveUtils")
def test_post_video_feature_asset(MockAgaveUtils, test_client, projects_fixture, feature_fixture, video_file_fixture):
    MockAgaveUtils().getFile.return_value = video_file_fixture
    u1 = db_session.query(User).filter(User.username == "test1").first()
    resp = test_client.post(
        '/projects/1/features/1/assets/',
        json={"system_id": 'test', 'path': '/test/test.mp4'},
        headers={'X-Tapis-Token': u1.jwt})
    data = resp.get_json() # noqa
    assert resp.status_code == 200

    u1 = db_session.query(User).get(1)
    resp2 = test_client.get("/projects/1/features/1/", headers={'X-Tapis-Token': u1.jwt})
    feat = resp2.get_json()
    assert len(feat["assets"]) == 1
