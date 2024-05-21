from geoapi.custom.designsafe.project import on_project_creation, on_project_deletion
from geoapi.services.features import FeaturesService
from geoapi.settings import settings
from geoapi.db import db_session
from urllib.parse import quote
import json
import os


def test_on_project_creation(tapis_url, requests_mock, user1, observable_projects_fixture):
    project = observable_projects_fixture.project
    create_file_url = tapis_url + quote(f"/files/media/system/{project.system_id}{project.system_path}/")
    requests_mock.post(create_file_url)

    designsafe_uuid = project.system_id[len("project-"):]

    metadata_url = settings.DESIGNSAFE_URL + f"/api/projects/v2/{designsafe_uuid}/"
    requests_mock.get(metadata_url, json={"baseProject": {"value": {"hazmapperMaps": []}}})
    requests_mock.post(metadata_url)

    on_project_creation(db_session, user1, project)

    assert len(FeaturesService.getTileServers(db_session, projectId=project.id)) == 2

    assert len(requests_mock.request_history) == 3
    update_metadata_request = requests_mock.request_history[2]
    assert json.loads(update_metadata_request.text) == {'hazmapperMaps':
                                                        [{"name": project.name,
                                                          "uuid": str(project.uuid),
                                                          "path": project.system_path,
                                                          "deployment": os.getenv("APP_ENV")}]}


def test_on_project_deletion(tapis_url, requests_mock, user1, observable_projects_fixture):
    project = observable_projects_fixture.project
    file_path = f"{project.system_path}/{project.system_file}.hazmapper"

    delete_file_url = tapis_url + quote(f"/files/media/system/{project.system_id}{file_path}")
    requests_mock.delete(delete_file_url)

    designsafe_uuid = project.system_id[len("project-"):]

    metadata_url = settings.DESIGNSAFE_URL + f"/api/projects/v2/{designsafe_uuid}/"
    requests_mock.get(
        metadata_url,
        json={
            "baseProject": {
                "value": {
                    "hazmapperMaps": [
                        {
                            "name": project.name,
                            "uuid": str(project.uuid),
                            "path": project.system_path,
                            "deployment": os.getenv("APP_ENV")
                        }
                    ]
                }
            }
        }
    )
    requests_mock.post(metadata_url)

    on_project_deletion(user1, project)

    assert len(requests_mock.request_history) == 3
    update_metadata_request = requests_mock.request_history[2]
    assert json.loads(update_metadata_request.text) == {'hazmapperMaps': []}
