from PIL import Image
from geoapi.services.images import ImageService, ImageData, ImageOverlay



def test_image_service_rotations(flipped_image_fixture, corrected_image_fixture):

    imdata = ImageService.resizeImage(flipped_image_fixture)
    imdata.resized.save("/tmp/test_it_is_rotated.jpg")
    original = Image.open(flipped_image_fixture)
    new = Image.open("/tmp/test_it_is_rotated.jpg")
    assert original != new
    truth = Image.open(corrected_image_fixture)
    assert truth == new




