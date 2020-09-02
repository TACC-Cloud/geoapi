
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

class ApiException(Exception):
    """ A generic exception from the api"""
    pass