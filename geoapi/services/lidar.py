import laspy
import typing
from geojson import Polygon, Point
from pyproj import Proj, transform
from geoapi.tasks.lidar import convert_to_potree

def _transform_to_geojson(epsg, point: tuple) -> tuple:
    inProj = Proj(init='EPSG:{}'.format(epsg))
    geojson_default_projection = Proj(init="epsg:4326")
    x, y = transform(inProj, geojson_default_projection, point[0], point[1], errcheck=True)
    return (x, y)

class LidarService:

    @staticmethod
    def addLidarDataToExistingSet(projectId: int, fileObj: typing.IO):
        pass

    @staticmethod
    def getBoundingBox(filePath: str) -> Polygon:
        """
        Get bounding box from las file
        :param filePath
        :return: Polygon
        """
        # TODO get current epsg
        epsg = 32614

        las_file = laspy.file.File(filePath, mode="r-")
        min_point = _transform_to_geojson(epsg=epsg, point=tuple(las_file.header.min[:2]))
        max_point = _transform_to_geojson(epsg=epsg, point=tuple(las_file.header.max[:2]))
        las_file.close()

        return Polygon([[Point(min_point), Point((max_point[0], min_point[1])),
                         Point(max_point), Point((min_point[0],max_point[1])),
                         Point(min_point)]])

    @staticmethod
    def addLidarData(projectId: int, featureId: int, filePath: str) -> None:
        """
        Add a las/laz file to a project. This is asynchronous. The dataset will be converted
        to potree viewer format and processed to get the extent which will be shown on the map.
        :param projectId: int
        :param featureId: int
        :param filePath
        :return: None
        """
        convert_to_potree.apply_async(args=[projectId, featureId, filePath])