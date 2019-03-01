import os
import pathlib
import uuid
import json
from typing import List, IO
from shapely.geometry import Point
from geoalchemy2.shape import from_shape, to_shape
import geojson

from geoapi.services.images import ImageService
from geoapi.settings import settings
from geoapi.models import Feature, FeatureAsset
from geoapi.db import db_session
from geoapi.exceptions import InvalidGeoJSON

class FeaturesService:

    IMAGE_FILE_EXTENSIONS = (
        'jpeg', 'png', 'tiff'
    )

    VIDEO_FILE_EXTENSIONS = (
        'mp4', 'mov'
    )

    @staticmethod
    def get(featureId: int)-> Feature:
        """
        Retreive a single Feature
        :param featureId: int
        :return: Feature
        """
        return Feature.query.get(featureId)


    @staticmethod
    def query(q: dict) -> List[Feature]:
        """
        Query/filter Features based on a bounding box or feature properties
        :param q: dict
        :return: GeoJSON
        """
        pass

    @staticmethod
    def delete(featureId: int) -> None:
        """
        Delete a Feature and any assets tied to it.
        :param featureId: int
        :return: None
        """
        # TODO: remove any assets tied to the feature also
        feat = Feature.query.get(featureId)
        base_asset_path = os.path.join(settings.ASSETS_BASE_DIR, str(feat.project_id))
        assets = FeatureAsset.query.filter(FeatureAsset.feature_id == featureId)
        for asset in assets:
            asset_path = os.path.join(base_asset_path, str(asset.uuid))




    @staticmethod
    def setProperties(featureId: int, props: dict) -> Feature:
        """
        Set the properties of a feature.
        :param featureId: int
        :param props: dict
        :return:
        """
        feat = Feature.query.get(featureId)
        # TODO: Throw assert if not found?
        # TODO: PROTECT assets and styles attributes
        feat.properties = props
        db_session.commit()
        return feat


    @staticmethod
    def addGeoJSON(projectId: int, feature: dict) -> dict:
        """
        Add a GeoJSON feature to a project
        :param projectId: int
        :param feature: dict
        :return: Feature
        """
        try:
            data = geojson.loads(json.dumps(feature))
        except ValueError:
            raise InvalidGeoJSON

        if data["type"] == "Feature":
            feat = Feature.fromGeoJSON(data)
            feat.project_id = projectId
            db_session.add(feat)
        elif data["type"] == "FeatureCollection":
            fc = geojson.FeatureCollection(data)
            for feature in fc.features:
                feat = Feature.fromGeoJSON(feature)
                feat.project_id = projectId
                db_session.add(feat)
        else:
            raise InvalidGeoJSON("Valid GeoJSON must be either a Feature or FeatureCollection.")
        db_session.commit()
        return {"status": "ok"}


    @staticmethod
    def fromImage(projectId: int, fileObj: IO, metadata: dict) -> None:
        """
        Create a Point feature from a georeferenced image
        :param projectId: int
        :param fileObj: file
        :param metadata: dict
        :return: None
        """
        imdata = ImageService.processImage(fileObj)
        point = Point(imdata.coordinates)
        f = Feature()
        f.project_id = projectId
        f.the_geom = from_shape(point, srid=4326)
        f.properties = metadata

        asset_uuid = uuid.uuid4()
        asset_path = os.path.join("/assets", str(projectId), str(asset_uuid))
        fa = FeatureAsset(
            uuid=asset_uuid,
            asset_type="image",
            path=asset_path,
            feature=f,
        )
        f.assets.append(fa)
        base_filepath = os.path.join(settings.ASSETS_BASE_DIR, str(projectId))
        pathlib.Path(base_filepath).mkdir(parents=True, exist_ok=True)
        imdata.thumb.save(os.path.join(base_filepath, str(asset_uuid) + ".thumb.jpeg"), "JPEG")
        imdata.resized.save(os.path.join(base_filepath, str(asset_uuid)+ '.jpeg'), "JPEG")
        db_session.add(f)
        db_session.commit()

    @staticmethod
    def createFeatureAsset(projectId:int , featureId: int, fileObj: IO) -> None:
        """

        :param projectId: int
        :param featureId: int
        :param fileObj: file
        :return: FeatureAsset
        """
        feat = Feature.query.get(featureId)
        imdata = ImageService.processImage(fileObj)
        asset_uuid = uuid.uuid4()
        # asset_path will be used to serve the asset with front end server
        asset_path = os.path.join("/assets", str(projectId), str(asset_uuid))
        fa = FeatureAsset(
            uuid=asset_uuid,
            asset_type="image",
            path=asset_path,

        )
        fa.feature = feat
        base_filepath = os.path.join(settings.ASSETS_BASE_DIR, str(projectId))
        pathlib.Path(base_filepath).mkdir(parents=True, exist_ok=True)
        imdata.thumb.save(os.path.join(base_filepath, str(asset_uuid) + ".thumb.jpeg"), "JPEG")
        imdata.resized.save(os.path.join(base_filepath, str(asset_uuid)+".jpeg"), "JPEG")
        db_session.add(fa)
        db_session.commit()


    @staticmethod
    def addLidarData(projectID: int, fileObj) -> None:
        """
        Add a las/laz file to a project. This is asynchronous. The dataset will be converted
        to potree viewer format and processed to get the extent which will be shown on the map.
        :param projectID: int
        :param fileObj: file
        :return: None
        """
        pass

    @staticmethod
    def importFromAgave(projectId, agaveSystemId, filePath) -> None:
        """
        Import data stored in an agave file system. This is asynchronous.
        :param projectId: int
        :param agaveSystemId: str
        :param filePath: str
        :return: None
        """
        pass