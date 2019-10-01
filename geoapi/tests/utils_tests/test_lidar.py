import pytest
from geoapi.utils.lidar import Lidar


@pytest.mark.worker
def test_get_epsg_las_1pt2(lidar_las1pt2_file_path_fixture):
    epsg = Lidar.getEPSG(lidar_las1pt2_file_path_fixture)
    assert epsg == 26913

@pytest.mark.worker
def test_get_epsg_las_1pt4(lidar_las1pt4_file_path_fixture):
    epsg = Lidar.getEPSG(lidar_las1pt4_file_path_fixture)
    assert epsg == 26913
