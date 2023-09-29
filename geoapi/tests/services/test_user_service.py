from geoapi.services.users import UserService
from geoapi.db import db_session


def test_is_admin_or_creator(user1, user2, projects_fixture, projects_fixture2):
    assert UserService.canAccess(db_session, user1, projects_fixture.id)
    assert UserService.is_admin_or_creator(db_session, user1, projects_fixture.id)
    assert not UserService.canAccess(db_session, user2, projects_fixture.id)
    assert not UserService.is_admin_or_creator(db_session, user2, projects_fixture.id)


def test_is_admin_or_creator2(user1, user2, projects_fixture, projects_fixture2):
    assert UserService.canAccess(db_session, user1, projects_fixture2.id)
    assert UserService.is_admin_or_creator(db_session, user1, projects_fixture2.id)
    assert UserService.canAccess(db_session, user2, projects_fixture2.id)
    assert not UserService.is_admin_or_creator(db_session, user2, projects_fixture2.id)
