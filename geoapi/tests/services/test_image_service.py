from geoapi.services.images import ImageService, get_exif_location
from geoapi.exceptions import InvalidEXIFData
from PIL import Image, ImageChops
from geoapi.utils.geo_location import GeoLocation
import pytest


def test_image_service_rotations(flipped_image_fixture, corrected_image_fixture):
    imdata = ImageService.processImage(flipped_image_fixture)
    imdata.resized.save("/tmp/test_it_is_rotated.jpg")
    original = Image.open(flipped_image_fixture)
    new = Image.open("/tmp/test_it_is_rotated.jpg")
    assert original != new
    truth = Image.open(corrected_image_fixture)

    assert new.height == truth.height
    assert new.width == truth.width

    diff = ImageChops.difference(truth, new)
    assert not diff.getbbox()

    # check lat long
    true_long = -81.64792777777778
    true_lat = 24.596927777777776
    assert imdata.coordinates.longitude - true_long < 0.0001
    assert imdata.coordinates.latitude - true_lat < 0.0001


def test_get_exif_location(image_file_fixture):
    coordinates = get_exif_location(image_file_fixture)
    assert coordinates == GeoLocation(longitude=-80.78037499999999, latitude=32.61850555555556)


def test_get_exif_location_missing(image_file_no_location_fixture):
    with pytest.raises(InvalidEXIFData):
        get_exif_location(image_file_no_location_fixture)


def test_process_image(image_file_fixture):
    imdata = ImageService.processImage(image_file_fixture)
    assert imdata.coordinates == GeoLocation(longitude=-80.78037499999999, latitude=32.61850555555556)


def test_process_image_location_missing(image_file_no_location_fixture):
    with pytest.raises(InvalidEXIFData):
        ImageService.processImage(image_file_no_location_fixture)

    imdata = ImageService.processImage(image_file_no_location_fixture, exif_geolocation=False)
    assert imdata.coordinates is None
