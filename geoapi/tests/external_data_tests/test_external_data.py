from tempfile import NamedTemporaryFile
from unittest.mock import MagicMock, patch, create_autospec

from geoapi.models import User, Project, Feature

from geoapi.db import db_session

from geoapi.tasks.external_data import import_from_agave

from geoapi.utils.agave import AgaveFileListing

@patch("geoapi.tasks.external_data.AgaveUtils")
def test_external_data_good_files(MockAgaveUtils, userdata, projects_fixture, geojson_file_fixture):
    filesListing = [
        AgaveFileListing({
            "system": "testSystem",
            "path": "/testPath",
            "type": "dir",
            "length": 4,
            "_links": "links",
            "mimeType": "folder"
        }),
        AgaveFileListing({
            "system": "testSystem",
            "type": "file",
            "length": 4096,
            "path": "/testPath/file.json",
            "_links": "links",
            "mimeType": "application/json"
        })
    ]
    u1 = db_session.query(User).filter(User.username == "test1").first()
    proj = db_session.query(Project).get(1)
    MockAgaveUtils().listing.return_value = filesListing
    MockAgaveUtils().getFile.return_value = geojson_file_fixture
    import_from_agave(u1, "testSystem", "/testPath", proj)
    features = db_session.query(Feature).all()
    # the test geojson has 3 features in it
    assert len(features) == 3
    # This should only have been called once, since there is only
    # one FILE in the listing
    assert MockAgaveUtils().getFile.called_once()





