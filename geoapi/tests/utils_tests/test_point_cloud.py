import pytest
from geoapi.utils.point_cloud import getProj4, get_bounding_box_2d
from geoapi.exceptions import InvalidCoordinateReferenceSystem
from shapely.geometry import Polygon


@pytest.mark.worker
def test_get_proj4_las_1pt2(lidar_las1pt2_file_path_fixture):
    proj4 = getProj4(lidar_las1pt2_file_path_fixture)
    assert proj4 == "+proj=utm +zone=13 +datum=NAD83 +units=m +no_defs"


@pytest.mark.worker
def test_get_proj4_las_1pt4(lidar_las1pt4_file_path_fixture):
    proj4 = getProj4(lidar_las1pt4_file_path_fixture)
    assert (
        proj4
        == "+proj=utm +zone=13 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs"
    )


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
    assert (
        str(bounding_box)
        == "POLYGON ((-105.20913391035427 39.661306045666485, -105.20095836629945 39.661306045666485,"
        " -105.20095836629945 39.66928109125274, -105.20913391035427 39.66928109125274,"
        " -105.20913391035427 39.661306045666485))"
    )


@pytest.mark.worker
def test_get_bounding_box_epsg7030(lidar_las_epsg7030_file_path_fixture):
    bounding_box = get_bounding_box_2d([lidar_las_epsg7030_file_path_fixture])
    assert (
        str(bounding_box) == "POLYGON ((83.56995766320439 0.0250710215953847,"
        " 83.5682433334877 0.0250710215953847,"
        " 83.5682433334877 0.0255677576841291,"
        " 83.56995766320439 0.0255677576841291,"
        " 83.56995766320439 0.0250710215953847))"
    )


@pytest.mark.worker
def test_get_bounding_box_medium_size_compressed_laz(
    lidar_medium_size_compressed_las1pt2,
):
    bounding_box = get_bounding_box_2d([lidar_medium_size_compressed_las1pt2])
    expected = Polygon(
        [
            (-105.2091, 39.6613),
            (-105.2010, 39.6613),
            (-105.2010, 39.6693),
            (-105.2091, 39.6693),
        ]
    )
    assert bounding_box.equals_exact(expected, tolerance=1e-3)
