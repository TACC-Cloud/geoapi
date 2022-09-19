from geoapi.services.images import ImageService, get_exif_location
from PIL import Image, ImageChops



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
    assert imdata.coordinates[0] - true_long < 0.0001
    assert imdata.coordinates[1] - true_lat < 0.0001


def test_get_exif_location(image_file_fixture):
    coordinates = get_exif_location(image_file_fixture)
    assert coordinates == (-80.78037499999999, 32.61850555555556)


def test_process_image(image_file_fixture):
    imdata = ImageService.processImage(image_file_fixture)
    assert imdata.coordinates == (-80.78037499999999, 32.61850555555556)
