
class InvalidGeoJSON(Exception):
    """ Custom exception to notify caller they have supplied Invalid GeoJson """
    pass

class InvalidEXIFData(Exception):
    """ Custom exception to notify caller they have supplied Invalid EXIF data """
    pass

class ApiException(Exception):
    """ A generic exception from the api"""
    pass