import os
import pathlib
import uuid
import json
import tempfile
from datetime import datetime
from typing import List, IO, Dict

from geoapi.services.videos import VideoService
from shapely.geometry import Point, shape
import fiona
from geoalchemy2.shape import from_shape
import geojson

from geoapi.services.images import ImageService, ImageData
from geoapi.settings import settings
from geoapi.models import Feature, FeatureAsset, Overlay
from geoapi.db import db_session
from geoapi.exceptions import InvalidGeoJSON, ApiException
from geoapi.utils.assets import make_project_asset_dir, delete_assets, get_asset_relative_path
from geoapi.log import logging
from geoapi.utils import geometries

import geoapi.tasks.external_data as data_tasks

logger = logging.getLogger(__name__)


class FeaturesService:
    GEOJSON_FILE_EXTENSIONS = (
        'json', 'geojson'
    )

    IMAGE_FILE_EXTENSIONS = (
        'jpeg', 'jpg',
    )

    VIDEO_FILE_EXTENSIONS = (
        'mp4', 'mov', 'mpeg4', 'webm'
    )

    AUDIO_FILE_EXTENSIONS = (
        'mp3', 'aac'
    )

    GPX_FILE_EXTENSIONS = (
        'gpx',
    )

    ALLOWED_GEOSPATIAL_EXTENSIONS = IMAGE_FILE_EXTENSIONS + GPX_FILE_EXTENSIONS + GEOJSON_FILE_EXTENSIONS

    ALLOWED_EXTENSIONS = IMAGE_FILE_EXTENSIONS + VIDEO_FILE_EXTENSIONS \
                         + AUDIO_FILE_EXTENSIONS + GPX_FILE_EXTENSIONS \
                         + GEOJSON_FILE_EXTENSIONS

    @staticmethod
    def get(featureId: int) -> Feature:
        """
        Retreive a single Feature
        :param featureId: int
        :return: Feature
        """
        return db_session.query(Feature).get(featureId)

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
        feat = db_session.query(Feature).get(featureId)
        assets = db_session.query(FeatureAsset).filter(FeatureAsset.feature_id == featureId)
        for asset in assets:
            delete_assets(projectId=feat.project_id, uuid=asset.uuid)
        db_session.delete(feat)
        db_session.commit()

    @staticmethod
    def setProperties(featureId: int, props: Dict) -> Feature:
        """
        Set the properties of a feature.
        :param featureId: int
        :param props: dict
        :return: Feature
        """
        feat = db_session.query(Feature).get(featureId)
        # TODO: Throw assert if not found?
        # TODO: PROTECT assets and styles attributes
        feat.properties = props
        db_session.commit()
        return feat

    @staticmethod
    def setStyles(featureId: int, styles: Dict) -> Feature:
        """
        Set the styles of a feature.
        :param featureId: int
        :param styles: dict
        :return: Feature
        """
        feat = db_session.query(Feature).get(featureId)
        # TODO: PROTECT assets and styles attributes
        feat.styles = styles
        db_session.commit()
        return feat

    @staticmethod
    def addGeoJSON(projectId: int, feature: Dict, original_path=None) -> List[Feature]:
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
        features = []
        if data["type"] == "Feature":
            feat = Feature.fromGeoJSON(data)
            feat.project_id = projectId
            # strip out image_src, thumb_src if they are there from the old hazmapper geojson
            feat = FeaturesService._importHazmapperV1Images(feat)
            db_session.add(feat)
            features.append(feat)
        elif data["type"] == "FeatureCollection":
            fc = geojson.FeatureCollection(data)
            for feature in fc.features:
                feat = Feature.fromGeoJSON(feature)
                feat.project_id = projectId
                feat = FeaturesService._importHazmapperV1Images(feat)
                db_session.add(feat)
                features.append(feat)
        else:
            raise InvalidGeoJSON("Valid GeoJSON must be either a Feature or FeatureCollection.")
        db_session.commit()
        return features

    #TODO: we should be able to get rid of the old Hazmapper stuff at some point...
    @staticmethod
    def _importHazmapperV1Images(feat: Feature) -> Feature:
        if feat.properties.get("image_src"):
            logger.info("Getting image from src")
            imdata = ImageService.processBase64(feat.properties.get("image_src"))
            fa = FeaturesService.featureAssetFromImData(feat.project_id, imdata)
            feat.assets.append(fa)
            feat.properties.pop("image_src")
        if feat.properties.get("thumb_src"):
            feat.properties.pop("thumb_src")
        return feat


    @staticmethod
    def fromLatLng(projectId: int, lat: float, lng: float, metadata: Dict) -> Feature:
        point = Point(lng, lat)
        f = Feature()
        f.project_id = projectId
        f.the_geom = from_shape(point, srid=4326)
        f.properties = metadata or {}
        return f

    @staticmethod
    def fromGPX(projectId: int, fileObj: IO, metadata: Dict, original_path=None) -> Feature:

        # TODO: Fiona should support reading from the file directly, this MemoryFile business
        #  should not be needed
        with fiona.io.MemoryFile(fileObj) as memfile:
            with memfile.open(layer="tracks") as collection:
                track = collection[0]
                shp = shape(track["geometry"])
                feat = Feature()
                feat.project_id = projectId
                feat.the_geom = from_shape(geometries.convert_3D_2D(shp), srid=4326)
                feat.properties = metadata or {}
                db_session.add(feat)
                db_session.commit()
                return feat

    @staticmethod
    def fromGeoJSON(projectId: int, fileObj: IO, metadata: Dict) -> List[Feature]:
        """

        :param projectId: int
        :param fileObj: file descriptor
        :param metadata: Dict of <key, val> pairs
        :return: Feature
        """
        data = json.loads(fileObj.read())
        fileObj.close()
        return FeaturesService.addGeoJSON(projectId, data)

    @staticmethod
    def fromFileObj(projectId: int, fileObj: IO, metadata: Dict, original_path: str=None) -> List[Feature]:
        ext = pathlib.Path(fileObj.filename).suffix.lstrip(".").lower()
        if ext in FeaturesService.IMAGE_FILE_EXTENSIONS:
            return [FeaturesService.fromImage(projectId, fileObj, metadata, original_path)]
        elif ext in FeaturesService.GPX_FILE_EXTENSIONS:
            return [FeaturesService.fromGPX(projectId, fileObj, metadata, original_path)]
        elif ext in FeaturesService.GEOJSON_FILE_EXTENSIONS:
            return FeaturesService.fromGeoJSON(projectId, fileObj, {})
        else:
            raise ApiException("Filetype not supported for direct upload. Create a feature and attach as an asset?")

    @staticmethod
    def fromImage(projectId: int, fileObj: IO, metadata: Dict, original_path: str=None) -> Feature:
        """
        Create a Point feature from a georeferenced image
        :param projectId: int
        :param fileObj: file
        :param metadata: dict
        :return: None
        """
        t1 = datetime.now()
        imdata = ImageService.processImage(fileObj)
        fileObj.close()
        point = Point(imdata.coordinates)
        f = Feature()
        f.project_id = projectId
        f.the_geom = from_shape(point, srid=4326)
        f.properties = metadata

        asset_uuid = uuid.uuid4()
        base_filepath = make_project_asset_dir(projectId)
        asset_path = os.path.join(base_filepath, str(asset_uuid) + '.jpeg')

        fa = FeatureAsset(
            uuid=asset_uuid,
            asset_type="image",
            original_path=original_path,
            display_path=original_path,
            path=get_asset_relative_path(asset_path),
            feature=f,
        )
        f.assets.append(fa)
        imdata.thumb.save(os.path.join(base_filepath, str(asset_uuid) + ".thumb.jpeg"), "JPEG")
        imdata.resized.save(os.path.join(base_filepath, str(asset_uuid) + '.jpeg'), "JPEG")
        db_session.add(f)
        db_session.commit()
        t2 = datetime.now()
        diff = (t2 - t1).microseconds
        logger.info("FeaturesService:fromImage :: Feature created in {tdiff}".format(tdiff=diff))
        return f

    @staticmethod
    def createFeatureAsset(projectId: int, featureId: int, fileObj: IO, original_path: str = None) -> Feature:
        """
        Create a feature asset and save the static content to the ASSETS_BASE_DIR
        :param projectId: int
        :param featureId: int
        :param fileObj: file
        :return: FeatureAsset
        """
        fpath = pathlib.Path(fileObj.filename)
        ext = fpath.suffix.lstrip('.')
        if ext in FeaturesService.IMAGE_FILE_EXTENSIONS:
            fa = FeaturesService.createImageFeatureAsset(projectId, fileObj, original_path=original_path)
        elif ext in FeaturesService.VIDEO_FILE_EXTENSIONS:
            fa = FeaturesService.createVideoFeatureAsset(projectId, fileObj, original_path=original_path)
        else:
            raise ApiException("Invalid format for feature assets")

        feat = FeaturesService.get(featureId)
        feat.assets.append(fa)
        db_session.commit()
        return feat

    @staticmethod
    def featureAssetFromImData(projectId: int, imdata: ImageData) -> FeatureAsset:
        asset_uuid = uuid.uuid4()
        base_filepath = make_project_asset_dir(projectId)
        asset_path = os.path.join(base_filepath, str(asset_uuid) + '.jpeg')
        imdata.thumb.save(pathlib.Path(asset_path).with_suffix(".thumb.jpeg"), "JPEG")
        imdata.resized.save(asset_path, "JPEG")
        fa = FeatureAsset(
            uuid=asset_uuid,
            asset_type="image",
            path=get_asset_relative_path(asset_path)
        )
        return fa

    @staticmethod
    def createImageFeatureAsset(projectId: int, fileObj: IO, original_path: str=None) -> FeatureAsset:
        asset_uuid = uuid.uuid4()
        imdata = ImageService.resizeImage(fileObj)
        base_filepath = make_project_asset_dir(projectId)
        asset_path = os.path.join(base_filepath, str(asset_uuid) + '.jpeg')
        imdata.thumb.save(pathlib.Path(asset_path).with_suffix(".thumb.jpeg"), "JPEG")
        imdata.resized.save(asset_path, "JPEG")
        fa = FeatureAsset(
            uuid=asset_uuid,
            asset_type="image",
            original_path=original_path,
            display_path=original_path,
            path=get_asset_relative_path(asset_path)
        )
        return fa

    @staticmethod
    def createVideoFeatureAsset(projectId: int, fileObj: IO, original_path:str =None) -> FeatureAsset:
        """

        :param projectId:
        :param fileObj: Should be a file descriptor of a file in tmp
        :return: FeatureAsset
        """
        asset_uuid = uuid.uuid4()
        base_filepath = make_project_asset_dir(projectId)
        save_path = os.path.join(base_filepath, str(asset_uuid) + '.mp4')
        with tempfile.TemporaryDirectory() as tmpdirname:
            tmp_path = os.path.join(tmpdirname, str(asset_uuid))
            with open(tmp_path, 'wb') as tmp:
                tmp.write(fileObj.read())
            encoded_path = VideoService.transcode(tmp_path)
            with open(encoded_path, 'rb') as enc:
                with open(save_path, 'wb') as f:
                    f.write(enc.read())
        # clean up the tmp file
        os.remove(encoded_path)
        fa = FeatureAsset(
            uuid=asset_uuid,
            original_path=original_path,
            display_path=original_path,
            path=get_asset_relative_path(save_path),
            asset_type="video"
        )
        return fa

    @staticmethod
    def clusterKMeans(projectId: int, numClusters: int = 20) -> Dict:
        """
        Cluster all the Point geometries in a project
        :param numClusters: int
        :param projectId: int
        :return: FeatureCollection
        """
        # TODO: Add filtering clause on the sub-select
        q = """
        select json_build_object(
               'type', 'FeatureCollection',
               'features', jsonb_agg(features.feature)
           )
        from (
                 select json_build_object(
                                'type', 'Feature',
                                'geometry', ST_AsGeoJSON(clusters.center)::jsonb,
                                'properties', json_build_object(
                                        'count', clusters.count
                                    )
                            ) as feature
                 from (
                          select ST_Centroid(ST_Collect(the_geom)) as center, count(clusters.cid) as count
                          from (
                                   SELECT ST_ClusterKMeans(the_geom, :numClusters) OVER () AS cid, the_geom
                                   from features
                                   where project_id = :projectId
                               ) as clusters
                          group by clusters.cid
                      ) as clusters
             ) as features
        """
        result = db_session.execute(q, {'projectId': projectId, 'numClusters': numClusters}).first()
        clusters = result[0]
        return clusters

    @staticmethod
    def addOverlay(projectId: int, fileObj: IO, bounds: List[float], label: str) -> Overlay:
        """

        :param projectId: int
        :param fileObj: IO
        :param bounds: List [minLon, minLat, maxLon, maxLat]
        :param label: str
        :return: None
        """

        imdata = ImageService.processOverlay(fileObj)
        ov = Overlay()
        ov.label = label
        ov.minLon = bounds[0]
        ov.minLat = bounds[1]
        ov.maxLon = bounds[2]
        ov.maxLat = bounds[3]
        ov.project_id = projectId
        ov.uuid = uuid.uuid4()
        asset_path = os.path.join(str(make_project_asset_dir(projectId)), str(ov.uuid) + '.jpeg')
        ov.path = get_asset_relative_path(asset_path)
        imdata.original.save(asset_path, 'JPEG')
        imdata.thumb.save(pathlib.Path(asset_path).with_suffix(".thumb.jpeg"), "JPEG")
        db_session.add(ov)
        db_session.commit()
        return ov

    @staticmethod
    def getOverlays(projectId: int) -> List[Overlay]:
        overlays = db_session.query(Overlay).filter_by(project_id=projectId).all()
        return overlays

    @staticmethod
    def deleteOverlay(projectId: int, overlayId: int) -> None:
        ov = db_session.query(Overlay).get(overlayId)
        delete_assets(projectId=projectId, uuid=ov.uuid)
        db_session.delete(ov)
        db_session.commit()

