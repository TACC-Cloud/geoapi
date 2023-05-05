import base64
import re
import io
import PIL
from PIL import Image
from PIL.Image import Image as PILImage
import exifread

from typing import Tuple, IO, AnyStr
from dataclasses import dataclass
from geoapi.exceptions import InvalidEXIFData
from geoapi.log import logger


@dataclass
class ImageData:
    thumb: PILImage
    resized: PILImage
    coordinates: Tuple[float, float]


@dataclass
class ImageOverlay:
    thumb: PILImage
    original: PILImage


class ImageService:

    THUMBSIZE = (100, 100)
    RESIZE = (1024, 1024)

    @staticmethod
    def processBase64(encoded: AnyStr) -> ImageData:
        image_data = re.sub('^data:image/.+;base64,', '', encoded)
        thumb = Image.open(io.BytesIO(base64.b64decode(image_data)))
        thumb.thumbnail(ImageService.THUMBSIZE)
        resized = Image.open(io.BytesIO(base64.b64decode(image_data)))
        resized.thumbnail(ImageService.RESIZE, PIL.Image.ANTIALIAS)
        imdata = ImageData(thumb, resized, (0, 0))
        return imdata

    @staticmethod
    def processImage(fileObj: IO) -> ImageData:
        """
        Resize and get the EXIF GeoLocation from an image

        Image need geolocation information. If missing, then
        get_exif_location raises InvalidEXIFData.

        :param fileObj:
        :return:
        """
        imdata = ImageService.resizeImage(fileObj)
        exif_loc = get_exif_location(fileObj)
        imdata.coordinates = exif_loc
        return imdata

    @staticmethod
    def resizeImage(fileObj: IO) -> ImageData:

        thumb = _fix_orientation(fileObj)
        thumb.thumbnail(ImageService.THUMBSIZE)
        resized = _fix_orientation(fileObj)
        resized.thumbnail(ImageService.RESIZE, PIL.Image.ANTIALIAS)
        imdata = ImageData(thumb, resized, (0, 0))
        return imdata

    @staticmethod
    def processOverlay(fileObj: IO) -> ImageOverlay:
        thumb = Image.open(fileObj)
        thumb.thumbnail(ImageService.THUMBSIZE)
        original = Image.open(fileObj)
        imdata = ImageOverlay(thumb, original)
        return imdata


def _fix_orientation(fileObj: IO) -> PILImage:
    # from https://github.com/ianare/exif-py#usage-example
    im = Image.open(fileObj)
    tags = exifread.process_file(fileObj, details=False)
    if "Image Orientation" in tags.keys():
        logger.info("yes Image Orientation")
    else:
        logger.info("no Image Orientation")

    if "Image Orientation" in tags.keys():
        orientation = tags["Image Orientation"]
        logger.info("Orientation: %s (%s)", orientation, orientation.values)
        val = orientation.values
        if 2 in val:
            val += [4, 3]
        if 5 in val:
            val += [4, 6]
        if 7 in val:
            val += [4, 8]
        if 3 in val:
            logger.info("Rotating by 180 degrees.")
            im = im.transpose(Image.ROTATE_180)
        if 4 in val:
            logger.info("Mirroring horizontally.")
            im = im.transpose(Image.FLIP_TOP_BOTTOM)
        if 6 in val:
            logger.info("Rotating by 270 degrees.")
            im = im.transpose(Image.ROTATE_270)
        if 8 in val:
            logger.info("Rotating by 90 degrees.")
            im = im.transpose(Image.ROTATE_90)
    return im


def _convert_to_degrees(value):
    """
    Helper function to convert the GPS coordinates stored in the EXIF to decimal degrees in float format
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


def _get_if_exist(data, key):
    if key in data:
        return data[key]

    return None


def _convert_to_degress(value):
    """
    Helper function to convert the GPS coordinates stored in the EXIF to degress in float format
    :param value:
    :type value: exifread.utils.Ratio
    :rtype: float
    """
    d = float(value.values[0].num) / float(value.values[0].den)
    m = float(value.values[1].num) / float(value.values[1].den)
    s = float(value.values[2].num) / float(value.values[2].den)

    return d + (m / 60.0) + (s / 3600.0)


def get_exif_location(image):
    """
    Returns the latitude and longitude, if available, from the provided exif_data (obtained through get_exif_data above)

    raises: InvalidEXIFData: if geospatial data missing

    """
    exif_data = exifread.process_file(image)
    lat = None
    lon = None

    gps_latitude = _get_if_exist(exif_data, 'GPS GPSLatitude')
    gps_latitude_ref = _get_if_exist(exif_data, 'GPS GPSLatitudeRef')
    gps_longitude = _get_if_exist(exif_data, 'GPS GPSLongitude')
    gps_longitude_ref = _get_if_exist(exif_data, 'GPS GPSLongitudeRef')

    if gps_latitude and gps_latitude_ref and gps_longitude and gps_longitude_ref:
        lat = _convert_to_degress(gps_latitude)
        if gps_latitude_ref.values[0] != 'N':
            lat = 0 - lat

        lon = _convert_to_degress(gps_longitude)
        if gps_longitude_ref.values[0] != 'E':
            lon = 0 - lon

    if not lat or not lon:
        raise InvalidEXIFData
    return lon, lat
