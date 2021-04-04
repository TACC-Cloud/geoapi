import pytest
import uuid
from geoapi.models import User, Notification
from geoapi.db import db_session
from geoapi.services.notifications import NotificationsService

test_uuid1 = uuid.uuid4()
test_uuid2 = uuid.uuid4()

@pytest.fixture
def notifications(userdata):
    u1 = db_session.query(User).filter(User.username == "test1").first()
    u2 = db_session.query(User).filter(User.username == "test2").first()
    NotificationsService.create(u1, "error", "test error")
    NotificationsService.create(u1, "success", "test success")

@pytest.fixture
def progress_notifications(userdata):
    u1 = db_session.query(User).filter(User.username == "test1").first()
    u2 = db_session.query(User).filter(User.username == "test2").first()
    NotificationsService.createProgress(u1, "error", "test error", test_uuid1)
    NotificationsService.createProgress(u1, "success", "test success", test_uuid2)


def test_get_notifications(test_client, notifications):
    u1 = db_session.query(User).get(1)

    resp = test_client.get('/notifications/',
                            headers={'x-jwt-assertion-test': u1.jwt})
    data = resp.get_json()
    assert resp.status_code == 200
    assert len(data) == 2

def test_filter_notifications(test_client, notifications):
    u1 = db_session.query(User).get(1)

    resp = test_client.get('/notifications/?startDate=2222-1-1T12:00:00+00:00',
                            headers={'x-jwt-assertion-test': u1.jwt})
    data = resp.get_json()
    assert resp.status_code == 200
    assert len(data) == 0

def test_filter_notifications_positive(test_client, notifications):
    u1 = db_session.query(User).get(1)

    resp = test_client.get('/notifications/?startDate=1900-1-1T12:00:00+00:00',
                            headers={'x-jwt-assertion-test': u1.jwt})
    data = resp.get_json()
    assert resp.status_code == 200
    assert len(data) == 2

def test_get_progress_notifications(test_client, notifications):
    u1 = db_session.query(User).get(1)

    resp = test_client.get('/notifications/progress',
                           headers={'x-jwt-assertion-test': u1.jwt})

    assert resp.status_code == 200

def test_delete_done_progress_notifications(test_client, progress_notifications):
    u1 = db_session.query(User).get(1)

    resp = test_client.delete('/notifications/progress',
                              headers={'x-jwt-assertion-test': u1.jwt})

    assert resp.status_code == 200

    resp = test_client.get('/notifications/progress',
                            headers={'x-jwt-assertion-test': u1.jwt})
    data = resp.get_json()
    assert len(data) == 1

def test_get_progress_notification(test_client, progress_notifications):
    u1 = db_session.query(User).get(1)

    resp = test_client.get('/notifications/progress/{}'.format(test_uuid1),
                            headers={'x-jwt-assertion-test': u1.jwt})

    data = resp.get_json()
    assert resp.status_code == 200
    assert len(data) == 1

def test_delete_progress_notification(test_client, progress_notifications):
    u1 = db_session.query(User).get(1)

    resp = test_client.delete('/notifications/progress/{}'.format(test_uuid1),
                              headers={'x-jwt-assertion-test': u1.jwt})

    assert resp.status_code == 200

    resp = test_client.get('/notifications/progress',
                            headers={'x-jwt-assertion-test': u1.jwt})

    data = resp.get_json()
    assert resp.status_code == 200
    assert len(data) == 1
