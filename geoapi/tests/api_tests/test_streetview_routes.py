import pytest
from unittest.mock import patch
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
                                           token="my_token",
                                           service_user="some_username")
    db_session.add(streetview_service_object)
    db_session.commit()
    yield streetview_service_object


@pytest.fixture(scope="function")
def organization_fixture(streetview_service_resource_fixture):
    u1 = db_session.query(User).get(1)
    org = StreetviewService.createOrganization(
        user=u1,
        service=streetview_service_resource_fixture.service,
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


@pytest.fixture(scope="function")
def convert_to_potree_mock():
    with patch('geoapi.tasks.streetview.from_tapis_to_streetview') as from_tapis_mock:
        yield from_tapis_mock


def test_list_streetview_service_resource(test_client, streetview_service_resource_fixture):
    u1 = db_session.query(User).get(1)
    resp = test_client.get('/streetview/services/',
                           headers={'x-jwt-assertion-test': u1.jwt})
    assert resp.status_code == 200
    assert resp.get_json() == [{'id': 1, 'user_id': 1, 'token': 'my_token',
                                'service': 'my_service', 'service_user': 'some_username',
                                'organizations': [], 'instances': []}]


def test_list_streetview_service_resource_unauthed(test_client, streetview_service_resource_fixture):
    resp = test_client.get('/streetview/services/')
    assert resp.status_code == 403


def test_create_streetview_service_resource(test_client):
    u1 = db_session.query(User).get(1)
    data = {
        "service": "service",
        "service_user": "some_username",
        "token": "my_token"
    }
    resp = test_client.post('/streetview/services/',
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


def test_create_streetview_service_resource_unauthed(test_client):
    data = {
        "service": "service",
        "service_user": "some_username",
        "token": "my_token"
    }
    resp = test_client.post('/streetview/services/', json=data)
    assert resp.status_code == 403


def test_get_streetview_service_resource(test_client, streetview_service_resource_fixture):
    u1 = db_session.query(User).get(1)
    resp = test_client.get(
        '/streetview/services/{}/'.format(streetview_service_resource_fixture.service),
        headers={'x-jwt-assertion-test': u1.jwt})
    assert resp.status_code == 200
    assert resp.get_json() == {'id': 1, 'user_id': 1, 'token': 'my_token',
                               'service': 'my_service', 'service_user': 'some_username',
                               'organizations': [], 'instances': []}


def test_get_streetview_service_resource_illegal_access(test_client, streetview_service_resource_fixture):
    u2 = db_session.query(User).get(2)
    resp = test_client.get(
        '/streetview/services/{}/'.format(streetview_service_resource_fixture.service),
        headers={'x-jwt-assertion-test': u2.jwt})
    assert resp.status_code == 404


def test_delete_streetview_service_resource(test_client, streetview_service_resource_fixture):
    u1 = db_session.query(User).get(1)
    resp = test_client.delete('/streetview/services/{}/'.format(streetview_service_resource_fixture.service),
                              headers={'x-jwt-assertion-test': u1.jwt})
    assert resp.status_code == 200
    assert db_session.query(StreetviewOrganization).first() is None


def test_delete_streetview_service_resource_illegal_access(test_client, streetview_service_resource_fixture):
    u2 = db_session.query(User).get(2)
    resp = test_client.delete('/streetview/services/{}/'.format(streetview_service_resource_fixture.service),
                              headers={'x-jwt-assertion-test': u2.jwt})
    assert resp.status_code == 404


def test_update_streetview_service_resource(test_client, streetview_service_resource_fixture):
    u1 = db_session.query(User).get(1)
    data = {
        "service_user": "some_different_username"
    }
    resp = test_client.put('/streetview/services/{}/'.format(streetview_service_resource_fixture.service),
                           json=data,
                           headers={'x-jwt-assertion-test': u1.jwt})
    assert resp.status_code == 200
    service = db_session.query(Streetview).get(1)
    assert service.service_user == "some_different_username"


def test_update_streetview_service_resource_illegal_access(test_client, streetview_service_resource_fixture):
    u2 = db_session.query(User).get(2)
    data = {
        "service_user": "some_different_username"
    }
    resp = test_client.put('/streetview/services/{}/'.format(streetview_service_resource_fixture.service),
                           json=data,
                           headers={'x-jwt-assertion-test': u2.jwt})
    assert resp.status_code == 404


def test_create_organization(test_client, streetview_service_resource_fixture):
    u1 = db_session.query(User).get(1)
    data = {
        "name": "my_name",
        "slug": "my_slug",
        "key": "my_key"

    }
    resp = test_client.post(
        '/streetview/services/{}/organization/'.format(streetview_service_resource_fixture.service),
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


def test_create_organization_illegal_access(test_client, streetview_service_resource_fixture):
    u2 = db_session.query(User).get(2)
    data = {
        "name": "my_name",
        "slug": "my_slug",
        "key": "my_key"

    }
    resp = test_client.post(
        '/streetview/services/{}/organization/'.format(streetview_service_resource_fixture.service),
        json=data,
        headers={'x-jwt-assertion-test': u2.jwt})
    assert resp.status_code == 404


def test_delete_organization(test_client, organization_fixture):
    u1 = db_session.query(User).get(1)
    resp = test_client.delete(
        f'streetview/services/{organization_fixture.streetview.service}/organization/{organization_fixture.id}/',
        headers={'x-jwt-assertion-test': u1.jwt})
    assert resp.status_code == 200
    assert db_session.query(StreetviewOrganization).first() is None


def test_delete_organization_illegal_access(test_client, organization_fixture):
    u2 = db_session.query(User).get(2)
    resp = test_client.delete(
        f'streetview/services/{organization_fixture.streetview.service}/organization/{organization_fixture.id}/',
        headers={'x-jwt-assertion-test': u2.jwt})
    assert resp.status_code == 404


def test_delete_instance(test_client, instance_fixture):
    u1 = db_session.query(User).get(1)
    resp = test_client.delete('streetview/instances/{}/'.format(instance_fixture.id),
                              headers={'x-jwt-assertion-test': u1.jwt})
    assert resp.status_code == 200
    assert db_session.query(StreetviewInstance).first() is None


def test_delete_instance_illegal_access(test_client, instance_fixture):
    u2 = db_session.query(User).get(2)
    resp = test_client.delete('streetview/instances/{}/'.format(instance_fixture.id),
                              headers={'x-jwt-assertion-test': u2.jwt})
    assert resp.status_code == 403

    u2 = db_session.query(User).get(2)
    resp = test_client.delete('streetview/instances/{}/'.format(1234),
                              headers={'x-jwt-assertion-test': u2.jwt})
    assert resp.status_code == 404


def test_add_sequence_to_instance(test_client,
                                  streetview_service_resource_fixture,
                                  organization_fixture):
    u1 = db_session.query(User).get(1)
    data = {
        "streetviewId": streetview_service_resource_fixture.id,
        "sequenceId": "seq_id",
        "organizationId": "orgid",
        "dir": {
            "system": "my_system",
            "path": "my_path"
        }
    }
    resp = test_client.post('/streetview/sequences/', json=data, headers={'x-jwt-assertion-test': u1.jwt})
    assert resp.status_code == 200

    streetview_instance = db_session.query(StreetviewInstance).first()
    assert len(streetview_instance.sequences) == 1
    sequence = streetview_instance.sequences[0]
    assert sequence.sequence_id == "seq_id"
    assert sequence.organization_id == "orgid"
    assert sequence.streetview_instance_id == streetview_service_resource_fixture.id


def test_add_sequence_to_existing_instance(test_client,
                                           streetview_service_resource_fixture,
                                           organization_fixture,
                                           instance_fixture):
    u1 = db_session.query(User).get(1)
    data = {
        "streetviewId": streetview_service_resource_fixture.id,
        "sequenceId": "seq_id",
        "organizationId": "ordid",
        "dir": {
            "system": instance_fixture.system_id,
            "path": instance_fixture.path
        }
    }
    resp = test_client.post('/streetview/sequences/', json=data, headers={'x-jwt-assertion-test': u1.jwt})
    assert resp.status_code == 200

    streetview_instance = db_session.query(StreetviewInstance).first()
    assert len(streetview_instance.sequences) == 1
    sequence = streetview_instance.sequences[0]
    assert sequence.sequence_id == "seq_id"
    assert sequence.organization_id == "ordid"
    assert sequence.streetview_instance_id == streetview_service_resource_fixture.id


def test_add_sequence_to_existing_instance_illegal_access(test_client,
                                                         streetview_service_resource_fixture,
                                                         organization_fixture,
                                                         instance_fixture):
    u2 = db_session.query(User).get(2)
    data = {
        "streetviewId": streetview_service_resource_fixture.id,
        "sequenceId": "seq_id",
        "organizationId": "ordid",
        "dir": {
            "system": instance_fixture.system_id,
            "path": instance_fixture.path
        }
    }
    resp = test_client.post('/streetview/sequences/', json=data, headers={'x-jwt-assertion-test': u2.jwt})
    assert resp.status_code == 403


def test_get_sequence(test_client, streetview_service_resource_fixture, sequence_fixture):
    u1 = db_session.query(User).get(1)
    resp = test_client.get('/streetview/sequences/{}/'.format(sequence_fixture.sequence_id),
                           headers={'x-jwt-assertion-test': u1.jwt})
    assert resp.status_code == 200
    assert resp.get_json() == {'bbox': None, 'end_date': None, 'id': 1, 'organization_id': '1',
                               'sequence_id': sequence_fixture.sequence_id, 'start_date': None, 'streetview_instance_id': 1}


def test_get_sequence_illegal_access(test_client, streetview_service_resource_fixture, sequence_fixture):
    u2 = db_session.query(User).get(2)
    resp = test_client.get('/streetview/sequences/{}/'.format(sequence_fixture.sequence_id),
                           headers={'x-jwt-assertion-test': u2.jwt})
    assert resp.status_code == 403


def test_update_sequence(test_client, streetview_service_resource_fixture, sequence_fixture):
    u1 = db_session.query(User).get(1)
    data = {
        "organization_id": "something_else",
    }
    # TODO differs from GET route where mapillary id is used
    resp = test_client.put(
        '/streetview/sequences/{}/'.format(sequence_fixture.id),
        json=data,
        headers={'x-jwt-assertion-test': u1.jwt})
    assert resp.status_code == 200
    updated = resp.get_json()
    assert updated["organization_id"] == "something_else"


def test_update_sequence_illegal_instance(test_client, streetview_service_resource_fixture, sequence_fixture):
    u2 = db_session.query(User).get(2)
    data = {
        "organization_id": "something_else",
    }
    resp = test_client.put(
        '/streetview/sequences/{}/'.format(sequence_fixture.id),
        json=data,
        headers={'x-jwt-assertion-test': u2.jwt})
    assert resp.status_code == 403

    resp = test_client.put(
        '/streetview/sequences/{}/'.format(1234),
        json=data,
        headers={'x-jwt-assertion-test': u2.jwt})
    assert resp.status_code == 404


def test_delete_sequence(test_client, streetview_service_resource_fixture, sequence_fixture):
    u1 = db_session.query(User).get(1)
    # TODO differs from GET route where mapillary id is used
    resp = test_client.delete(
        'streetview/instances/{}/'.format(sequence_fixture.id),
        headers={'x-jwt-assertion-test': u1.jwt})
    assert resp.status_code == 200
    assert db_session.query(StreetviewSequence).first() is None


def test_delete_sequence_illegal_access(test_client, streetview_service_resource_fixture, sequence_fixture):
    u2 = db_session.query(User).get(2)
    resp = test_client.delete(
        'streetview/instances/{}/'.format(sequence_fixture.id),
        headers={'x-jwt-assertion-test': u2.jwt})
    assert resp.status_code == 403


def test_publish(test_client, streetview_service_resource_fixture, organization_fixture, convert_to_potree_mock):
    u1 = db_session.query(User).get(1)
    data = {
        "service": streetview_service_resource_fixture.service,
        "organization_key": organization_fixture.key,
        "system_id": "mysystem",
        "path": "mypath"
    }
    resp = test_client.post('/streetview/publish/',
                            json=data,
                            headers={'x-jwt-assertion-test': u1.jwt})
    assert resp.status_code == 200
    assert resp.get_json() == {"message": "accepted"}
    convert_to_potree_mock.delay.assert_called_once()
