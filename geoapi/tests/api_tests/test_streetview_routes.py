import pytest

from geoapi.db import db_session
from geoapi.models.users import User
from geoapi.models.streetview import (Streetview, StreetviewOrganization,
                                      StreetviewInstance, StreetviewSequence)
from geoapi.services.streetview import StreetviewService


@pytest.fixture(scope="function")
def streetview_service_resource_fixture():
    u1 = db_session.query(User).get(1)
    streetview_service_object = Streetview(user_id=u1.id,
                                           service="my_service",
                                           token="my_token", )
    db_session.add(streetview_service_object)
    db_session.commit()
    yield streetview_service_object


@pytest.fixture(scope="function")
def organization_fixture(streetview_service_resource_fixture):
    org = StreetviewService.createOrganization(
        streetview_id=streetview_service_resource_fixture.id,
        data={"key": "my_key", "name": "my_name", "slug": "my_slug"})
    yield org


@pytest.fixture(scope="function")
def instance_fixture(streetview_service_resource_fixture):
    streetview_instance = StreetviewInstance(
        streetview_id=streetview_service_resource_fixture.id,
        system_id="mySystem",
        path="myPath")
    db_session.add(streetview_instance)
    db_session.commit()
    yield streetview_instance


@pytest.fixture(scope="function")
def sequence_fixture(streetview_service_resource_fixture, instance_fixture, organization_fixture, feature_fixture):
    streetview_sequence = StreetviewSequence(
        feature_id=feature_fixture.id,
        organization_id=organization_fixture.id,
        streetview_instance_id=instance_fixture.id,
        sequence_id="abcd")
    db_session.add(streetview_sequence)
    db_session.commit()
    yield streetview_sequence


def test_list_streetview_service_resource(test_client, streetview_service_resource_fixture):
    u1 = db_session.query(User).get(1)
    resp = test_client.get('/streetview/',
                           headers={'x-jwt-assertion-test': u1.jwt})
    assert resp.status_code == 200
    assert resp.get_json() == [{'id': 1, 'user_id': 1, 'token': 'my_token',
                                'service': 'my_service', 'service_user': None,
                                'organizations': [], 'instances': []}]


def test_create_streetview_service_resource(test_client):
    u1 = db_session.query(User).get(1)
    data = {
        "service": "service",
        "service_user": "some_username",
        "token": "my_token"
    }
    resp = test_client.post('/streetview/',
                            json=data,
                            headers={'x-jwt-assertion-test': u1.jwt})
    assert resp.status_code == 200
    streetview_service_object = db_session.query(Streetview).get(1)
    assert streetview_service_object.service == data["service"]
    assert streetview_service_object.service_user == data["service_user"]
    assert streetview_service_object.token == data["token"]
    assert resp.get_json() == {'id': 1, 'instances': [], 'organizations': [],
                               'service': 'service', 'service_user': 'some_username',
                               'token': 'my_token', 'user_id': 1}


def test_get_streetview_service_resource(test_client, streetview_service_resource_fixture):
    u1 = db_session.query(User).get(1)
    resp = test_client.get(
        '/streetview/{}/'.format(streetview_service_resource_fixture.service),
        headers={'x-jwt-assertion-test': u1.jwt})
    assert resp.status_code == 200
    assert resp.get_json() == {'id': 1, 'user_id': 1, 'token': 'my_token',
                               'service': 'my_service', 'service_user': None,
                               'organizations': [], 'instances': []}


def test_delete_streetview_service_resource(test_client, streetview_service_resource_fixture):
    u1 = db_session.query(User).get(1)
    resp = test_client.delete('/streetview/{}/'.format(streetview_service_resource_fixture.service),
                              headers={'x-jwt-assertion-test': u1.jwt})
    assert resp.status_code == 200
    assert db_session.query(StreetviewOrganization).first() is None


def test_update_streetview_service_resource(test_client, streetview_service_resource_fixture):
    u1 = db_session.query(User).get(1)
    data = {
        "service_user": "some_different_username"
    }
    resp = test_client.put('/streetview/{}/'.format(streetview_service_resource_fixture.service),
                           json=data,
                           headers={'x-jwt-assertion-test': u1.jwt})
    assert resp.status_code == 200
    service = db_session.query(Streetview).get(1)
    assert service.service_user == "some_different_username"


