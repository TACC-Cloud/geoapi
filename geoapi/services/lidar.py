import subprocess
import regex as re
import laspy
import typing
from geojson import Polygon, Point
from pyproj import Proj, transform
from geoapi.tasks.lidar import convert_to_potree
from geoapi.exceptions import InvalidCoordinateReferenceSystem



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
    return (x, y)


class LidarService:

    @staticmethod
    def addLidarDataToExistingSet(projectId: int, fileObj: typing.IO):
        pass

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
        wkt_re = '(?<=\"EPSG\"\,\")\d+(?=\"\]\])(?!.*EPSG)' # LAS 1.4
        geotiff_re = '\d+(?=\s*- ProjectedCSTypeGeoKey)' # LAS < 1.4
        for epsg_re in [wkt_re, geotiff_re]:
            epsg = re.search(epsg_re, result.stdout)
            if epsg:
                return int(epsg.group())

        raise InvalidCoordinateReferenceSystem()

    @staticmethod
    def getBoundingBox(filePath: str) -> Polygon:
        """
        Get bounding box from las file
        :param filePath
        :return: Polygon
        """
        epsg = LidarService.getEPSG(filePath)

        las_file = laspy.file.File(filePath, mode="r-")
        min_point = _transform_to_geojson(epsg=epsg, point=tuple(las_file.header.min[:2]))
        max_point = _transform_to_geojson(epsg=epsg, point=tuple(las_file.header.max[:2]))
        las_file.close()

        return Polygon([[Point(min_point), Point((max_point[0], min_point[1])),
                         Point(max_point), Point((min_point[0],max_point[1])),
                         Point(min_point)]])

    @staticmethod
    def addProcessedLidarData(projectId: int, featureId: int, filePath: str) -> None:
        """
        Process a las/laz file and add to a project. This is asynchronous. The dataset will be converted
        to potree viewer format.
        :param projectId: int
        :param featureId: int
        :param filePath
        :return: None
        """
        convert_to_potree.apply_async(args=[projectId, featureId, filePath])