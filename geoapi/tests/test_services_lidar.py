import pytest
from geoapi.services.lidar import LidarService


def test_get_epsg_las_1pt2(lidar_las1pt2_file_path_fixture):
    epsg = LidarService.getEPSG(lidar_las1pt2_file_path_fixture)
    assert epsg == 26913

def test_get_epsg_las_1pt4(lidar_las1pt4_file_path_fixture):
    epsg = LidarService.getEPSG(lidar_las1pt4_file_path_fixture)
    assert epsg == 26913