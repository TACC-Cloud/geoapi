from geoapi.db import db_session
from geoapi.models.users import User
from geoapi.models import Streetview

from unittest.mock import patch


def test_post_streetview_token(test_client, projects_fixture):
    u1 = db_session.query(User).get(1)
    data = {
        "token": "test token"
    }
    resp = test_client.post('/streetview/{}/token/'.format('mapillary'),
                            json=data,
                            headers={'x-jwt-assertion-test': u1.jwt})

    assert resp.status_code == 200


def test_delete_streetview_token(test_client, projects_fixture):
    u1 = db_session.query(User).get(1)
    data = {
        'token': 'test token'
    }
    test_client.post('/streetview/{}/token/'.format('mapillary'),
                     json=data,
                     headers={'x-jwt-assertion-test': u1.jwt})

    resp = test_client.delete('/streetview/{}/token/'.format('mapillary'),
                              headers={'x-jwt-assertion-test': u1.jwt})

    assert resp.status_code == 200


def test_get_streetview_sequences(test_client, projects_fixture):
    u1 = db_session.query(User).get(1)
    resp = test_client.get('/streetview/',
                           headers={'x-jwt-assertion-test': u1.jwt})

    assert resp.status_code == 200


def test_post_streetview_sequences(test_client, projects_fixture):
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


def test_delete_streetview_sequence(test_client, projects_fixture):
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
