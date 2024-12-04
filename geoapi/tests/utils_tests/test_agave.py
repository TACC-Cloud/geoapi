import pytest
import os
import tempfile
from unittest.mock import patch
from geoapi.utils.agave import AgaveUtils, AgaveFileGetError
from geoapi.db import db_session


@pytest.fixture(scope="function")
def retry_sleep_seconds_mock():
    with patch("geoapi.utils.agave.SLEEP_SECONDS_BETWEEN_RETRY", 0) as sleep_mock:
        yield sleep_mock


def test_get_file(
    user1, tapis_url, requests_mock, retry_sleep_seconds_mock, image_file_fixture
):
    system = "system"
    path = "path"
    requests_mock.get(
        tapis_url + f"/v3/files/content/{system}/{path}",
        status_code=200,
        body=image_file_fixture,
    )
    agave_utils = AgaveUtils(db_session, user1)
    agave_utils.getFile(system, path)


def test_get_file_to_path(
    user1,
    requests_mock,
    tapis_url,
    projects_fixture,
    retry_sleep_seconds_mock,
    image_file_fixture,
):
    system = "system"
    path = "path"
    requests_mock.get(
        tapis_url + f"/v3/files/content/{system}/{path}",
        status_code=200,
        body=image_file_fixture,
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        to_path = os.path.join(temp_dir, "test.jpg")

        agave_utils = AgaveUtils(db_session, user1)
        agave_utils.get_file_to_path(system, path, to_path)
        assert os.path.isfile(to_path)


def test_get_file_retry_after_first_attempt(
    user1, tapis_url, requests_mock, retry_sleep_seconds_mock, image_file_fixture
):
    system = "system"
    path = "path"
    responses = [{"status_code": 500} for _ in range(2)]
    responses.append({"status_code": 200, "body": image_file_fixture})
    requests_mock.get(tapis_url + f"/v3/files/content/{system}/{path}", responses)
    agave_utils = AgaveUtils(db_session, user1)
    agave_utils.getFile(system, path)


def test_get_file_retry_too_many_attempts(
    user1, tapis_url, requests_mock, retry_sleep_seconds_mock
):
    system = "system"
    path = "path"
    bad_response = [{"status_code": 500} for _ in range(10)]
    requests_mock.get(tapis_url + f"/v3/files/content/{system}/{path}", bad_response)
    agave_utils = AgaveUtils(db_session, user1)
    with pytest.raises(AgaveFileGetError):
        agave_utils.getFile(system, path)
