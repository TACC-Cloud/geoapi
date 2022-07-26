import pytest
from unittest.mock import patch
from geoapi.exceptions import MissingServiceAccount
from geoapi.utils.agave import service_account_client, AgaveUtils, AgaveFileGetError


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


def test_get_file(requests_mock, retry_sleep_seconds_mock, image_file_fixture):
    system = "system"
    path = "path"
    requests_mock.get(AgaveUtils.BASE_URL + f"/files/media/system/{system}/{path}",
                      status_code=200,
                      body=image_file_fixture)
    agave_utils = AgaveUtils()
    agave_utils.getFile(system, path)


def test_get_file_retry_after_first_attempt(requests_mock, retry_sleep_seconds_mock, image_file_fixture):
    system = "system"
    path = "path"
    bad_response = [{'status_code': 500} for _ in range(2)]
    bad_response.append({"status_code": 200, "body": image_file_fixture})
    requests_mock.get(AgaveUtils.BASE_URL + f"/files/media/system/{system}/{path}",
                      bad_response)
    agave_utils = AgaveUtils()
    agave_utils.getFile(system, path)


def test_get_file_retry_too_many_attempts(requests_mock, retry_sleep_seconds_mock):
    system = "system"
    path = "path"
    bad_response = [{'status_code': 500} for _ in range(10)]
    requests_mock.get(AgaveUtils.BASE_URL + f"/files/media/system/{system}/{path}",
                      bad_response)
    agave_utils = AgaveUtils()
    with pytest.raises(AgaveFileGetError):
        agave_utils.getFile(system, path)
