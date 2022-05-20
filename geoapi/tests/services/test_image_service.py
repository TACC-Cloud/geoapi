from PIL import Image
from geoapi.services.images import ImageService


def test_image_service_rotations(flipped_image_fixture, corrected_image_fixture):
    true_long = -81.64792777777778
    true_lat = 24.596927777777776
    imdata = ImageService.processImage(flipped_image_fixture)
    imdata.resized.save("/tmp/test_it_is_rotated.jpg")
    original = Image.open(flipped_image_fixture)
    new = Image.open("/tmp/test_it_is_rotated.jpg")
    assert original != new
    truth = Image.open(corrected_image_fixture)
    assert truth == new
    assert imdata.coordinates[0] - true_long < 0.0001
    assert imdata.coordinates[1] - true_lat < 0.0001
