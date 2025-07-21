from geoapi.models import User


def test_get_all_tasks(test_client, projects_fixture, task_fixture, db_session):
    u1 = db_session.get(User, 1)
    resp = test_client.get("/projects/1/tasks/", headers={"X-Tapis-Token": u1.jwt})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    task = data[0]
    assert task["status"] == task_fixture.status
    assert task["description"] == task_fixture.description
