import subprocess
import json
import laspy
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union
from pyproj import Proj, transform
from geoapi.exceptions import InvalidCoordinateReferenceSystem
from typing import List


def _transform_to_geojson(proj4, point: tuple) -> tuple:
    """
    Transform point to epsg:4326
    :param proj4: proj string
    :param point
    :return: point
    """
    input_projection = Proj(proj4)
    geojson_default_projection = Proj(init="epsg:4326")
    x, y, _ = transform(input_projection, geojson_default_projection, point[0], point[1], point[2], errcheck=True)
    return x, y


def getProj4(filePath: str):
    """
    Get proj4 of las file
    :param filePath
    :return: str
    :raises InvalidCoordinateReferenceSystem
    """
    result = subprocess.run([
        "pdal",
        "info",
        filePath,
        "--metadata"
    ], capture_output=True, text=True, check=True)
    info = json.loads(result.stdout)
    try:
        proj4 = info['metadata']['srs']['proj4']
        if proj4:
            return proj4
    except KeyError:
        pass

    raise InvalidCoordinateReferenceSystem()


def get_bounding_box_2d(filePaths: List[str]) -> MultiPolygon:
    """
    Get 2D bounding box(s) from las file(s)

    Bounding box is in epsg:4326

    :param filePaths: List[Project]
    :return: MultiPolygon or Polygon
    """

    # TODO this could all be replaced by calling `pdal info` which provides
    #  an EPSG:4326 boundary box in our desired 4326 crs. The downside is that
    #  pdal info takes a long time (single threaded)
    polygons = []
    for input_file in filePaths:
        proj4 = getProj4(input_file)

        las_file = laspy.file.File(input_file, mode="r-")
        min_point = _transform_to_geojson(proj4=proj4, point=tuple(las_file.header.min[:3]))
        max_point = _transform_to_geojson(proj4=proj4, point=tuple(las_file.header.max[:3]))
        las_file.close()

        polygons.append(Polygon([min_point,
                                 (max_point[0], min_point[1]),
                                 max_point,
                                 (min_point[0], max_point[1])]))
    return polygons[0] if len(polygons) == 1 else unary_union(polygons)
