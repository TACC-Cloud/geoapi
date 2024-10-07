
class InvalidGeoJSON(Exception):
    """ Custom exception to notify caller they have supplied Invalid GeoJson """
    pass


class InvalidEXIFData(Exception):
    """ Custom exception to notify caller they have supplied Invalid EXIF data """
    pass


class InvalidCoordinateReferenceSystem(Exception):
    """ Custom exception to notify caller they have supplied data with missing or invalid coordinate reference system"""
    pass


class ProjectSystemPathWatchFilesAlreadyExists(Exception):
    """ Project with watch_files True already exists for this system path"""
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


class GetUsersForProjectNotSupported(Exception):
    """ Getting users for a project is not supported) """
    pass


class AuthenticationIssue(Exception):
    """ Issue during auth process"""
    def __init__(self, message="Unknown error in auth"):
        self.message = message
        super().__init__(self.message)
