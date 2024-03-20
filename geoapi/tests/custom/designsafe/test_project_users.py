import os
import pytest
import json
from geoapi.custom.designsafe.project_users import get_system_users


@pytest.fixture()
def project_response(mocker):
    home = os.path.dirname(__file__)
    with open(os.path.join(home, '../../fixtures/designsafe_api_project.json'), 'rb') as f:
        mock_data = json.loads(f.read())

    # TODO_TAPISV3 https://tacc-main.atlassian.net/browse/WG-257 can be dropped later as we rely on requests_mock
    # in tests
    with mocker.patch('geoapi.custom.designsafe.project_users.get_project_data', return_value=mock_data["value"]):
        yield mock_data


@pytest.fixture()
def project_response_with_duplicate_users(mocker):
    home = os.path.dirname(__file__)
    with open(os.path.join(home, '../../fixtures/designsafe_api_project_with_duplicate_users.json'), 'rb') as f:
        mock_data = json.loads(f.read())

    # TODO_TAPISV3 https://tacc-main.atlassian.net/browse/WG-257 can be dropped later as we rely on equests_mock
    # in tests
    with mocker.patch('geoapi.custom.designsafe.project_users.get_project_data', return_value=mock_data["value"]):
        yield mock_data["value"]


def test_get_system_users(requests_mock, user1, project_response):
    uuid = "5752672753351626260-242ac118-0001-014"
    requests_mock.get(f"https://agave.designsafe-ci.org/projects/v2/{uuid}/", json=project_response)

    users = get_system_users(user1, system_id=f"project-{uuid}")
    users_as_list_of_dict = [{u.username: u.admin} for u in users]
    assert users_as_list_of_dict == [{'user_pi': True}, {'user_copi': True}, {'user3': False}, {'user4': False}]

    users = get_system_users(user1, system_id=f"project-{uuid}")
    users_as_list_of_dict = [{u.username: u.admin} for u in users]
    assert users_as_list_of_dict == [{'user_pi': True}, {'user_copi': True}, {'user3': False}, {'user4': False}]


def test_get_system_users_duplicate(requests_mock, user1, project_response_with_duplicate_users):
    uuid = "5752672753351626260-242ac118-0001-014"
    requests_mock.get(f"https://agave.designsafe-ci.org/projects/v2/{uuid}/", json=project_response_with_duplicate_users)

    users = get_system_users(user1, system_id=f"project-{uuid}")
    users_as_list_of_dict = [{u.username: u.admin} for u in users]
    assert users_as_list_of_dict == [{'user_pi': True},
                                     {'user_copi_1': True},
                                     {'user_copi_2': True},
                                     {'user4': False},
                                     {'user5': True}]
