import subprocess
import regex as re
import laspy
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union
from pyproj import Proj, transform
from geoapi.exceptions import InvalidCoordinateReferenceSystem
from typing import List


def _transform_to_geojson(epsg, point: tuple) -> tuple:
    """
    Transform point to epsg:4326
    :param epsg: int
    :param point
    :return: point
    """
    input_projection = Proj(init='EPSG:{}'.format(epsg))
    geojson_default_projection = Proj(init="epsg:4326")
    x, y = transform(input_projection, geojson_default_projection, point[0], point[1], errcheck=True)
    return x, y


class Lidar:

    @staticmethod
    def getEPSG(filePath: str):
        """
        Get EPSG of las file
        :param filePath
        :return: int
        """

        result = subprocess.run([
            "lasinfo",
            "-i",
            filePath,
            "-stdout"
        ], capture_output=True, text=True, check=True)
        wkt_re = '(?<=\"EPSG\"\,\")\d+(?=\"\]\])(?!.*EPSG)'  # LAS 1.4
        geotiff_re = '\d+(?=\s*- ProjectedCSTypeGeoKey)'  # LAS < 1.4
        for epsg_re in [wkt_re, geotiff_re]:
            epsg = re.search(epsg_re, result.stdout)
            if epsg:
                return int(epsg.group())

        raise InvalidCoordinateReferenceSystem()

    @staticmethod
    def getBoundingBox(filePaths: List[str]) -> MultiPolygon:
        """
        Get bounding box(s) from las file(s)

        :param filePaths: List[Project]
        :return: MultiPolygon or Polygon
        """
        polygons = []
        for input_file in filePaths:
            epsg = Lidar.getEPSG(input_file)

            las_file = laspy.file.File(input_file, mode="r-")
            min_point = _transform_to_geojson(epsg=epsg, point=tuple(las_file.header.min[:2]))
            max_point = _transform_to_geojson(epsg=epsg, point=tuple(las_file.header.max[:2]))
            las_file.close()

            polygons.append(Polygon([min_point,
                                     (max_point[0], min_point[1]),
                                     max_point,
                                     (min_point[0], max_point[1])]))
        return polygons[0] if len(polygons) == 1 else unary_union(polygons)
