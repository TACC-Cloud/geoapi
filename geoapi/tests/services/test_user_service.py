from geoapi.services.users import UserService


def test_is_admin_or_creator(user1, user2, projects_fixture, projects_fixture2):
    assert UserService.canAccess(user1, projects_fixture.id)
    assert UserService.is_admin_or_creator(user1, projects_fixture.id)
    assert not UserService.canAccess(user2, projects_fixture.id)
    assert not UserService.is_admin_or_creator(user2, projects_fixture.id)


def test_is_admin_or_creator2(user1, user2, projects_fixture, projects_fixture2):
    assert UserService.canAccess(user1, projects_fixture2.id)
    assert UserService.is_admin_or_creator(user1, projects_fixture2.id)
    assert UserService.canAccess(user2, projects_fixture2.id)
    assert not UserService.is_admin_or_creator(user2, projects_fixture2.id)
