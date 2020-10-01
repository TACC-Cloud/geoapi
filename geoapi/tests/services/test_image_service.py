from PIL import Image
from geoapi.services.images import ImageService, ImageData, ImageOverlay



def test_image_service_rotations(flipped_image_fixture, corrected_image_fixture):
    TRUE_LONG=-81.64792777777778
    TRUE_LAT=24.596927777777776
    imdata = ImageService.processImage(flipped_image_fixture)
    imdata.resized.save("/tmp/test_it_is_rotated.jpg")
    original = Image.open(flipped_image_fixture)
    new = Image.open("/tmp/test_it_is_rotated.jpg")
    assert original != new
    truth = Image.open(corrected_image_fixture)
    assert truth == new
    assert imdata.coordinates[0] - TRUE_LONG < 0.0001
    assert imdata.coordinates[1] - TRUE_LAT < 0.0001




