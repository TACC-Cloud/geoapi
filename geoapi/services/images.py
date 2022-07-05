import base64
import re
import io
import PIL
from PIL import Image
from PIL.Image import Image as PILImage
from PIL.ExifTags import TAGS, GPSTAGS

from typing import Tuple, IO, AnyStr
from dataclasses import dataclass
from geoapi.exceptions import InvalidEXIFData
from geoapi.log import logging

logger = logging.getLogger(__name__)


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
        :param fileObj:
        :return:
        """

        try:
            imdata = ImageService.resizeImage(fileObj)
            exif_loc = get_exif_location(imdata.resized)
            imdata.coordinates = exif_loc
            return imdata
        except:  # noqa: E722
            raise InvalidEXIFData()

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
    im = Image.open(fileObj)
    try:
        image_exif = im._getexif()
        # 274 is a magic number here and I don't like it. Alternatively
        # can do something like:
        #         for orientation in ExifTags.TAGS.keys():
        #             if ExifTags.TAGS[orientation] == 'Orientation': break
        # That will also return 274, the key for the value of 'Orientation'. I have no idea
        # why PIL would arrange things that way, it seems a bit insane.
        image_orientation = image_exif[274]
        if image_orientation in (2, '2'):
            return im.transpose(Image.FLIP_LEFT_RIGHT)
        elif image_orientation in (3, '3'):
            return im.transpose(Image.ROTATE_180)
        elif image_orientation in (4, '4'):
            return im.transpose(Image.FLIP_TOP_BOTTOM)
        elif image_orientation in (5, '5'):
            return im.transpose(Image.ROTATE_90).transpose(Image.FLIP_TOP_BOTTOM)
        elif image_orientation in (6, '6'):
            return im.transpose(Image.ROTATE_270)
        elif image_orientation in (7, '7'):
            return im.transpose(Image.ROTATE_270).transpose(Image.FLIP_TOP_BOTTOM)
        elif image_orientation in (8, '8'):
            return im.transpose(Image.ROTATE_90)
        else:
            return im
    except (KeyError, AttributeError, TypeError, IndexError):
        return im


def get_exif_data(image):
    """Returns a dictionary from the exif data of an PIL Image item. Also converts the GPS Tags"""
    exif_data = {}
    info = image.getexif()
    for tag, value in info.items():
        decoded = TAGS.get(tag, tag)
        if decoded == "GPSInfo":
            for t in value:
                sub_decoded = GPSTAGS.get(t, t)
                exif_data[sub_decoded] = value[t]
        else:
            exif_data[decoded] = value

    return exif_data


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

    lat = _convert_to_degrees(gps_latitude)
    if gps_latitude_ref != 'N':
        lat = 0 - lat

    lon = _convert_to_degrees(gps_longitude)
    if gps_longitude_ref != 'E':
        lon = 0 - lon

    return lon, lat
