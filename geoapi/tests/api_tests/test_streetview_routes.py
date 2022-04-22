import pytest

from geoapi.db import db_session
from geoapi.models.users import User
from geoapi.models.streetview import Streetview, StreetviewOrganization
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
    resp = test_client.get('/streetview/{}/'.format(streetview_service_resource_fixture.service),
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
    resp = test_client.post('/streetview/{}/organization/'.format(streetview_service_resource_fixture.id),
                            json=data,
                            headers={'x-jwt-assertion-test': u1.jwt})
    assert resp.status_code == 200
    assert resp.get_json() == {'id': 1,'key': 'my_key','name': 'my_name',    'slug': 'my_slug',  'streetview_id': 1}

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


def test_post_streetview_sequences(test_client):
    u1 = db_session.query(User).get(1)
    data = {
        'dir': {
            'path': 'test path',
            'system': 'test system'
        },
        'service': 'mapillary',
        'sequences': ['test key 1', 'test key 2', 'test key 3', 'test key 4']
    }
    resp = test_client.post('/streetview/sequences/',
                            json=data,
                            headers={'x-jwt-assertion-test': u1.jwt})

    assert resp.status_code == 200
    assert len(data['sequences']) == 4


def test_delete_streetview_sequence(test_client):
    u1 = db_session.query(User).get(1)
    data = {
        'dir': {
            'path': 'test path',
            'system': 'test system'
        },
        'service': 'mapillary',
        'sequences': ['test key 1', 'test key 2', 'test key 3', 'test key 4']
    }

    resp = test_client.post('/streetview/sequences/',
                            json=data,
                            headers={'x-jwt-assertion-test': u1.jwt})

    resp = test_client.get('/streetview/',
                           headers={'x-jwt-assertion-test': u1.jwt})

    seq_id = resp.get_json()[0]['sequences'][0]['id']

    test_client.delete('/streetview/sequences/{}/'.format(seq_id),
                       headers={'x-jwt-assertion-test': u1.jwt})

    assert resp.status_code == 200
