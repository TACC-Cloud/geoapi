import pytest

from geoapi.db import db_session

from geoapi.services.streetview import StreetviewService
from geoapi.models import User


def test_create_streetview_token():
    user = db_session.query(User).get(1)
    StreetviewService.setToken(user, 'mapillary', 'test token')
    assert user.mapillary_jwt == 'test token'


def test_get_streetview_token():
    user = db_session.query(User).get(1)
    StreetviewService.setToken(user, 'mapillary', 'test token')
    tok = StreetviewService.getToken(user, 'mapillary')
    assert user.mapillary_jwt == tok


def test_create_streetview():
    user = db_session.query(User).get(1)
    streetview = StreetviewService.create(user.id, 'test system', 'test path')
    assert streetview.id is not None


def test_get_user_streetview():
    user = db_session.query(User).get(1)
    StreetviewService.create(user.id, 'test system', 'test path')
    StreetviewService.create(user.id, 'test system 2', 'test path 2')
    streetview_list = StreetviewService.getAll(user)
    assert len(streetview_list) == 2


def test_get_streetview_system_path():
    user = db_session.query(User).get(1)
    StreetviewService.create(user.id, 'test system', 'test path')
    StreetviewService.create(user.id, 'test system 2', 'test path 2')
    streetviews_from_path = StreetviewService.getFromSystemPath(user, 'test system 2', 'test path 2')
    assert streetviews_from_path[0].id == 2
    assert streetviews_from_path[0].system_id == 'test system 2'
    assert streetviews_from_path[0].path == 'test path 2'


def test_create_sequence():
    user = db_session.query(User).get(1)
    streetview = StreetviewService.create(user.id, 'test system', 'test path')
    sequence = StreetviewService.createSequence(streetview_id=streetview.id)
    assert len(streetview.sequences) == 1
    assert sequence.streetview_id == 1


def test_update_sequence():
    user = db_session.query(User).get(1)
    streetview = StreetviewService.create(user.id, 'test system', 'test path')
    sequence = StreetviewService.createSequence(streetview.id, service='service', sequence_key='test sequence key')
    data = {
        'sequence_key': 'new sequence key',
    }
    new_sequence = StreetviewService.updateSequence(sequence.id, data)
    assert new_sequence.id == sequence.id
    assert new_sequence.sequence_key == 'new sequence key'


def test_add_sequence_to_path():
    user = db_session.query(User).get(1)
    streetview = StreetviewService.create(user.id, 'test system', 'test path')
    data = {
        'dir': {
            'path': 'test path',
            'system': 'test system'
        },
        'service': 'mapillary',
        'sequences': ['test key 1', 'test key 2', 'test key 3', 'test key 4'],
        'service': 'mapillary'
    }
    StreetviewService.addSequenceToStreetview(user, data)
    assert len(streetview.sequences) == 4