def test_create_organization(test_client, streetview_service_resource_fixture):
    u1 = db_session.query(User).get(1)
    data = {
        "name": "my_name",
        "slug": "my_slug",
        "key": "my_key"

    }
    resp = test_client.post(
        '/streetview/{}/organization/'.format(streetview_service_resource_fixture.id),
        json=data,
        headers={'x-jwt-assertion-test': u1.jwt})
    assert resp.status_code == 200
    assert resp.get_json() == {'id': 1, 'key': 'my_key', 'name': 'my_name',
                               'slug': 'my_slug', 'streetview_id': 1}

    streetview_service_resource = db_session.query(Streetview).get(1)
    organization = streetview_service_resource.organizations[0]
    assert organization.name == "my_name"
    assert organization.slug == "my_slug"
    assert organization.key == "my_key"


def test_delete_organization(test_client, organization_fixture):
    u1 = db_session.query(User).get(1)
    resp = test_client.delete('streetview/organization/{}/'.format(organization_fixture.id),
                              headers={'x-jwt-assertion-test': u1.jwt})
    assert resp.status_code == 200
    assert db_session.query(StreetviewOrganization).first() is None


def test_delete_instance(test_client, instance_fixture):
    u1 = db_session.query(User).get(1)
    resp = test_client.delete('streetview/instances/{}/'.format(instance_fixture.id),
                              headers={'x-jwt-assertion-test': u1.jwt})
    assert resp.status_code == 200
    assert db_session.query(StreetviewInstance).first() is None


def test_add_sequence_to_instance(test_client,
                                  streetview_service_resource_fixture,
                                  organization_fixture):
    u1 = db_session.query(User).get(1)
    data = {
        "streetviewId": streetview_service_resource_fixture.id,
        "sequenceId": "my_sequence_id",
        "organizationId": "my_org_id",
        "dir": {
            "system": "my_system",
            "path": "my_path"
        }
    }
    resp = test_client.post('/streetview/sequences/', json=data, headers={'x-jwt-assertion-test': u1.jwt})
    assert resp.status_code == 200
    # NOTE: shouldn't response by the instance

    streetview_instance = db_session.query(StreetviewInstance).first()
    assert len(streetview_instance.sequences) == 1
    sequence = streetview_instance.sequences[0]
    assert sequence.sequence_id == "my_sequence_id"
    assert sequence.organization_id == "my_org_id"
    assert sequence.streetview_instance_id == streetview_service_resource_fixture.id


def test_get_sequence(test_client, streetview_service_resource_fixture, sequence_fixture):
    u1 = db_session.query(User).get(1)
    resp = test_client.get('/streetview/sequences/{}/'.format(sequence_fixture.sequence_id),
                           headers={'x-jwt-assertion-test': u1.jwt})
    assert resp.status_code == 200
    assert resp.get_json() == {'bbox': None, 'end_date': None, 'id': 1, 'organization_id': '1',
                               'sequence_id': sequence_fixture.sequence_id, 'start_date': None, 'streetview_instance_id': 1}


def test_update_sequence(test_client, streetview_service_resource_fixture, sequence_fixture):
    u1 = db_session.query(User).get(1)
    data = {
        "organization_id": "something_else",
    }
    resp = test_client.put(
        '/streetview/sequences/{}/'.format(sequence_fixture.id),  # TODO differs from GET route where mapillary id is used
        json=data,
        headers={'x-jwt-assertion-test': u1.jwt})
    assert resp.status_code == 200
    updated = resp.get_json()
    assert updated["organization_id"] == "something_else"


def test_delete_sequence(test_client, streetview_service_resource_fixture, sequence_fixture):
    u1 = db_session.query(User).get(1)
    resp = test_client.delete(
        'streetview/instances/{}/'.format(sequence_fixture.id),  # TODO differs from GET route where mapillary id is used
        headers={'x-jwt-assertion-test': u1.jwt})
    assert resp.status_code == 200
    assert db_session.query(StreetviewSequence).first() is None
