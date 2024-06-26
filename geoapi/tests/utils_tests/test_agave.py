import pytest
import os
import tempfile
from unittest.mock import patch, call
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


def test_get_file_to_path(requests_mock, projects_fixture, retry_sleep_seconds_mock, image_file_fixture):
    system = "system"
    path = "path"
    requests_mock.get(AgaveUtils.BASE_URL + f"/files/media/system/{system}/{path}",
                      status_code=200,
                      body=image_file_fixture)

    with tempfile.TemporaryDirectory() as temp_dir:
        to_path = os.path.join(temp_dir, "test.jpg")

        agave_utils = AgaveUtils()
        agave_utils.get_file_to_path(system, path, to_path)
        assert os.path.isfile(to_path)


def test_get_file_retry_after_first_attempt(requests_mock, retry_sleep_seconds_mock, image_file_fixture):
    system = "system"
    path = "path"
    responses = [{'status_code': 500} for _ in range(2)]
    responses.append({"status_code": 200, "body": image_file_fixture})
    requests_mock.get(AgaveUtils.BASE_URL + f"/files/media/system/{system}/{path}", responses)
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


def test_get_file_using_service_account_for_CS_169(requests_mock, retry_sleep_seconds_mock, image_file_fixture):
    system = "system"
    path = "path.jpg"
    # api prod fails with 403 (i.e. CS_169)
    api_prod_mocked_file_service = requests_mock.get(AgaveUtils.BASE_URL + f"/files/media/system/{system}/{path}",
                                                     status_code=403)
    # service account's use of designsafe works (i.e. CS_169)
    designsafe_mocked_file_service = requests_mock.get("https://agave.designsafe-ci.org" + f"/files/media/system/{system}/{path}",
                                                       status_code=200,
                                                       body=image_file_fixture)
    agave_utils = AgaveUtils()
    with patch.object(AgaveUtils, 'systemsGet', return_value={"public": True}):
        with patch.object(agave_utils, '_get_file', wraps=agave_utils._get_file) as mock:
            agave_utils.getFile(system, path)

            # assert that there is a second call to use the service account if we get a 403 on a public folder
            mock.assert_has_calls([call(system, path), call(system, path, use_service_account=True)])
            assert api_prod_mocked_file_service.call_count == 1
            assert designsafe_mocked_file_service.call_count == 1
