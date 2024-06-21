from geoapi.tasks.streetview import _from_tapis
from geoapi.utils.agave import AgaveFileListing
from geoapi.utils.streetview import (get_project_streetview_dir, remove_project_streetview_dir)
from geoapi.db import db_session
from unittest.mock import patch, MagicMock
import os
import pytest
import uuid


@pytest.fixture(scope="function")
def agave_utils_with_image_file(image_file_fixture):
    with patch('geoapi.tasks.streetview.AgaveUtils.listing') as mock_listing, \
            patch('geoapi.tasks.streetview.AgaveUtils.get_file_context_manager') as mock_get_file_context_manager:
        filesListing = [
            AgaveFileListing({
                "path": "/testPath",
                "type": "dir",
                "lastModified": "2020-08-31T12:00:00Z"
            }),
            AgaveFileListing({
                "type": "file",
                "path": "/testPath/file.jpg",
                "lastModified": "2020-08-31T12:00:00Z"
            })
        ]
        mock_listing.return_value = filesListing
        mock_file_context_manager = MagicMock()
        mock_get_file_context_manager.return_value = mock_file_context_manager
        mock_file_context_manager.__enter__.return_value = image_file_fixture
        yield


@pytest.fixture
def mock_notifications_service():
    with patch('geoapi.tasks.streetview.NotificationsService') as MockNotificationsService:
        yield MockNotificationsService()


def test_get_file_to_path(user1, task_fixture, mock_notifications_service, agave_utils_with_image_file):
    system_id = "foo"
    path = "path/"
    task_uuid = uuid.uuid3(uuid.NAMESPACE_URL, system_id + path)

    _from_tapis(db_session, user1, task_uuid, system_id, path)

    assert len(os.listdir(get_project_streetview_dir(user1.id, task_uuid))) == 1
    remove_project_streetview_dir(user1.id, task_uuid)
