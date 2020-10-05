import pytest
from geoapi.utils.lidar import getProj4, get_bounding_box_2d
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
def test_get_proj4_raises_error(empty_las_file_path_fixture):
    with pytest.raises(InvalidCoordinateReferenceSystem):
        getProj4(empty_las_file_path_fixture)


@pytest.mark.worker
def test_get_bounding_box(lidar_las1pt4_file_path_fixture):
    bounding_box = get_bounding_box_2d([lidar_las1pt4_file_path_fixture])
    assert str(bounding_box) == "POLYGON ((-105.2091339103543 39.66130604566649, " \
                                "-105.2009583662994 39.66130604566649, " \
                                "-105.2009583662994 39.66928109125274, " \
                                "-105.2091339103543 39.66928109125274, " \
                                "-105.2091339103543 39.66130604566649))"


@pytest.mark.worker
def test_get_bounding_box_epsg7030(lidar_las_epsg7030_file_path_fixture):
    bounding_box = get_bounding_box_2d([lidar_las_epsg7030_file_path_fixture])
    assert str(bounding_box) == "POLYGON ((83.56995766320439 0.02507102159538472," \
                                " 83.5682433334877 0.02507102159538472," \
                                " 83.5682433334877 0.0255677576841291," \
                                " 83.56995766320439 0.0255677576841291," \
                                " 83.56995766320439 0.02507102159538472))"
