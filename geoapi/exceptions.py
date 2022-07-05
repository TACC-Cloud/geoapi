
class InvalidGeoJSON(Exception):
    """ Custom exception to notify caller they have supplied Invalid GeoJson """
    pass


class InvalidEXIFData(Exception):
    """ Custom exception to notify caller they have supplied Invalid EXIF data """
    pass


class InvalidCoordinateReferenceSystem(Exception):
    """ Custom exception to notify caller they have supplied data with missing or invalid coordinate reference system"""
    pass


class ObservableProjectAlreadyExists(Exception):
    """ Observable Project already exists for this path"""
    pass


class MissingServiceAccount(Exception):
    """ No service account for this tenant """
    pass


class ApiException(Exception):
    """ A generic exception from the api"""
    pass


class StreetviewAuthException(Exception):
    """ Not logged in to streetview service """
    pass


class StreetviewLimitException(Exception):
    """ Exceed concurrent streetview publish limit """
    pass


class StreetviewExistsException(Exception):
    """ Already published the streetview assets from a system/path """
    pass
