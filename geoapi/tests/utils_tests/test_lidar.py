import pytest
from geoapi.utils.lidar import getProj4
from geoapi.exceptions import InvalidCoordinateReferenceSystem


@pytest.mark.worker
def test_get_proj4_las_1pt2(lidar_las1pt2_file_path_fixture):
    proj4 = getProj4(lidar_las1pt2_file_path_fixture)
    assert proj4 == "+proj=utm +zone=13 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs"


@pytest.mark.worker
def test_get_proj4_las_1pt4(lidar_las1pt4_file_path_fixture):
    proj4 = getProj4(lidar_las1pt4_file_path_fixture)
    assert proj4 == "+proj=utm +zone=13 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs"


@pytest.mark.worker
def test_get_proj4_las_7030(lidar_las_epsg7030_file_path_fixture):
    proj4 = getProj4(lidar_las_epsg7030_file_path_fixture)
    assert proj4 == "+proj=geocent +datum=WGS84 +units=m +no_defs"


@pytest.mark.worker
def test_raises(empty_las_file_path_fixture):
    with pytest.raises(InvalidCoordinateReferenceSystem):
        getProj4(empty_las_file_path_fixture)
