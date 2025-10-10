import pytest
from geoapi.services.users import UserService
from geoapi.services.projects import ProjectsService
from geoapi.exceptions import ApiException
from geoapi.models.project import ProjectUser


def test_user_get(userdata, db_session):
    user = UserService.getUser(db_session, "test1", "test")
    assert user.id is not None
    assert user.created is not None


def test_user_create(userdata, db_session):
    user = UserService.create(
        database_session=db_session,
        username="newUser",
        access_token="testjwt",
        tenant="test",
    )
    assert user.id is not None
    assert user.created is not None
    assert user.username == "newUser"
    assert user.auth.access_token == "testjwt"


def test_projects_for_user(user1, db_session):
    data = {"name": "new project", "description": "test"}
    ProjectsService.create(db_session, data, user1)
    my_projects = ProjectsService.list(db_session, user1)
    assert len(my_projects) == 1
    assert my_projects[0].name == "new project"


def test_add_new_user_to_project(user1, db_session):
    data = {"name": "new project", "description": "test"}
    proj = ProjectsService.create(db_session, data, user1)
    ProjectsService.addUserToProject(db_session, proj.id, "newUser", admin=False)
    proj = ProjectsService.get(database_session=db_session, project_id=proj.id)
    assert len(proj.users) == 2


def test_add_existing_user_to_project(user1, user2, projects_fixture, db_session):
    assert not UserService.canAccess(db_session, user2, projects_fixture.id)

    ProjectsService.addUserToProject(
        database_session=db_session,
        projectId=projects_fixture.id,
        username=user2.username,
        admin=False,
    )
    assert UserService.canAccess(db_session, user2, projects_fixture.id)
    project_user = (
        db_session.query(ProjectUser)
        .filter(ProjectUser.project_id == projects_fixture.id)
        .filter(ProjectUser.user_id == user2.id)
        .one_or_none()
    )
    assert project_user.admin is False
    assert UserService.canAccess(db_session, user1, projects_fixture.id)


def test_add_existing_user_to_project_as_admin(
    user1, user2, projects_fixture, db_session
):
    assert not UserService.canAccess(db_session, user2, projects_fixture.id)

    ProjectsService.addUserToProject(
        database_session=db_session,
        projectId=projects_fixture.id,
        username=user2.username,
        admin=True,
    )
    assert UserService.canAccess(db_session, user2, projects_fixture.id)
    project_user = (
        db_session.query(ProjectUser)
        .filter(ProjectUser.project_id == projects_fixture.id)
        .filter(ProjectUser.user_id == user2.id)
        .one_or_none()
    )
    assert project_user.admin is True
    assert UserService.canAccess(db_session, user1, projects_fixture.id)


def test_remove_user(projects_fixture, db_session):
    ProjectsService.addUserToProject(
        db_session, projects_fixture.id, "newUser", admin=False
    )
    assert len(projects_fixture.users) == 2
    ProjectsService.removeUserFromProject(db_session, projects_fixture.id, "newUser")
    assert len(projects_fixture.users) == 1


def test_remove_missing_user_failure(projects_fixture, db_session):
    ProjectsService.addUserToProject(
        db_session, projects_fixture.id, "newUser", admin=False
    )
    assert len(projects_fixture.users) == 2
    with pytest.raises(ApiException):
        ProjectsService.removeUserFromProject(
            db_session, projects_fixture.id, "someOtherUser"
        )
    assert len(projects_fixture.users) == 2


def test_remove_user_with_only_one_user_failure(projects_fixture, db_session):
    with pytest.raises(ApiException):
        ProjectsService.removeUserFromProject(db_session, projects_fixture.id, "test1")
    assert len(projects_fixture.users) == 1


def test_remove_last_user_with_jwt_from_watch_users_project_failure(
    watch_content_users_projects_fixture, db_session
):
    project = watch_content_users_projects_fixture
    ProjectsService.addUserToProject(db_session, project.id, "newUser", admin=False)
    assert len(project.users) == 2
    with pytest.raises(ApiException):
        ProjectsService.removeUserFromProject(
            db_session, project.id, project.users[0].username
        )
    assert len(project.users) == 2
