import os
import PIL
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from typing import Tuple, IO
from dataclasses import dataclass
from geoapi.exceptions import InvalidEXIFData
from geoapi.settings import settings

@dataclass
class ImageData:
    thumb: Image
    resized: Image
    coordinates: Tuple[float, float]


class ImageService:

    THUMBSIZE = (100, 100)
    RESIZE = (1024, 1024)

    @staticmethod
    def processImage(fileObj: IO) -> ImageData:

        try:
            thumb = Image.open(fileObj)
            thumb.thumbnail(ImageService.THUMBSIZE)
            resized = Image.open(fileObj)
            resized.thumbnail(ImageService.RESIZE, PIL.Image.ANTIALIAS)
            exif_loc = get_exif_location(thumb)
            imdata = ImageData(thumb, resized, exif_loc)
            return imdata
        except:
            raise InvalidEXIFData()



def get_exif_data(image):
    """Returns a dictionary from the exif data of an PIL Image item. Also converts the GPS Tags"""
    exif_data = {}
    info = image._getexif()
    for tag, value in info.items():
        decoded = TAGS.get(tag, tag)
        if decoded == "GPSInfo":
            for t in value:
                sub_decoded = GPSTAGS.get(t, t)
                exif_data[sub_decoded] = value[t]
        else:
            exif_data[decoded] = value

    return exif_data

def _convert_to_degress(value):
    """
    Helper function to convert the GPS coordinates stored in the EXIF to degress in float format
    :param value:
    :type value: tuple
    :rtype: float
    """
    d0 = value[0][0]
    d1 = value[0][1]
    d = float(d0) / float(d1)

    m0 = value[1][0]
    m1 = value[1][1]
    m = float(m0) / float(m1)

    s0 = value[2][0]
    s1 = value[2][1]
    s = float(s0) / float(s1)

    return d + (m / 60.0) + (s / 3600.0)


def get_exif_location(image):
    """
    Returns the latitude and longitude, if available, from the provided exif_data (obtained through get_exif_data above)
    """
    exif_data = get_exif_data(image)
    lat = None
    lon = None

    gps_latitude = exif_data['GPSLatitude']
    gps_latitude_ref = exif_data['GPSLatitudeRef']
    gps_longitude = exif_data['GPSLongitude']
    gps_longitude_ref = exif_data['GPSLongitudeRef']

    lat = _convert_to_degress(gps_latitude)
    if gps_latitude_ref != 'N':
        lat = 0 - lat

    lon = _convert_to_degress(gps_longitude)
    if gps_longitude_ref != 'E':
        lon = 0 - lon

    return lat, lon