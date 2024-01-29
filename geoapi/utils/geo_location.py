from dataclasses import dataclass
from geoapi.utils.agave import get_metadata_using_service_account
from geoapi.models import User
from typing import Optional

from geoapi.log import logger


@dataclass
class GeoLocation:
    """ Represents a geographical location with latitude and longitude."""
    latitude: float
    longitude: float


def parse_rapid_geolocation(geolocation_metadata):
    first_coordinates = geolocation_metadata[0]
    lat = first_coordinates["latitude"]
    lon = first_coordinates["longitude"]
    return GeoLocation(lat, lon)


def get_geolocation_from_file_metadata(user: User, system_id: str, path: str) -> Optional[GeoLocation]:
    """
    Retrieves the geolocation from Tapis file metadata.

    This function attempts to extract geolocation information from the metadata of a file.
    If the metadata does not exist or does not contain geolocation information, None is returned.

    Note: This metadata is typically written by the Rapp application.

    :return: A GeoLocation object if geolocation information is found; otherwise, None.
    """
    meta = get_metadata_using_service_account(user.tenant_id, system_id, path)
    if meta and "geolocation" in meta and len(meta["geolocation"]) > 1:
        return parse_rapid_geolocation(meta.get("geolocation"))

    return None
