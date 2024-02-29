import pytest
import os
import tempfile
from unittest.mock import patch, call
from geoapi.exceptions import MissingServiceAccount
from geoapi.utils.agave import service_account_client, AgaveUtils, AgaveFileGetError


@pytest.mark.skip(reason="Skipping until https://tacc-main.atlassian.net/browse/WG-257")
def test_service_account_client():
    service_account = service_account_client("designsafe")
    assert "ABCDEFG12344" in service_account.client.headers['Authorization']

    service_account = service_account_client("DesignSafe")
    assert "ABCDEFG12344" in service_account.client.headers['Authorization']


def test_service_account_client_missing():
    with pytest.raises(MissingServiceAccount):
        service_account_client("non_existing_tenant")


@pytest.fixture(scope="function")
def retry_sleep_seconds_mock():
    with patch('geoapi.utils.agave.SLEEP_SECONDS_BETWEEN_RETRY', 0) as sleep_mock:
        yield sleep_mock


def test_get_file(user1, tapis_url, requests_mock, retry_sleep_seconds_mock, image_file_fixture):
    system = "system"
    path = "path"
    requests_mock.get(tapis_url + f"/v3/files/content/{system}/{path}",
                      status_code=200,
                      body=image_file_fixture)
    agave_utils = AgaveUtils(user1)
    agave_utils.getFile(system, path)


@pytest.mark.skip(reason="Skipping until https://tacc-main.atlassian.net/browse/WG-257")
def test_get_file_to_path(requests_mock, tapis_url, projects_fixture, retry_sleep_seconds_mock, image_file_fixture):
    system = "system"
    path = "path"
    requests_mock.get(tapis_url + f"/v3/files/content/{system}/{path}",
                      status_code=200,
                      body=image_file_fixture)

    with tempfile.TemporaryDirectory() as temp_dir:
        to_path = os.path.join(temp_dir, "test.jpg")

        agave_utils = AgaveUtils()
        agave_utils.get_file_to_path(system, path, to_path)
        assert os.path.isfile(to_path)


@pytest.mark.skip(reason="Skipping until https://tacc-main.atlassian.net/browse/WG-257")
def test_get_file_retry_after_first_attempt(requests_mock, retry_sleep_seconds_mock, image_file_fixture):
    system = "system"
    path = "path"
    responses = [{'status_code': 500} for _ in range(2)]
    responses.append({"status_code": 200, "body": image_file_fixture})
    requests_mock.get(AgaveUtils.BASE_URL + f"/v3/files/content/{system}/{path}", responses)
    agave_utils = AgaveUtils()
    agave_utils.getFile(system, path)


def test_get_file_retry_too_many_attempts(user1, tapis_url, requests_mock, retry_sleep_seconds_mock):
    system = "system"
    path = "path"
    bad_response = [{'status_code': 500} for _ in range(10)]
    requests_mock.get(tapis_url + f"/v3/files/content/{system}/{path}",
                      bad_response)
    agave_utils = AgaveUtils(user1)
    with pytest.raises(AgaveFileGetError):
        agave_utils.getFile(system, path)
