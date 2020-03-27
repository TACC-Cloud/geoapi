import pytest
from geoapi.models import User, Notification
from geoapi.db import db_session
from geoapi.services.notifications import NotificationsService


@pytest.fixture
def notifications(userdata):
    u1 = db_session.query(User).filter(User.username == "test1").first()
    u2 = db_session.query(User).filter(User.username == "test2").first()
    NotificationsService.create(u1, "error", "test error")
    NotificationsService.create(u1, "success", "test success")


def test_get_notifications(test_client, notifications):
    u1 = db_session.query(User).get(1)

    resp = test_client.get('/notifications/',
                            headers={'x-jwt-assertion-test': u1.jwt})
    data = resp.get_json()
    assert resp.status_code == 200
    assert len(data) == 2
