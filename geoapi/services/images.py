import base64
import re
import io
import xml.etree.ElementTree as ET
import PIL
from PIL import Image
from PIL.Image import Image as PILImage
from PIL.ExifTags import TAGS, GPSTAGS

from typing import Tuple, IO, AnyStr, Dict
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
        except:
            raise InvalidEXIFData()

    @staticmethod
    def resizeImage(fileObj: IO) -> ImageData:

        thumb = _fix_orientation(fileObj)
        thumb.thumbnail(ImageService.THUMBSIZE)
        resized = _fix_orientation(fileObj)
        resized.thumbnail(ImageService.RESIZE, PIL.Image.ANTIALIAS)
        imdata = ImageData(thumb, resized, (0,0))
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

def parse(val):
    """parse literal to actual value"""
    literal = {
        'True': True,
        'False': False
    }
    if val in literal:
        return literal.get(val)
    elif val.isdigit():
        return int(val)
    else:
        try:
            return float(val)
        except ValueError:
            return val


# TODO: Refactor so that it would just get data
#       and is_gpano should check if it has gpano
#       and this should be get_xmp_data
# def get_xmp_data(image):
def is_gpano(fileObj):
    image = Image.open(fileObj)

    ns = {
        'GPano': 'http://ns.google.com/photos/1.0/panorama/',
        'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#'
    }

    metainfo = {
        TAGS[k]: v
        for k, v in image._getexif().items()
        if k in TAGS
    }

    pano_prefix = '{%s}' % ns['GPano']

    for segment, content in image.applist:
        # print(type(content))
        # print(content)
        marker, body = content.split(b'\x00', 1)
        # print(body)
        # print(marker)
        if segment == 'APP1' and marker == b'http://ns.adobe.com/xap/1.0/':
            return True
            # print(body)
            # root = ET.fromstring(body)
            # print(root)
            # node = root.find('rdf:RDF', ns).find('rdf:Description', ns)
            # metainfo.update({key[len(pano_prefix):]: parse(node.get(key))
            #                  for key in node.keys() if key.startswith(pano_prefix)})
            # print("awesome!")
    return False

    # print('\n'.join(['{0:32} {1}'.format(item, metainfo[item]) for item in metainfo]))

# def has_gpano(image):
#     xmp = get_xmp_data(image)
#     xmp['gpano']
#     return true
