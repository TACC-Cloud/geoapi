from geoapi.db import db_session
from geoapi.models.users import User
from geoapi.models import Streetview

from unittest.mock import patch


def post_user_streetview_token(test_client, projects_fixture):
    u1 = db_session.query(User).get(1)
    data = {
        'token': 'test token'
    }
    resp = test_client.post('/projects/1/users/{}/streetview/{}'.format(u1.username, 'mapillary'),
                            data=data,
                            headers={'x-jwt-assertion-test': u1.jwt})
    assert resp.status_code == 200


def delete_user_streetview_token(test_client, projects_fixture):
    u1 = db_session.query(User).get(1)
    data = {
        'token': 'test token'
    }
    test_client.post('/projects/1/users/{}/streetview/{}'.format(u1.username, 'mapillary'),
                     data=data,
                     headers={'x-jwt-assertion-test': u1.jwt})

    resp = test_client.delete('/projects/1/users/{}/streetview/{}'.format(u1.username, 'mapillary'),
                     headers={'x-jwt-assertion-test': u1.jwt})

    assert resp.status_code == 200


def get_user_streetview_sequences(test_client, projects_fixture):
    u1 = db_session.query(User).get(1)
    resp = test_client.get('/projects/1/users/{}/streetview/{}/sequences'.format(u1.username, 'mapillary'),
                           headers={'x-jwt-assertion-test': u1.jwt})

    assert resp.status_code == 200


def put_user_streetview_sequences(test_client, projects_fixture):
    u1 = db_session.query(User).get(1)
    data = {
        'dir': {
            'path': 'test path',
            'system': 'test system'
        },
        'sequences': ['test key 1', 'test key 2', 'test key 3', 'test key 4']
    }
    resp = test_client.put('/projects/1/users/{}/streetview/{}/sequences'.format(u1.username, 'mapillary'),
                           data=data,
                           headers={'x-jwt-assertion-test': u1.jwt})

    assert resp.status_code == 200
    assert len(data['sequences']) == 4


def delete_user_streetview_sequence(test_client, projects_fixture):
    u1 = db_session.query(User).get(1)
    data = {
        'dir': {
            'path': 'test path',
            'system': 'test system'
        },
        'sequences': ['test key 1', 'test key 2', 'test key 3', 'test key 4']
    }
    resp = test_client.put('/projects/1/users/{}/streetview/{}/sequences'.format(u1.username, 'mapillary'),
                           data=data,
                           headers={'x-jwt-assertion-test': u1.jwt})

    seq_id = data['sequences'][0].id
    resp = test_client.delete('/projects/1/users/{}/streetview/{}/sequences/{}'.format(u1.username, 'mapillary', seq_id),
                              headers={'x-jwt-assertion-test': u1.jwt})

    assert resp


# def post_user_streetview_upload(test_client, projects_fixture):
#     resp = test_client.get('/projects/1/users/{}/streetview/{}/sequences'.format(u1.username, 'mapillary'),
#     pass
