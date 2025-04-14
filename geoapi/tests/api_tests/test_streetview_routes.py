import pytest

from geoapi.db import db_session
from geoapi.models.users import User
from geoapi.models.streetview import Streetview, StreetviewOrganization
from datetime import datetime, timedelta, timezone


@pytest.fixture(scope="function")
def streetview_service_resource_fixture():
    u1 = db_session.get(User, 1)
    streetview_service_object = Streetview(
        user_id=u1.id,
        service="my_service",
        token="my_token",
        token_expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    db_session.add(streetview_service_object)
    db_session.commit()
    yield streetview_service_object


@pytest.fixture(scope="function")
def streetview_service_resource_expired_fixture(streetview_service_resource_fixture):
    sv = streetview_service_resource_fixture
    sv.token_expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    db_session.commit()
    return sv


@pytest.fixture(scope="function")
def streetview_service_resource_missing_token_expires_at_fixture(
    streetview_service_resource_fixture,
):
    sv = streetview_service_resource_fixture
    sv.token_expires_at = None
    db_session.commit()
    return sv


@pytest.fixture(scope="function")
def organization_fixture(streetview_service_resource_fixture):
    org = StreetviewOrganization(
        streetview_id=streetview_service_resource_fixture.id,
        key="my_key",
        name="my_name",
        slug="my_slug",
    )
    db_session.add(org)
    db_session.commit()
    yield org


def test_list_streetview_service_resource(
    test_client, streetview_service_resource_fixture
):
    u1 = db_session.get(User, 1)
    resp = test_client.get("/streetview/services/", headers={"X-Tapis-Token": u1.jwt})
    assert resp.status_code == 200
    assert resp.get_json() == [
        {
            "id": 1,
            "user_id": 1,
            "token": streetview_service_resource_fixture.token,
            "token_expires_at": str(
                streetview_service_resource_fixture.token_expires_at
            ),
            "service": "my_service",
            "service_user": None,
            "organizations": [],
            "instances": [],
        }
    ]


def test_list_streetview_service_expired_resource(
    test_client, streetview_service_resource_expired_fixture
):
    u1 = db_session.get(User, 1)
    resp = test_client.get("/streetview/services/", headers={"X-Tapis-Token": u1.jwt})
    assert resp.status_code == 200
    assert resp.get_json() == [
        {
            "id": 1,
            "user_id": 1,
            "token": None,
            "token_expires_at": None,
            "service": "my_service",
            "service_user": None,
            "organizations": [],
            "instances": [],
        }
    ]

    # Assert token was nulled in DB
    sv = (
        db_session.query(Streetview)
        .filter_by(id=streetview_service_resource_expired_fixture.id)
        .first()
    )
    assert sv is not None
    assert sv.token is None
    assert sv.token_expires_at is None


def test_list_streetview_service_missing_token_expires_at_resource(
    test_client, streetview_service_resource_missing_token_expires_at_fixture
):
    u1 = db_session.get(User, 1)
    resp = test_client.get("/streetview/services/", headers={"X-Tapis-Token": u1.jwt})
    assert resp.status_code == 200
    assert resp.get_json() == [
        {
            "id": 1,
            "user_id": 1,
            "token": None,
            "token_expires_at": None,
            "service": "my_service",
            "service_user": None,
            "organizations": [],
            "instances": [],
        }
    ]

    # Assert token was nulled in DB
    sv = (
        db_session.query(Streetview)
        .filter_by(id=streetview_service_resource_missing_token_expires_at_fixture.id)
        .first()
    )
    assert sv is not None
    assert sv.token is None
    assert sv.token_expires_at is None


def test_create_streetview_service_resource(test_client):
    u1 = db_session.get(User, 1)
    data = {"service": "service", "service_user": "some_username", "token": "my_token"}
    resp = test_client.post(
        "/streetview/services/", json=data, headers={"X-Tapis-Token": u1.jwt}
    )
    assert resp.status_code == 200
    streetview_service_object = db_session.get(Streetview, 1)
    assert streetview_service_object.service == data["service"]
    assert streetview_service_object.service_user == data["service_user"]
    assert streetview_service_object.token == data["token"]
    assert resp.get_json() == {
        "id": 1,
        "instances": [],
        "organizations": [],
        "service": "service",
        "service_user": "some_username",
        "token": "my_token",
        "token_expires_at": None,
        "user_id": 1,
    }


def test_get_streetview_service_resource(
    test_client, streetview_service_resource_fixture
):
    u1 = db_session.get(User, 1)
    resp = test_client.get(
        "/streetview/services/{}/".format(streetview_service_resource_fixture.service),
        headers={"X-Tapis-Token": u1.jwt},
    )
    assert resp.status_code == 200
    assert resp.get_json() == {
        "id": 1,
        "user_id": 1,
        "token": "my_token",
        "token_expires_at": str(streetview_service_resource_fixture.token_expires_at),
        "service": "my_service",
        "service_user": None,
        "organizations": [],
        "instances": [],
    }


def test_delete_streetview_service_resource(
    test_client, streetview_service_resource_fixture
):
    u1 = db_session.get(User, 1)
    resp = test_client.delete(
        "/streetview/services/{}/".format(streetview_service_resource_fixture.service),
        headers={"X-Tapis-Token": u1.jwt},
    )
    assert resp.status_code == 200
    assert db_session.query(StreetviewOrganization).first() is None


def test_update_streetview_service_resource(
    test_client, streetview_service_resource_fixture
):
    u1 = db_session.get(User, 1)
    data = {"service_user": "some_different_username"}
    resp = test_client.put(
        "/streetview/services/{}/".format(streetview_service_resource_fixture.service),
        json=data,
        headers={"X-Tapis-Token": u1.jwt},
    )
    assert resp.status_code == 200
    service = db_session.get(Streetview, 1)
    assert service.service_user == "some_different_username"


def test_create_organization(test_client, streetview_service_resource_fixture):
    u1 = db_session.get(User, 1)
    data = {"name": "my_name", "slug": "my_slug", "key": "my_key"}
    resp = test_client.post(
        "/streetview/services/{}/organization/".format(
            streetview_service_resource_fixture.service
        ),
        json=data,
        headers={"X-Tapis-Token": u1.jwt},
    )
    assert resp.status_code == 200
    assert resp.get_json() == {
        "id": 1,
        "key": "my_key",
        "name": "my_name",
        "slug": "my_slug",
        "streetview_id": 1,
    }

    streetview_service_resource = db_session.get(Streetview, 1)
    organization = streetview_service_resource.organizations[0]
    assert organization.name == "my_name"
    assert organization.slug == "my_slug"
    assert organization.key == "my_key"


def test_delete_organization(test_client, organization_fixture):
    u1 = db_session.get(User, 1)
    resp = test_client.delete(
        "/streetview/services/{}/organization/{}/".format(
            organization_fixture.streetview.service, organization_fixture.id
        ),
        headers={"X-Tapis-Token": u1.jwt},
    )
    assert resp.status_code == 200
    assert db_session.query(StreetviewOrganization).first() is None


def FAILING_test_post_streetview_sequences(test_client):
    u1 = db_session.get(User, 1)
    data = {
        "dir": {"path": "test path", "system": "test system"},
        "service": "mapillary",
        "sequences": ["test key 1", "test key 2", "test key 3", "test key 4"],
    }
    resp = test_client.post(
        "/streetview/sequences/", json=data, headers={"X-Tapis-Token": u1.jwt}
    )

    assert resp.status_code == 200
    assert len(data["sequences"]) == 4


def FAILING_test_delete_streetview_sequence(test_client):
    u1 = db_session.get(User, 1)
    data = {
        "dir": {"path": "test path", "system": "test system"},
        "service": "mapillary",
        "sequences": ["test key 1", "test key 2", "test key 3", "test key 4"],
    }

    resp = test_client.post(
        "/streetview/sequences/", json=data, headers={"X-Tapis-Token": u1.jwt}
    )

    resp = test_client.get("/streetview/", headers={"X-Tapis-Token": u1.jwt})

    seq_id = resp.get_json()[0]["sequences"][0]["id"]

    test_client.delete(
        "/streetview/sequences/{}/".format(seq_id), headers={"X-Tapis-Token": u1.jwt}
    )

    assert resp.status_code == 200
