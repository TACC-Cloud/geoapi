from geoapi.utils.geo_location import get_geolocation_from_file_metadata, GeoLocation

import re

METADATA_ROUTE = re.compile(r"https://.*/api/filemeta/.*/.*")
SYSTEM = "SYSTEM"
PATH = "PATH"


def test_no_metadata(requests_mock, user1, db_session):
    response = {}
    requests_mock.get(METADATA_ROUTE, json=response)
    assert (
        get_geolocation_from_file_metadata(
            db_session, user1, system_id=SYSTEM, path=PATH
        )
        is None
    )


def test_metadata_but_no_geolocation(
    requests_mock, user1, tapis_metadata_without_geolocation, db_session
):
    requests_mock.get(METADATA_ROUTE, json=tapis_metadata_without_geolocation)

    assert (
        get_geolocation_from_file_metadata(
            db_session, user1, system_id=SYSTEM, path=PATH
        )
        is None
    )


def test_metadata_with_geolocation(
    requests_mock, user1, tapis_metadata_with_geolocation, db_session
):
    requests_mock.get(METADATA_ROUTE, json=tapis_metadata_with_geolocation)

    assert get_geolocation_from_file_metadata(
        db_session, user1, system_id=SYSTEM, path=PATH
    ) == GeoLocation(longitude=-122.30701480072206, latitude=47.65349416532335)
